"""Post-scrape consolidation pipeline for Florida (and future states)."""

from app.consolidation.rollup import classify_filings, rescore_accounts, rollup_accounts
from app.logging import get_logger
from app.mca.pipeline import run_mca_pipeline

logger = get_logger("consolidation_pipeline")


async def run_post_scrape_pipeline(state: str = "FL", *, run_mca: bool = True) -> dict:
    """Classify filings → rollup accounts → rescore → optional MCA leads."""
    classified = 0
    while True:
        batch = await classify_filings(state, batch_size=500)
        classified += batch
        if batch < 500:
            break

    accounts = await rollup_accounts(state)
    rescored = await rescore_accounts(state)
    leads = 0
    if run_mca:
        while True:
            processed, batch_leads = await run_mca_pipeline(batch_size=500)
            leads += batch_leads
            if processed == 0:
                break

    summary = {
        "state": state,
        "filings_classified": classified,
        "accounts_rolled_up": accounts,
        "accounts_rescored": rescored,
        "mca_leads_created": leads,
    }
    logger.info("post_scrape_pipeline_complete", **summary)
    return summary
