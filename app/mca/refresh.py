"""Reclassify filings and refresh account MCA counts after alias changes."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.consolidation.classifier import (
    classify_secured_party,
    load_alias_lender_classes,
    reset_alias_class_cache,
)
from app.consolidation.rollup import classify_filings, rescore_accounts, rollup_accounts
from app.db import get_session
from app.mca.detector import detect_mca
from app.mca.pipeline import run_mca_pipeline
from app.models.filing import UCCFiling
from app.models.lead import Lead


async def refresh_mca_classification(state: str = "FL") -> dict:
    """Re-run lender classification, MCA detection, rollup, and optional lead sync.

    Idempotent for the given state. Updates ``lender_class`` / ``is_mca`` on filings,
    rolls up ``business_accounts`` (including ``mca_funder_count``), and runs the MCA
    pipeline for any unprocessed filings.
    """
    state = state.strip().upper()
    reset_alias_class_cache()
    alias_classes = await load_alias_lender_classes()

    reclassified = 0
    cleared_mca = 0
    async with get_session() as session:
        result = await session.execute(select(UCCFiling).where(UCCFiling.state == state))
        filings = list(result.scalars().all())
        for filing in filings:
            filing.lender_class = classify_secured_party(
                filing.secured_party, alias_classes
            )
            is_mca, _, _, _ = await detect_mca(
                filing.secured_party,
                filing.collateral_description,
                alias_class_map=alias_classes,
            )
            if filing.is_mca and not is_mca:
                filing.is_mca = False
                cleared_mca += 1
            elif is_mca:
                filing.is_mca = True
            reclassified += 1

    removed_leads = 0
    async with get_session() as session:
        lead_rows = await session.execute(
            select(Lead, UCCFiling)
            .join(UCCFiling, Lead.source_filing_id == UCCFiling.id)
            .where(Lead.state == state)
        )
        invalid_ids: list[int] = []
        for lead, filing in lead_rows.all():
            is_mca, _, _, _ = await detect_mca(
                filing.secured_party,
                filing.collateral_description,
                alias_class_map=alias_classes,
            )
            if not is_mca:
                invalid_ids.append(lead.id)
                filing.is_mca = False

        if invalid_ids:
            await session.execute(delete(Lead).where(Lead.id.in_(invalid_ids)))
            removed_leads = len(invalid_ids)

    while True:
        batch = await classify_filings(state, batch_size=500)
        if batch < 500:
            break

    accounts = await rollup_accounts(state)
    rescored = await rescore_accounts(state)

    leads_created = 0
    while True:
        processed, batch_leads = await run_mca_pipeline(batch_size=200)
        leads_created += batch_leads
        if processed == 0:
            break

    return {
        "state": state,
        "filings_reclassified": reclassified,
        "is_mca_cleared": cleared_mca,
        "invalid_leads_removed": removed_leads,
        "accounts_rolled_up": accounts,
        "accounts_rescored": rescored,
        "new_filing_leads": leads_created,
    }
