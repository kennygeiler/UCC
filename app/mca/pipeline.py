"""MCA detection pipeline — wires scraper output to detector and scorer.

Processes new UCC filings through MCA detection and lead scoring,
producing scored lead records ready for enrichment.
"""

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.mca.detector import (
    check_collateral_keywords,
    detect_mca,
    load_alias_map,
    normalize_name,
)
from app.mca.scorer import score_lead
from app.models.filing import UCCFiling
from app.models.lead import Lead

logger = get_logger("mca_pipeline")


async def get_unprocessed_filings(batch_size: int = 100) -> list[UCCFiling]:
    """Fetch filings not yet run through MCA detection (``is_mca`` still null)."""
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling).where(UCCFiling.is_mca.is_(None)).limit(batch_size)
        )
        return list(result.scalars().all())


async def process_filing(filing: UCCFiling) -> Lead | None:
    """Process a single UCC filing through detection and scoring.

    Idempotent: if a lead already exists for ``filing.id``, returns that lead.
    """
    async with get_session() as session:
        existing = await session.execute(
            select(Lead).where(Lead.source_filing_id == filing.id)
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            return prior

    from app.consolidation.classifier import load_alias_lender_classes

    return await _process_filing_with_maps(
        filing,
        alias_map=await load_alias_map(),
        alias_class_map=await load_alias_lender_classes(),
    )


async def run_mca_pipeline(batch_size: int = 100) -> tuple[int, int]:
    """Process a batch of unanalyzed filings through MCA pipeline.

    Returns:
        (filings_processed, leads_created)
    """
    from app.consolidation.classifier import load_alias_lender_classes

    filings = await get_unprocessed_filings(batch_size)
    if not filings:
        return 0, 0

    alias_map = await load_alias_map()
    alias_class_map = await load_alias_lender_classes()
    leads_created = 0

    for filing in filings:
        lead = await _process_filing_with_maps(
            filing, alias_map=alias_map, alias_class_map=alias_class_map
        )
        if lead:
            leads_created += 1

    logger.info("mca_pipeline_run_complete", processed=len(filings), leads=leads_created)
    return len(filings), leads_created


async def _process_filing_with_maps(
    filing: UCCFiling,
    *,
    alias_map: dict[str, tuple[str, float]],
    alias_class_map: dict[str, str] | None,
) -> Lead | None:
    """Like :func:`process_filing` but reuses preloaded alias maps."""
    async with get_session() as session:
        existing = await session.execute(
            select(Lead).where(Lead.source_filing_id == filing.id)
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            row = await session.get(UCCFiling, filing.id)
            if row is not None and row.is_mca is None:
                row.is_mca = True
            return prior

    is_mca, canonical_lender, confidence, match_type = await detect_mca(
        filing.secured_party,
        filing.collateral_description,
        alias_map=alias_map,
        alias_class_map=alias_class_map,
    )
    if not is_mca:
        async with get_session() as session:
            row = await session.get(UCCFiling, filing.id)
            if row is not None:
                row.is_mca = False
        return None

    async with get_session() as session:
        row = await session.get(UCCFiling, filing.id)
        if row is not None:
            row.is_mca = True

    has_mca_collateral = check_collateral_keywords(filing.collateral_description)
    scoring = await score_lead(
        filing.debtor_name,
        filing.state,
        filing.filing_date,
        has_mca_collateral,
        mca_match_confidence=confidence,
        mca_match_type=match_type,
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
            mca_match_type=match_type,
            mca_lender_canonical=canonical_lender,
            mca_match_confidence=confidence,
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
        match_type=match_type,
    )
    return lead
