"""4-layer compliance gate orchestrator — absolute, zero tolerance (C-02).

Layer order: Internal DNC → DataMerch → DNC.com/CCC → Blacklist Alliance.
A lead failing ANY layer is permanently blocked. No override, no soft flag.
"""

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.dnc import ComplianceCheck, InternalDNC
from app.models.lead import Lead

logger = get_logger("compliance_gate")


def _safe_http_error_log(gate: str, exc: Exception) -> None:
    """Log HTTP client errors without query strings or auth headers (COMPLY-07)."""
    if isinstance(exc, httpx.HTTPStatusError):
        req = exc.request
        url = str(req.url).split("?")[0]
        logger.error(
            f"{gate}_http_error",
            component="compliance_gate",
            status="error",
            error_type=type(exc).__name__,
            context=f"{req.method} {url} status={exc.response.status_code}",
        )
        return
    logger.error(
        f"{gate}_error",
        component="compliance_gate",
        status="error",
        error_type=type(exc).__name__,
        context=str(exc)[:200],
    )


async def check_internal_dnc(phone: str | None, email: str | None) -> bool:
    """Layer 1: Check internal DNC list (checked FIRST, before paid APIs).

    Args:
        phone: Phone number to check.
        email: Email to check.

    Returns:
        True if BLOCKED (on active DNC list).
    """
    if not phone and not email:
        return False
    async with get_session() as session:
        if phone:
            result = await session.execute(
                select(InternalDNC.id)
                .where(
                    InternalDNC.phone == phone,
                    InternalDNC.is_active.is_(True),
                )
                .limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
        if email:
            result = await session.execute(
                select(InternalDNC.id)
                .where(
                    InternalDNC.email == email,
                    InternalDNC.is_active.is_(True),
                )
                .limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
    return False


async def check_datamerch(debtor_name: str, **kwargs) -> bool:
    """Layer 2: Check DataMerch for MCA default history (C-15).

    Args:
        debtor_name: Business name to check.

    Returns:
        True if BLOCKED (known defaulter or litigator), or fail-closed when configured.
    """
    from app.config import Settings

    settings = Settings()
    if not settings.DATAMERCH_API_KEY:
        logger.warning(
            "datamerch_unconfigured",
            component="compliance_gate",
            status="warn",
            error_type="missing_key",
            context="datamerch_fallback",
        )
        if settings.COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH:
            return True
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.datamerch.com/v1/check",
                params={"name": debtor_name},
                headers={"Authorization": f"Bearer {settings.DATAMERCH_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return bool(data.get("blocked", False))
    except Exception as exc:
        _safe_http_error_log("datamerch", exc)
        return False


async def check_dnc_scrub(phone: str | None) -> bool:
    """Layer 3: Check federal + state DNC lists via CCC/DNC.com API.

    Args:
        phone: Phone number to check.

    Returns:
        True if BLOCKED (on DNC list).
    """
    if not phone:
        return False
    from app.config import Settings

    settings = Settings()
    if not settings.DNC_SCRUB_API_KEY:
        logger.warning(
            "dnc_scrub_unconfigured",
            component="compliance_gate",
            status="warn",
            error_type="missing_key",
            context="",
        )
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.dnc.com/v1/check",
                params={"phone": phone},
                headers={"Authorization": f"Bearer {settings.DNC_SCRUB_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return bool(data.get("on_dnc_list", False))
    except Exception as exc:
        _safe_http_error_log("dnc_scrub", exc)
        return False


async def check_blacklist_alliance(phone: str | None) -> bool:
    """Layer 4: Check Blacklist Alliance for TCPA litigators.

    Args:
        phone: Phone number to check.

    Returns:
        True if BLOCKED (known litigator).
    """
    if not phone:
        return False
    from app.config import Settings

    settings = Settings()
    if not settings.BLACKLIST_API_KEY:
        logger.warning(
            "blacklist_unconfigured",
            component="compliance_gate",
            status="warn",
            error_type="missing_key",
            context="",
        )
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.blacklistalliance.com/v1/lookup",
                params={"phone": phone},
                headers={"Authorization": f"Bearer {settings.BLACKLIST_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return bool(data.get("is_litigator", False))
    except Exception as exc:
        _safe_http_error_log("blacklist_alliance", exc)
        return False


async def _log_check(lead_id: int, gate_name: str, result: str) -> None:
    """Log a compliance check to the audit trail.

    Args:
        lead_id: Lead being checked.
        gate_name: Name of the compliance layer.
        result: 'pass' or 'blocked'.
    """
    async with get_session() as session:
        check = ComplianceCheck(
            lead_id=lead_id,
            gate_name=gate_name,
            result=result,
            checked_at=datetime.now(timezone.utc),
        )
        session.add(check)


async def run_compliance_gate(lead: Lead) -> bool:
    """Run all 4 compliance layers sequentially. Block on ANY failure.

    Args:
        lead: Lead to check.

    Returns:
        True if lead PASSES all checks and can be exported.
    """
    layers = [
        ("internal_dnc", check_internal_dnc, {"phone": lead.phone, "email": lead.email}),
        ("datamerch", check_datamerch, {"debtor_name": lead.debtor_name}),
        ("dnc_scrub", check_dnc_scrub, {"phone": lead.phone}),
        ("blacklist_alliance", check_blacklist_alliance, {"phone": lead.phone}),
    ]

    for gate_name, check_fn, kwargs in layers:
        blocked = await check_fn(**kwargs)
        result = "blocked" if blocked else "pass"
        await _log_check(lead.id, gate_name, result)
        if blocked:
            await _mark_blocked(lead, gate_name)
            return False

    await _mark_compliant(lead)
    return True


async def _mark_blocked(lead: Lead, gate_name: str) -> None:
    """Permanently block a lead — no override, no export-with-warning.

    Args:
        lead: Lead to block.
        gate_name: Which gate blocked it.
    """
    async with get_session() as session:
        row = await session.get(Lead, lead.id)
        if row is not None:
            row.compliance_status = f"blocked:{gate_name}"
            session.add(row)
    logger.warning(
        "lead_blocked",
        component="compliance_gate",
        status="blocked",
        error_type="",
        context=gate_name,
        lead_id=lead.id,
        gate=gate_name,
    )


async def _mark_compliant(lead: Lead) -> None:
    """Mark a lead as compliance-cleared.

    Args:
        lead: Lead that passed all gates.
    """
    async with get_session() as session:
        row = await session.get(Lead, lead.id)
        if row is not None:
            row.compliance_status = "cleared"
            session.add(row)
    logger.info(
        "lead_cleared",
        component="compliance_gate",
        status="cleared",
        error_type="",
        context="",
        lead_id=lead.id,
    )
