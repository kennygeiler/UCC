#!/usr/bin/env python3
"""Re-score existing leads with Better B MCA scoring and persisted match fields."""

import asyncio
import sys

from sqlalchemy import select

from app.db import get_session
from app.logging import configure_logging, get_logger
from app.mca.detector import check_collateral_keywords, detect_mca
from app.mca.scorer import score_lead
from app.models.filing import UCCFiling
from app.models.lead import Lead

logger = get_logger("rescore_leads")


async def _apply_detection(lead: Lead, filing: UCCFiling) -> tuple[float, str | None, bool]:
    """Persist match fields on lead; mark filing MCA. Returns conf, type, has_collateral."""
    is_mca, canonical, confidence, match_type = await detect_mca(
        filing.secured_party, filing.collateral_description
    )
    if not is_mca:
        return confidence, match_type, False

    lead.mca_match_type = match_type
    lead.mca_lender_canonical = canonical
    lead.mca_match_confidence = confidence
    filing.is_mca = True
    has_collateral = check_collateral_keywords(filing.collateral_description)
    return confidence, match_type, has_collateral


async def main(state: str | None = None) -> int:
    """Re-score leads: commit is_mca flags first, then score in a second pass."""
    configure_logging()
    lead_ids: list[int] = []

    async with get_session() as session:
        stmt = select(Lead.id)
        if state:
            stmt = stmt.where(Lead.state == state.upper())
        lead_ids = list((await session.execute(stmt)).scalars().all())

    # Pass 1: detection + is_mca flags (committed per lead)
    for lid in lead_ids:
        async with get_session() as session:
            lead_row = await session.get(Lead, lid)
            if lead_row is None or not lead_row.source_filing_id:
                continue
            filing = await session.get(UCCFiling, lead_row.source_filing_id)
            if filing is None:
                continue
            if lead_row.mca_match_type is None:
                await _apply_detection(lead_row, filing)
            else:
                filing.is_mca = True

    # Pass 2: scoring (is_mca visible after pass 1 commits)
    updated = 0
    for lid in lead_ids:
        async with get_session() as session:
            lead_row = await session.get(Lead, lid)
            if lead_row is None:
                continue
            filing = None
            if lead_row.source_filing_id:
                filing = await session.get(UCCFiling, lead_row.source_filing_id)
            confidence = lead_row.mca_match_confidence or 0.0
            match_type = lead_row.mca_match_type
            has_collateral = (
                check_collateral_keywords(filing.collateral_description) if filing else False
            )
            scoring = await score_lead(
                lead_row.debtor_name,
                lead_row.state,
                filing.filing_date if filing else None,
                has_collateral,
                mca_match_confidence=confidence,
                mca_match_type=match_type,
            )
            lead_row.lead_score = scoring["lead_score"]
            lead_row.mca_position_count = scoring["mca_position_count"]
            lead_row.mca_tier = scoring["tier"]
            updated += 1

    logger.info("rescore_complete", updated=updated, state=state or "ALL")
    return updated


if __name__ == "__main__":
    st = sys.argv[1].upper() if len(sys.argv) > 1 else None
    count = asyncio.run(main(st))
    print(f"Rescored {count} lead(s)" + (f" in {st}" if st else ""))
