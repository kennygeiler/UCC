"""Lead scoring engine — scores leads by financial distress level.

Primary signal: position count (number of MCA liens per debtor).
Secondary: filing recency, collateral type.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import get_session
from app.logging import get_logger
from app.models.filing import UCCFiling
from app.models.lead import Lead

logger = get_logger("scorer")


async def count_positions(debtor_name: str, state: str) -> int:
    """Count total MCA filing positions for a debtor.

    Args:
        debtor_name: Canonical debtor name.
        state: State code for the filing.

    Returns:
        Number of distinct MCA filings for this debtor.
    """
    async with get_session() as session:
        result = await session.execute(
            select(func.count(UCCFiling.id)).where(
                UCCFiling.debtor_name == debtor_name,
                UCCFiling.state == state,
            )
        )
        return result.scalar_one()


def calculate_recency_boost(filing_date: datetime | None) -> float:
    """Calculate a recency boost for recent filings.

    Args:
        filing_date: Date of the UCC filing.

    Returns:
        Boost value (0.0 to 1.0).
    """
    if not filing_date:
        return 0.0
    age = datetime.now(timezone.utc) - filing_date
    if age < timedelta(days=30):
        return 1.0
    if age < timedelta(days=90):
        return 0.5
    if age < timedelta(days=180):
        return 0.25
    return 0.0


def assign_tier(position_count: int) -> str:
    """Assign lead tier based on position count.

    Args:
        position_count: Number of MCA liens for the debtor.

    Returns:
        Tier string: 'hot', 'warm', or 'cold'.
    """
    if position_count >= 3:
        return "hot"
    if position_count == 2:
        return "warm"
    return "cold"


def compute_score(
    position_count: int,
    recency_boost: float,
    has_mca_collateral: bool,
) -> float:
    """Compute the final lead score.

    Args:
        position_count: Number of MCA filing positions.
        recency_boost: Recency boost value (0.0-1.0).
        has_mca_collateral: Whether collateral matches MCA keywords.

    Returns:
        Numeric score (higher = more qualified).
    """
    base = position_count * 10.0
    collateral_bonus = 5.0 if has_mca_collateral else 0.0
    return base + (recency_boost * 5.0) + collateral_bonus


async def score_lead(
    debtor_name: str,
    state: str,
    filing_date: datetime | None,
    has_mca_collateral: bool,
) -> dict:
    """Score a lead and return scoring details.

    Args:
        debtor_name: Canonical debtor name.
        state: State code.
        filing_date: Date of the triggering filing.
        has_mca_collateral: Whether collateral indicates MCA.

    Returns:
        Dict with score, tier, position_count.
    """
    positions = await count_positions(debtor_name, state)
    recency = calculate_recency_boost(filing_date)
    score = compute_score(positions, recency, has_mca_collateral)
    tier = assign_tier(positions)

    logger.info(
        "lead_scored",
        debtor=debtor_name,
        state=state,
        positions=positions,
        score=score,
        tier=tier,
    )
    return {
        "lead_score": score,
        "mca_position_count": positions,
        "tier": tier,
    }
