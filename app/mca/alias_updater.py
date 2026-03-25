"""Self-improving MCA alias updater — nightly pattern analysis job.

Analyzes secured_party names from recent filings, identifies patterns
from successful leads, and adds new aliases with appropriate confidence.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

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
    """Find secured party names associated with hot leads.

    Returns:
        List of secured party names linked to high-scoring leads.
    """
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling.secured_party)
            .join(Lead, UCCFiling.debtor_name == Lead.debtor_name)
            .where(Lead.lead_score >= 30.0)
            .where(UCCFiling.secured_party.isnot(None))
            .distinct()
        )
        return [row[0] for row in result.all()]


async def run_alias_update() -> int:
    """Execute the nightly alias update job.

    Returns:
        Number of new aliases added.
    """
    existing = await get_existing_aliases()
    high_converting = await find_high_converting_parties()
    added = 0

    async with get_session() as session:
        for party_name in high_converting:
            normalized = normalize_name(party_name)
            if normalized not in existing and len(normalized) > 2:
                alias = MCAlias(
                    alias_name=party_name,
                    canonical_lender_name=party_name,
                    confidence=0.8,
                    source="auto_updater",
                )
                session.add(alias)
                existing.add(normalized)
                added += 1

    logger.info("alias_update_complete", new_aliases=added)
    return added
