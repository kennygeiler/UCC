"""State-scoped database reset — idempotent, transactional, FK-safe."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.account import BusinessAccount, ScraperCheckpoint
from app.models.dnc import ComplianceCheck
from app.models.filing import UCCFiling
from app.models.job import EnrichmentRetryQueue
from app.models.lead import Lead
from app.models.operations import ScraperRun


@dataclass(frozen=True)
class ResetCounts:
    """Row counts affected by :func:`reset_state_data`."""

    compliance_checks: int = 0
    enrichment_retry_queue: int = 0
    leads: int = 0
    business_accounts: int = 0
    ucc_filings: int = 0
    scraper_runs: int = 0
    scraper_checkpoints: int = 0

    @property
    def total(self) -> int:
        return (
            self.compliance_checks
            + self.enrichment_retry_queue
            + self.leads
            + self.business_accounts
            + self.ucc_filings
            + self.scraper_runs
            + self.scraper_checkpoints
        )


def _state_lead_filter(state_code: str):
    """Leads tied to state filings or tagged with state."""
    state = state_code.strip().upper()
    filing_ids = select(UCCFiling.id).where(UCCFiling.state == state)
    return or_(Lead.state == state, Lead.source_filing_id.in_(filing_ids))


async def count_state_scoped_rows(session: AsyncSession, state_code: str) -> ResetCounts:
    """Count rows that would be removed by :func:`reset_state_data`."""
    state = state_code.strip().upper()
    lead_filter = _state_lead_filter(state)
    state_lead_ids = select(Lead.id).where(lead_filter)

    compliance = (
        await session.execute(
            select(func.count()).select_from(ComplianceCheck).where(
                ComplianceCheck.lead_id.in_(state_lead_ids)
            )
        )
    ).scalar_one()

    retry = (
        await session.execute(
            select(func.count()).select_from(EnrichmentRetryQueue).where(
                EnrichmentRetryQueue.lead_id.in_(state_lead_ids)
            )
        )
    ).scalar_one()

    leads = (
        await session.execute(select(func.count()).select_from(Lead).where(lead_filter))
    ).scalar_one()

    accounts = (
        await session.execute(
            select(func.count())
            .select_from(BusinessAccount)
            .where(BusinessAccount.state == state)
        )
    ).scalar_one()

    filings = (
        await session.execute(
            select(func.count()).select_from(UCCFiling).where(UCCFiling.state == state)
        )
    ).scalar_one()

    runs = (
        await session.execute(
            select(func.count()).select_from(ScraperRun).where(ScraperRun.state == state)
        )
    ).scalar_one()

    checkpoints = (
        await session.execute(
            select(func.count())
            .select_from(ScraperCheckpoint)
            .where(ScraperCheckpoint.state == state)
        )
    ).scalar_one()

    return ResetCounts(
        compliance_checks=compliance,
        enrichment_retry_queue=retry,
        leads=leads,
        business_accounts=accounts,
        ucc_filings=filings,
        scraper_runs=runs,
        scraper_checkpoints=checkpoints,
    )


async def reset_state_data(state_code: str, *, dry_run: bool = False) -> ResetCounts:
    """Clear pipeline data for one state in FK-safe order.

    Does not touch other states, schema, or global tables (aliases, DNC, etc.).
    """
    state = state_code.strip().upper()
    async with get_session() as session:
        before = await count_state_scoped_rows(session, state)
        if dry_run:
            return before

        lead_filter = _state_lead_filter(state)
        state_lead_ids = select(Lead.id).where(lead_filter)

        await session.execute(
            delete(ComplianceCheck).where(ComplianceCheck.lead_id.in_(state_lead_ids))
        )
        await session.execute(
            delete(EnrichmentRetryQueue).where(
                EnrichmentRetryQueue.lead_id.in_(state_lead_ids)
            )
        )
        await session.execute(delete(Lead).where(lead_filter))
        await session.execute(
            delete(BusinessAccount).where(BusinessAccount.state == state)
        )
        await session.execute(delete(UCCFiling).where(UCCFiling.state == state))
        await session.execute(delete(ScraperRun).where(ScraperRun.state == state))
        await session.execute(
            delete(ScraperCheckpoint).where(ScraperCheckpoint.state == state)
        )

    return before
