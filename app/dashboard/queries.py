"""Dashboard data queries — aggregations for the manager view."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.db import get_session
from app.models.account import BusinessAccount
from app.models.filing import UCCFiling
from app.models.lead import Lead
from app.models.mca_alias import MCAlias
from app.models.operations import PipelineEvent, ScraperRun

# Account qualifies as a lead when rollup shows at least one MCA funder on filings.
MCA_LEAD_MIN_FUNDERS = 1
CONSOLIDATION_TIERS = ("priority", "work", "monitor", "suppress")


def _mca_lead_account_filter():
    """Business accounts that qualify as MCA funder leads."""
    return BusinessAccount.mca_funder_count >= MCA_LEAD_MIN_FUNDERS


async def count_mca_lead_accounts(*, state: str | None = None) -> int:
    """Count accounts with at least one MCA funder on linked filings."""
    async with get_session() as session:
        stmt = select(func.count(BusinessAccount.id)).where(_mca_lead_account_filter())
        if state and state.strip():
            stmt = stmt.where(BusinessAccount.state == state.strip().upper())
        return (await session.execute(stmt)).scalar_one()


async def get_dashboard_stats() -> dict:
    """Fetch high-level pipeline statistics for the dashboard."""
    async with get_session() as session:
        total = await _count_where(session, BusinessAccount, _mca_lead_account_filter())
        enriched = await _count_where(session, Lead, Lead.enrichment_status == "complete")
        cleared = await _count_where(session, Lead, Lead.compliance_status == "cleared")
        exported = await _count_where(session, Lead, Lead.export_status == "exported")
        blocked = await _count_where(session, Lead, Lead.compliance_status.like("blocked:%"))
        filing_leads = await _count(session, Lead)

    state_coverage = await get_state_filing_lead_stats()

    return {
        "total_leads": total,
        "filing_leads": filing_leads,
        "enriched_leads": enriched,
        "cleared_leads": cleared,
        "exported_leads": exported,
        "blocked_leads": blocked,
        "state_coverage": state_coverage,
    }


async def get_state_filing_lead_stats() -> list[dict]:
    """Per state: stored UCC filing count, lead count, and scraper run flag."""
    async with get_session() as session:
        filing_rows = await session.execute(
            select(UCCFiling.state, func.count(UCCFiling.id)).group_by(UCCFiling.state)
        )
        lead_rows = await session.execute(
            select(BusinessAccount.state, func.count(BusinessAccount.id))
            .where(_mca_lead_account_filter())
            .group_by(BusinessAccount.state)
        )
        run_states_result = await session.execute(select(ScraperRun.state).distinct())

    filings_by_state = {row[0]: int(row[1]) for row in filing_rows.all()}
    leads_by_state = {row[0]: int(row[1]) for row in lead_rows.all()}
    scraper_states = {row[0] for row in run_states_result.all()}

    from app.scrapers.registry import get_tier1_state_codes, registry_readiness

    all_states = sorted(
        set(get_tier1_state_codes())
        | set(filings_by_state)
        | set(leads_by_state)
        | scraper_states
    )
    return [
        {
            "state": code,
            "filings": filings_by_state.get(code, 0),
            "leads": leads_by_state.get(code, 0),
            "scraper_run": code in scraper_states,
            "readiness": registry_readiness(code),
        }
        for code in all_states
    ]


async def get_scraper_status() -> list[dict]:
    """Latest scraper run per state; Tier 1 always listed with readiness."""
    from app.scrapers.registry import get_tier1_state_codes, registry_readiness

    async with get_session() as session:
        subq = (
            select(
                ScraperRun.state,
                func.max(ScraperRun.started_at).label("last_run"),
            )
            .group_by(ScraperRun.state)
            .subquery()
        )
        result = await session.execute(
            select(ScraperRun)
            .join(
                subq,
                (ScraperRun.state == subq.c.state)
                & (ScraperRun.started_at == subq.c.last_run),
            )
            .order_by(ScraperRun.state)
        )
        runs = {r.state: r for r in result.scalars().all()}

    tier1 = get_tier1_state_codes()
    other_states = sorted(set(runs) - set(tier1))
    ordered = tier1 + other_states

    rows: list[dict] = []
    for code in ordered:
        readiness = registry_readiness(code)
        r = runs.get(code)
        if r is not None:
            rows.append(
                {
                    "state": code,
                    "status": r.status,
                    "records_found": r.records_found or 0,
                    "last_run": r.started_at.isoformat() if r.started_at else "never",
                    "filings_url": f"/dashboard/filings?state={code}",
                    "readiness": readiness,
                    "runnable": readiness in ("ready", "playwright") if readiness else True,
                }
            )
        elif readiness:
            rows.append(
                {
                    "state": code,
                    "status": "not_implemented",
                    "records_found": 0,
                    "last_run": "never",
                    "filings_url": f"/dashboard/filings?state={code}",
                    "readiness": readiness,
                    "runnable": readiness in ("ready", "playwright"),
                }
            )
    return rows


async def get_recent_scraper_runs(limit: int = 10) -> list[dict]:
    """Most recent scraper runs across all states."""
    async with get_session() as session:
        result = await session.execute(
            select(ScraperRun)
            .order_by(ScraperRun.started_at.desc())
            .limit(limit)
        )
        runs = result.scalars().all()

    return [
        {
            "state": r.state,
            "status": r.status,
            "records_found": r.records_found or 0,
            "started_at": r.started_at.isoformat() if r.started_at else "",
            "finished_at": r.finished_at.isoformat() if r.finished_at else "",
            "filings_url": f"/dashboard/filings?state={r.state}",
        }
        for r in runs
    ]


async def get_recent_alerts(limit: int = 20) -> list[dict]:
    """Fetch recent pipeline events for the alerts view."""
    async with get_session() as session:
        result = await session.execute(
            select(PipelineEvent)
            .order_by(PipelineEvent.created_at.desc())
            .limit(limit)
        )
        events = result.scalars().all()

    return [
        {
            "type": e.event_type,
            "component": e.component,
            "detail": e.detail,
            "time": e.created_at.isoformat() if e.created_at else "",
        }
        for e in events
    ]


def _ilike(column, value: str | None):
    """Partial match filter; no-op when value is empty."""
    if not value or not value.strip():
        return None
    return column.ilike(f"%{value.strip()}%")


def _is_mca_filing(filing: UCCFiling) -> bool:
    return filing.lender_class == "mca_funder" or filing.is_mca is True


def _account_lead_row_dict(account: BusinessAccount) -> dict:
    """Serialize an MCA funder business account for the leads browse table."""
    return {
        "id": account.id,
        "debtor_name": account.display_name,
        "state": account.state,
        "mca_funder_count": account.mca_funder_count,
        "consolidation_score": account.consolidation_score,
        "consolidation_tier": account.consolidation_tier or "",
        "days_since_last_filing": account.days_since_last_filing,
        "account_url": f"/dashboard/accounts/{account.id}",
        "detail_url": f"/dashboard/leads/accounts/{account.id}/detail",
        "filings_url": f"/dashboard/filings?state={account.state}&debtor_name={account.display_name}",
    }


async def _mca_funders_for_account(session, account_id: int) -> list[dict]:
    """Distinct MCA secured parties on an account's filings."""
    result = await session.execute(
        select(UCCFiling).where(UCCFiling.account_id == account_id)
    )
    seen: set[str] = set()
    funders: list[dict] = []
    for filing in result.scalars().all():
        if not _is_mca_filing(filing):
            continue
        sp = (filing.secured_party or "").strip()
        key = sp[:120].lower() if sp else f"filing-{filing.id}"
        if key in seen:
            continue
        seen.add(key)
        funders.append(
            {
                "secured_party": sp or "—",
                "lender_class": filing.lender_class or "unknown",
                "is_mca": filing.is_mca,
                "filing_number": filing.filing_number,
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else "",
            }
        )
    return funders


