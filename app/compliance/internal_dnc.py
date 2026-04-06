"""Internal DNC management — append-only, irrevocable (C-12).

Any DNC request via any channel creates a permanent block.
Reversal requires explicit manager action with audit trail (no DELETE).
"""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.dnc import DncReversalAudit, InternalDNC

logger = get_logger("internal_dnc")


async def add_to_dnc(
    phone: str | None = None,
    email: str | None = None,
    source_channel: str = "manual",
    added_by: str = "system",
) -> bool:
    """Add a phone/email to the internal DNC list. Append-only.

    Args:
        phone: Phone number to block.
        email: Email to block.
        source_channel: How the DNC request came in (sms, call, webhook, manual).
        added_by: Who added it (system, manager, ghl_webhook).

    Returns:
        True if a new entry was created.
    """
    if not phone and not email:
        return False

    async with get_session() as session:
        if phone:
            existing = await session.execute(
                select(InternalDNC.id)
                .where(
                    InternalDNC.phone == phone,
                    InternalDNC.is_active == True,  # noqa: E712
                )
                .limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                return False

        if email:
            existing_e = await session.execute(
                select(InternalDNC.id)
                .where(
                    InternalDNC.email == email,
                    InternalDNC.is_active == True,  # noqa: E712
                )
                .limit(1)
            )
            if existing_e.scalar_one_or_none() is not None:
                return False

        entry = InternalDNC(
            phone=phone,
            email=email,
            source_channel=source_channel,
            added_by=added_by,
            added_at=datetime.now(timezone.utc),
            is_active=True,
        )
        session.add(entry)

    logger.info("dnc_added", phone=phone, email=email, source=source_channel)
    return True


async def is_on_dnc(phone: str | None = None, email: str | None = None) -> bool:
    """Check if a phone or email is on the active internal DNC list.

    Args:
        phone: Phone number to check.
        email: Email to check.
    """
    if not phone and not email:
        return False

    async with get_session() as session:
        if phone:
            result = await session.execute(
                select(InternalDNC.id)
                .where(
                    InternalDNC.phone == phone,
                    InternalDNC.is_active == True,  # noqa: E712
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
                    InternalDNC.is_active == True,  # noqa: E712
                )
                .limit(1)
            )
            if result.scalar_one_or_none() is not None:
                return True
    return False


async def reverse_dnc_block(
    internal_dnc_id: int,
    reversed_by: str,
    reason: str | None = None,
) -> bool:
    """Manager-only: deactivate a DNC row and append audit (never DELETE).

    Args:
        internal_dnc_id: Primary key of ``internal_dnc`` row.
        reversed_by: Manager identifier (e.g. email or username).
        reason: Optional free-text reason.

    Returns:
        True if a row was deactivated.
    """
    async with get_session() as session:
        row = await session.get(InternalDNC, internal_dnc_id)
        if row is None or not row.is_active:
            return False
        row.is_active = False
        session.add(
            DncReversalAudit(
                internal_dnc_id=internal_dnc_id,
                reversed_by=reversed_by,
                reason=reason,
            )
        )
    logger.info(
        "dnc_reversal",
        internal_dnc_id=internal_dnc_id,
        reversed_by=reversed_by,
        component="internal_dnc",
        status="reversed",
        error_type="",
        context=(reason or "")[:200],
    )
    return True
