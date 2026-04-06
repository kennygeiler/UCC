"""MCA detection pipeline — wires scraper output to detector and scorer.

Processes new UCC filings through MCA detection and lead scoring,
producing scored lead records ready for enrichment.
"""

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.mca.detector import check_collateral_keywords, detect_mca, normalize_name
from app.mca.scorer import score_lead
from app.models.filing import UCCFiling
from app.models.lead import Lead

logger = get_logger("mca_pipeline")


async def get_unprocessed_filings(batch_size: int = 100) -> list[UCCFiling]:
    """Fetch filings that haven't been analyzed for MCA yet (per filing id).

    Args:
        batch_size: Maximum number of filings to process per batch.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling)
            .outerjoin(Lead, Lead.source_filing_id == UCCFiling.id)
            .where(Lead.id.is_(None))
            .limit(batch_size)
        )
        return list(result.scalars().all())


async def process_filing(filing: UCCFiling) -> Lead | None:
    """Process a single UCC filing through detection and scoring.

    Idempotent: if a lead already exists for ``filing.id``, returns that lead.

    Args:
        filing: UCC filing record to analyze.

    Returns:
        Created Lead if MCA detected, None otherwise.
    """
    async with get_session() as session:
        existing = await session.execute(
            select(Lead).where(Lead.source_filing_id == filing.id)
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            return prior

    is_mca, _canonical_lender, _confidence = await detect_mca(
        filing.secured_party, filing.collateral_description
    )
    if not is_mca:
        return None

    has_mca_collateral = check_collateral_keywords(filing.collateral_description)
    scoring = await score_lead(
        filing.debtor_name, filing.state, filing.filing_date, has_mca_collateral
    )

    debtor_key = normalize_name(filing.debtor_name)

    async with get_session() as session:
        lead = Lead(
            debtor_name=filing.debtor_name,
            debtor_name_normalized=debtor_key,
            state=filing.state,
            lead_score=scoring["lead_score"],
            mca_position_count=scoring["mca_position_count"],
            mca_tier=scoring["tier"],
            source_filing_id=filing.id,
            enrichment_status="pending",
            compliance_status="pending",
            export_status="pending",
        )
        session.add(lead)
        await session.flush()
        lead_id = lead.id

    logger.info(
        "lead_created",
        lead_id=lead_id,
        debtor=filing.debtor_name,
        tier=scoring["tier"],
        score=scoring["lead_score"],
    )
    return lead


async def run_mca_pipeline(batch_size: int = 100) -> int:
    """Process a batch of unanalyzed filings through MCA pipeline.

    Args:
        batch_size: Max filings to process per run.

    Returns:
        Number of new leads created.
    """
    filings = await get_unprocessed_filings(batch_size)
    leads_created = 0

    for filing in filings:
        lead = await process_filing(filing)
        if lead:
            leads_created += 1

    logger.info("mca_pipeline_run_complete", processed=len(filings), leads=leads_created)
    return leads_created