async def search_filings(
    *,
    state: str | None = None,
    debtor_name: str | None = None,
    secured_party: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated UCC filings browse with optional filters and lead links."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conditions = []
    if state and state.strip():
        conditions.append(UCCFiling.state == state.strip().upper())
    debtor_filt = _ilike(UCCFiling.debtor_name, debtor_name)
    if debtor_filt is not None:
        conditions.append(debtor_filt)
    secured_filt = _ilike(UCCFiling.secured_party, secured_party)
    if secured_filt is not None:
        conditions.append(secured_filt)

    LeadByFiling = aliased(Lead)

    async with get_session() as session:
        count_stmt = select(func.count(UCCFiling.id))
        data_stmt = (
            select(UCCFiling, LeadByFiling)
            .outerjoin(LeadByFiling, LeadByFiling.source_filing_id == UCCFiling.id)
            .order_by(UCCFiling.scraped_at.desc())
        )
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            data_stmt = data_stmt.where(cond)

        total = (await session.execute(count_stmt)).scalar_one()
        rows = (await session.execute(data_stmt.limit(limit).offset(offset))).all()

    filings = []
    for filing, lead in rows:
        filings.append(
            {
                "id": filing.id,
                "filing_number": filing.filing_number,
                "state": filing.state,
                "debtor_name": filing.debtor_name,
                "secured_party": filing.secured_party or "",
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else "",
                "scraped_at": filing.scraped_at.isoformat() if filing.scraped_at else "",
                "is_mca": filing.is_mca,
                "lead_id": lead.id if lead else None,
                "lead_tier": lead.mca_tier if lead else None,
                "lead_url": f"/dashboard/leads?state={filing.state}&debtor_name={filing.debtor_name}"
                if lead
                else None,
            }
        )

    return {
        "filings": filings,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def get_mca_lead_detail(account_id: int) -> dict | None:
    """MCA funder account with distinct funders from linked filings."""
    async with get_session() as session:
        account = await session.get(BusinessAccount, account_id)
        if account is None or account.mca_funder_count < MCA_LEAD_MIN_FUNDERS:
            return None
        funders = await _mca_funders_for_account(session, account_id)
    row = _account_lead_row_dict(account)
    row["mca_funders"] = funders
    return row


async def search_leads(
    *,
    state: str | None = None,
    debtor_name: str | None = None,
    tier: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated MCA funder accounts (primary operator leads queue)."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conditions = [_mca_lead_account_filter()]
    if state and state.strip():
        conditions.append(BusinessAccount.state == state.strip().upper())
    debtor_filt = _ilike(BusinessAccount.display_name, debtor_name)
    if debtor_filt is not None:
        conditions.append(debtor_filt)
    tier_val = (tier or "").strip().lower()
    if tier_val in CONSOLIDATION_TIERS:
        conditions.append(BusinessAccount.consolidation_tier == tier_val)

    async with get_session() as session:
        count_stmt = select(func.count(BusinessAccount.id))
        data_stmt = select(BusinessAccount).order_by(
            BusinessAccount.consolidation_score.desc().nulls_last(),
            BusinessAccount.mca_funder_count.desc(),
            BusinessAccount.id.desc(),
        )
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            data_stmt = data_stmt.where(cond)

        total = (await session.execute(count_stmt)).scalar_one()
        rows = (await session.execute(data_stmt.limit(limit).offset(offset))).scalars().all()

    return {
        "leads": [_account_lead_row_dict(a) for a in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def list_mca_aliases(
    *,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Paginated ``mca_aliases`` rows for lender management UI."""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    conditions = []
    q = _ilike(MCAlias.alias_name, search)
    if q is not None:
        conditions.append(q)

    async with get_session() as session:
        count_stmt = select(func.count(MCAlias.id))
        data_stmt = select(MCAlias).order_by(MCAlias.alias_name)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            data_stmt = data_stmt.where(cond)
        total = (await session.execute(count_stmt)).scalar_one()
        rows = (await session.execute(data_stmt.limit(limit).offset(offset))).scalars().all()

    return {
        "aliases": [
            {
                "id": r.id,
                "alias_name": r.alias_name,
                "canonical_lender_name": r.canonical_lender_name,
                "lender_class": r.lender_class or "mca_funder",
                "consolidation_weight": r.consolidation_weight,
                "confidence": r.confidence,
                "source": r.source or "",
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def upsert_mca_alias(
    *,
    alias_name: str,
    canonical_lender_name: str,
    lender_class: str = "mca_funder",
    consolidation_weight: float | None = None,
    confidence: float = 1.0,
    source: str = "dashboard",
) -> MCAlias:
    """Insert or update an MCA alias by normalized alias name."""
    from app.mca.names import normalize_name

    key = normalize_name(alias_name)
    async with get_session() as session:
        existing = (
            await session.execute(select(MCAlias).where(MCAlias.alias_name == alias_name.strip()))
        ).scalar_one_or_none()
        if existing is None:
            by_norm = (
                await session.execute(select(MCAlias))
            ).scalars().all()
            for row in by_norm:
                if normalize_name(row.alias_name) == key:
                    existing = row
                    break
        if existing:
            existing.alias_name = alias_name.strip()
            existing.canonical_lender_name = canonical_lender_name.strip()
            existing.lender_class = lender_class or "mca_funder"
            existing.consolidation_weight = consolidation_weight
            existing.confidence = confidence
            existing.source = source
            return existing
        row = MCAlias(
            alias_name=alias_name.strip(),
            canonical_lender_name=canonical_lender_name.strip(),
            lender_class=lender_class or "mca_funder",
            consolidation_weight=consolidation_weight,
            confidence=confidence,
            source=source,
        )
        session.add(row)
        return row


async def _count(session, model) -> int:
    result = await session.execute(select(func.count(model.id)))
    return result.scalar_one()


async def _count_where(session, model, condition) -> int:
    result = await session.execute(select(func.count(model.id)).where(condition))
    return result.scalar_one()


async def get_last_fl_scraper_finished_at() -> datetime | None:
    """Latest completed FL scraper run ``finished_at``."""
    async with get_session() as session:
        row = (
            await session.execute(
                select(ScraperRun.finished_at)
                .where(
                    ScraperRun.state == "FL",
                    ScraperRun.status == "completed",
                    ScraperRun.finished_at.is_not(None),
                )
                .order_by(ScraperRun.finished_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    return row


async def search_accounts(
    *,
    state: str = "FL",
    tier: str | None = None,
    since_last_run: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Paginated business accounts sorted by consolidation score."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conditions = [BusinessAccount.state == (state or "FL").strip().upper()]
    tier_val = (tier or "").strip().lower()
    if tier_val in CONSOLIDATION_TIERS:
        conditions.append(BusinessAccount.consolidation_tier == tier_val)

    last_run = await get_last_fl_scraper_finished_at() if since_last_run else None
    if last_run is not None:
        from sqlalchemy import or_

        conditions.append(
            or_(
                BusinessAccount.last_event_at > last_run,
                BusinessAccount.updated_at > last_run,
            )
        )

    async with get_session() as session:
        count_stmt = select(func.count(BusinessAccount.id))
        data_stmt = select(BusinessAccount).order_by(
            BusinessAccount.consolidation_score.desc().nulls_last(),
            BusinessAccount.id.desc(),
        )
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
            data_stmt = data_stmt.where(cond)
        total = (await session.execute(count_stmt)).scalar_one()
        rows = (await session.execute(data_stmt.limit(limit).offset(offset))).scalars().all()

    return {
        "accounts": [
            {
                "id": a.id,
                "display_name": a.display_name,
                "state": a.state,
                "consolidation_score": a.consolidation_score,
                "consolidation_tier": a.consolidation_tier or "",
                "mca_funder_count": a.mca_funder_count,
                "material_ucc_count": a.material_ucc_count,
                "days_since_last_filing": a.days_since_last_filing,
                "last_event_at": a.last_event_at.isoformat() if a.last_event_at else "",
                "detail_url": f"/dashboard/accounts/{a.id}",
                "filings_url": f"/dashboard/filings?state={a.state}&debtor_name={a.display_name}",
            }
            for a in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "since_last_run": since_last_run,
        "last_fl_run_at": last_run.isoformat() if last_run else None,
    }


async def get_account_detail(account_id: int) -> dict | None:
    """Account with score breakdown and related filings."""
    async with get_session() as session:
        account = await session.get(BusinessAccount, account_id)
        if account is None:
            return None
        filings_result = await session.execute(
            select(UCCFiling)
            .where(UCCFiling.account_id == account_id)
            .order_by(UCCFiling.filing_date.desc().nulls_last(), UCCFiling.id.desc())
        )
        filings = list(filings_result.scalars().all())
        lead_rows = await session.execute(
            select(Lead).where(
                Lead.debtor_name_normalized == account.debtor_name_normalized,
                Lead.state == account.state,
            )
        )
        leads = list(lead_rows.scalars().all())

    filing_items = [
        {
            "id": f.id,
            "filing_number": f.filing_number,
            "filing_date": f.filing_date.isoformat() if f.filing_date else "",
            "secured_party": f.secured_party or "",
            "lender_class": f.lender_class or "unknown",
            "is_mca": f.is_mca,
        }
        for f in filings
    ]
    return {
        "id": account.id,
        "display_name": account.display_name,
        "state": account.state,
        "consolidation_score": account.consolidation_score,
        "consolidation_tier": account.consolidation_tier or "",
        "score_components": account.score_components or {},
        "mca_funder_count": account.mca_funder_count,
        "material_ucc_count": account.material_ucc_count,
        "days_since_last_filing": account.days_since_last_filing,
        "last_event_at": account.last_event_at.isoformat() if account.last_event_at else "",
        "last_scored_at": account.last_scored_at.isoformat() if account.last_scored_at else "",
        "filings": filing_items,
        "leads": [
            {
                "id": l.id,
                "lead_score": l.lead_score,
                "mca_tier": l.mca_tier or "",
                "url": f"/dashboard/leads?state={l.state}&debtor_name={l.debtor_name}",
            }
            for l in leads
        ],
    }
