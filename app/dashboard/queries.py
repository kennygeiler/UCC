"""Dashboard data queries — aggregations for the manager view."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import get_session
from app.models.filing import UCCFiling
from app.models.lead import Lead
from app.models.operations import PipelineEvent, ScraperRun


async def get_dashboard_stats() -> dict:
    """Fetch high-level pipeline statistics for the dashboard.

    Returns:
        Dict with lead counts, enrichment stats, compliance stats.
    """
    async with get_session() as session:
        total = await _count(session, Lead)
        enriched = await _count_where(session, Lead, Lead.enrichment_status == "complete")
        cleared = await _count_where(session, Lead, Lead.compliance_status == "cleared")
        exported = await _count_where(session, Lead, Lead.export_status == "exported")
        blocked = await _count_where(session, Lead, Lead.compliance_status.like("blocked:%"))

    state_coverage = await get_state_filing_lead_stats()

    return {
        "total_leads": total,
        "enriched_leads": enriched,
        "cleared_leads": cleared,
        "exported_leads": exported,
        "blocked_leads": blocked,
        "state_coverage": state_coverage,
    }


async def get_state_filing_lead_stats() -> list[dict]:
    """Per state: stored UCC filing count, lead count, and whether a scraper run occurred.

    Filings are rows in ``ucc_filings`` (cumulative ingested). Leads are rows in
    ``leads`` for that state. States appear if they have filings, leads, or any
    ``scraper_runs`` row.
    """
    async with get_session() as session:
        filing_rows = await session.execute(
            select(UCCFiling.state, func.count(UCCFiling.id)).group_by(UCCFiling.state)
        )
        lead_rows = await session.execute(
            select(Lead.state, func.count(Lead.id)).group_by(Lead.state)
        )
        run_states_result = await session.execute(select(ScraperRun.state).distinct())

    filings_by_state = {row[0]: int(row[1]) for row in filing_rows.all()}
    leads_by_state = {row[0]: int(row[1]) for row in lead_rows.all()}
    scraper_states = {row[0] for row in run_states_result.all()}

    all_states = sorted(set(filings_by_state) | set(leads_by_state) | scraper_states)
    return [
        {
            "state": code,
            "filings": filings_by_state.get(code, 0),
            "leads": leads_by_state.get(code, 0),
            "scraper_run": code in scraper_states,
        }
        for code in all_states
    ]


async def get_scraper_status() -> list[dict]:
    """Fetch latest scraper run status per state.

    Returns:
        List of dicts with state, status, records_found, last_run.
    """
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
            .join(subq, (ScraperRun.state == subq.c.state) & (ScraperRun.started_at == subq.c.last_run))
        )
        runs = result.scalars().all()

    return [
        {
            "state": r.state,
            "status": r.status,
            "records_found": r.records_found or 0,
            "last_run": r.started_at.isoformat() if r.started_at else "never",
        }
        for r in runs
    ]


async def get_recent_alerts(limit: int = 20) -> list[dict]:
    """Fetch recent pipeline events for the alerts view.

    Args:
        limit: Max number of events to return.
    """
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


async def _count(session, model) -> int:
    """Count all rows in a model table."""
    result = await session.execute(select(func.count(model.id)))
    return result.scalar_one()


async def _count_where(session, model, condition) -> int:
    """Count rows matching a condition."""
    result = await session.execute(select(func.count(model.id)).where(condition))
    return result.scalar_one()
