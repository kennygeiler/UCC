"""Self-improving MCA alias updater — nightly pattern analysis job.

Analyzes secured_party names from recent filings, identifies patterns
from successful leads, and adds new aliases with appropriate confidence.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import get_session
from app.logging import get_logger
from app.mca.detector import normalize_name
from app.mca.seed_data import SHELL_COMPANY_PATTERNS
from app.models.filing import UCCFiling
from app.models.lead import Lead
from app.models.mca_alias import MCAlias

logger = get_logger("alias_updater")


async def get_recent_secured_parties(days: int = 30) -> list[str]:
    """Fetch distinct secured party names from recent filings.

    Args:
        days: Look-back window in days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling.secured_party)
            .where(UCCFiling.scraped_at >= cutoff)
            .where(UCCFiling.secured_party.isnot(None))
            .distinct()
        )
        return [row[0] for row in result.all()]


async def get_existing_aliases() -> set[str]:
    """Load all normalized alias names currently in the database."""
    async with get_session() as session:
        result = await session.execute(select(MCAlias.alias_name))
        return {normalize_name(row[0]) for row in result.all()}


async def find_high_converting_parties() -> list[str]:
    """Find secured party names associated with hot leads (state-safe join).

    Returns:
        List of secured party names linked to high-scoring leads.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling.secured_party)
            .join(
                Lead,
                (UCCFiling.debtor_name == Lead.debtor_name)
                & (UCCFiling.state == Lead.state),
            )
            .where(Lead.lead_score >= 30.0)
            .where(UCCFiling.secured_party.isnot(None))
            .distinct()
        )
        return [row[0] for row in result.all()]


async def run_alias_update() -> int:
    """Execute the nightly alias update job.

    Uses INSERT ... ON CONFLICT DO NOTHING for idempotent inserts.

    Returns:
        Number of new aliases attempted (rows skipped on conflict do not raise).
    """
    existing = await get_existing_aliases()
    high_converting = await find_high_converting_parties()
    inserted = 0

    async with get_session() as session:
        for party_name in high_converting:
            normalized = normalize_name(party_name)
            if normalized in existing or len(normalized) <= 2:
                continue
            stmt = (
                insert(MCAlias)
                .values(
                    alias_name=party_name,
                    canonical_lender_name=party_name,
                    confidence=0.8,
                    source="auto_updater",
                )
                .on_conflict_do_nothing(index_elements=["alias_name"])
            )
            result = await session.execute(stmt)
            rc = getattr(result, "rowcount", None) or 0
            if rc > 0:
                inserted += 1
            existing.add(normalized)

    logger.info("alias_update_complete", new_aliases_inserted=inserted)
    return inserted


async def run_alias_update_job() -> None:
    """APScheduler entrypoint: run alias update and log outcome (never crashes scheduler)."""
    try:
        n = await run_alias_update()
        logger.info(
            "alias_update_job_complete",
            component="alias_updater",
            status="ok",
            new_aliases=n,
        )
    except Exception as exc:
        logger.error(
            "alias_update_job_failed",
            component="alias_updater",
            status="failed",
            error_type=type(exc).__name__,
            context=str(exc)[:500],
        )
