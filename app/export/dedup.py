"""Lead deduplication — exact and fuzzy cross-state matching (C-10)."""

from difflib import SequenceMatcher

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.lead import Lead

logger = get_logger("dedup")


async def find_duplicate(debtor_name: str, state: str) -> Lead | None:
    """Check for an existing lead matching this debtor (exact or fuzzy).

    Args:
        debtor_name: Debtor name from the new filing.
        state: State code for the filing.

    Returns:
        Existing Lead if duplicate found, None otherwise.
    """
    exact = await _exact_match(debtor_name)
    if exact:
        return exact
    return await _fuzzy_match(debtor_name)


async def _exact_match(debtor_name: str) -> Lead | None:
    """Check for exact debtor name match across all states.

    Args:
        debtor_name: Name to match.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Lead).where(Lead.debtor_name == debtor_name).limit(1)
        )
        return result.scalar_one_or_none()


async def _fuzzy_match(debtor_name: str, threshold: float = 0.85) -> Lead | None:
    """Check for fuzzy name match across all states.

    Args:
        debtor_name: Name to match.
        threshold: Minimum similarity ratio (0.0-1.0).
    """
    async with get_session() as session:
        result = await session.execute(select(Lead).limit(500))
        leads = result.scalars().all()

    for lead in leads:
        ratio = SequenceMatcher(None, debtor_name.lower(), lead.debtor_name.lower()).ratio()
        if ratio >= threshold:
            logger.info("fuzzy_match", new=debtor_name, existing=lead.debtor_name, ratio=ratio)
            return lead
    return None
