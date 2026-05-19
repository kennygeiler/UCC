"""Florida-scoped database reset — idempotent, transactional, FK-safe."""

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

FL_STATE = "FL"


@dataclass(frozen=True)
class ResetCounts:
    """Row counts affected by :func:`reset_fl_data`."""

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


def _fl_lead_filter():
    """Leads tied to FL filings or tagged FL."""
    fl_filing_ids = select(UCCFiling.id).where(UCCFiling.state == FL_STATE)
    return or_(Lead.state == FL_STATE, Lead.source_filing_id.in_(fl_filing_ids))


async def count_fl_scoped_rows(session: AsyncSession) -> ResetCounts:
    """Count rows that would be removed by :func:`reset_fl_data`."""
    lead_filter = _fl_lead_filter()
    fl_lead_ids = select(Lead.id).where(lead_filter)

    compliance = (
        await session.execute(
            select(func.count()).select_from(ComplianceCheck).where(
                ComplianceCheck.lead_id.in_(fl_lead_ids)
            )
        )
    ).scalar_one()

    retry = (
        await session.execute(
            select(func.count()).select_from(EnrichmentRetryQueue).where(
                EnrichmentRetryQueue.lead_id.in_(fl_lead_ids)
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
            .where(BusinessAccount.state == FL_STATE)
        )
    ).scalar_one()

    filings = (
        await session.execute(
            select(func.count()).select_from(UCCFiling).where(UCCFiling.state == FL_STATE)
        )
    ).scalar_one()

    runs = (
        await session.execute(
            select(func.count()).select_from(ScraperRun).where(ScraperRun.state == FL_STATE)
        )
    ).scalar_one()

    checkpoints = (
        await session.execute(
            select(func.count())
            .select_from(ScraperCheckpoint)
            .where(ScraperCheckpoint.state == FL_STATE)
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


async def reset_fl_data(*, dry_run: bool = False) -> ResetCounts:
    """Clear Florida pipeline data in FK-safe order.

    Does not touch other states, schema, or global tables (aliases, DNC, etc.).
    Idempotent: second run deletes zero rows when FL is already empty.
    """
    async with get_session() as session:
        before = await count_fl_scoped_rows(session)
        if dry_run:
            return before

        lead_filter = _fl_lead_filter()
        fl_lead_ids = select(Lead.id).where(lead_filter)

        await session.execute(
            delete(ComplianceCheck).where(ComplianceCheck.lead_id.in_(fl_lead_ids))
        )
        await session.execute(
            delete(EnrichmentRetryQueue).where(
                EnrichmentRetryQueue.lead_id.in_(fl_lead_ids)
            )
        )
        await session.execute(delete(Lead).where(lead_filter))
        await session.execute(
            delete(BusinessAccount).where(BusinessAccount.state == FL_STATE)
        )
        await session.execute(delete(UCCFiling).where(UCCFiling.state == FL_STATE))
        await session.execute(delete(ScraperRun).where(ScraperRun.state == FL_STATE))
        await session.execute(
            delete(ScraperCheckpoint).where(ScraperCheckpoint.state == FL_STATE)
        )

    return before
