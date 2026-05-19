"""Lead scoring engine — MCA-only position counts with stack + recency tiers.

Tier rules (Better B):
- **hot:** ``mca_position_count >= 3`` OR (``>= 2`` MCA positions with any filing in last 90 days)
- **warm:** exactly 2 MCA positions (not hot by recency) OR 1 MCA position filed within 30 days
- **cold:** all other MCA leads

Score uses MCA position count, triggering-filing recency, collateral bonus, and a
confidence multiplier on the subtotal. Fuzzy matches receive a flat penalty.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.db import get_session
from app.logging import get_logger
from app.models.filing import UCCFiling
from app.models.lead import Lead

logger = get_logger("scorer")

FUZZY_MATCH_PENALTY = 5.0
REVIEW_CONFIDENCE_THRESHOLD = 0.85


async def count_positions(debtor_name: str, state: str) -> int:
    """Count MCA filing positions for a debtor in one state.

    Only rows with ``ucc_filings.is_mca`` true are counted (honest MCA stack depth).
    """
    async with get_session() as session:
        result = await session.execute(
            select(func.count(UCCFiling.id)).where(
                UCCFiling.debtor_name == debtor_name,
                UCCFiling.state == state,
                UCCFiling.is_mca.is_(True),
            )
        )
        return result.scalar_one()


async def get_mca_filing_dates(debtor_name: str, state: str) -> list[datetime]:
    """Filing dates for MCA-flagged filings for this debtor/state."""
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling.filing_date).where(
                UCCFiling.debtor_name == debtor_name,
                UCCFiling.state == state,
                UCCFiling.is_mca.is_(True),
                UCCFiling.filing_date.is_not(None),
            )
        )
        return [row[0] for row in result.all() if row[0] is not None]


def calculate_recency_boost(filing_date: datetime | None) -> float:
    """Recency boost from the triggering filing (0.0–1.0)."""
    if not filing_date:
        return 0.0
    if filing_date.tzinfo is None:
        filing_date = filing_date.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - filing_date
    if age < timedelta(days=30):
        return 1.0
    if age < timedelta(days=90):
        return 0.5
    if age < timedelta(days=180):
        return 0.25
    return 0.0


def _has_filing_within(days: int, dates: list[datetime]) -> bool:
    """True if any filing date is within ``days`` of now."""
    if not dates:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for dt in dates:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= cutoff:
            return True
    return False


def assign_tier(
    mca_position_count: int,
    mca_filing_dates: list[datetime],
) -> str:
    """Assign hot/warm/cold from MCA stack size and filing recency."""
    if mca_position_count >= 3:
        return "hot"
    if mca_position_count >= 2 and _has_filing_within(90, mca_filing_dates):
        return "hot"
    if mca_position_count == 2:
        return "warm"
    if mca_position_count == 1 and _has_filing_within(30, mca_filing_dates):
        return "warm"
    return "cold"


def compute_score(
    mca_position_count: int,
    recency_boost: float,
    has_mca_collateral: bool,
    mca_match_confidence: float,
    mca_match_type: str | None,
) -> float:
    """Compute lead score with confidence multiplier and match-type penalty."""
    base = mca_position_count * 10.0
    collateral_bonus = 5.0 if has_mca_collateral else 0.0
    subtotal = base + (recency_boost * 5.0) + collateral_bonus

    conf = max(0.0, min(1.0, mca_match_confidence))
    score = subtotal * (0.5 + 0.5 * conf)

    if mca_match_type == "fuzzy":
        score -= FUZZY_MATCH_PENALTY

    return round(max(0.0, score), 2)


def needs_match_review(mca_match_confidence: float | None, mca_match_type: str | None) -> bool:
    """True when MCA match should be human-reviewed."""
    if mca_match_type == "fuzzy":
        return True
    if mca_match_confidence is None:
        return False
    return mca_match_confidence < REVIEW_CONFIDENCE_THRESHOLD


async def score_lead(
    debtor_name: str,
    state: str,
    filing_date: datetime | None,
    has_mca_collateral: bool,
    mca_match_confidence: float = 1.0,
    mca_match_type: str | None = "exact",
) -> dict:
    """Score a lead and return tier, MCA position count, and score."""
    positions = await count_positions(debtor_name, state)
    filing_dates = await get_mca_filing_dates(debtor_name, state)
    if filing_date and filing_date not in filing_dates:
        filing_dates = [*filing_dates, filing_date]

    recency = calculate_recency_boost(filing_date)
    tier = assign_tier(positions, filing_dates)
    score = compute_score(
        positions,
        recency,
        has_mca_collateral,
        mca_match_confidence,
        mca_match_type,
    )

    logger.info(
        "lead_scored",
        debtor=debtor_name,
        state=state,
        mca_positions=positions,
        score=score,
        tier=tier,
        match_type=mca_match_type,
    )
    return {
        "lead_score": score,
        "mca_position_count": positions,
        "tier": tier,
    }
