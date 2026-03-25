"""Lead recycling — re-queue eligible leads after disposition cooldown."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.lead import Lead

logger = get_logger("recycler")

# Disposition → cooldown days before re-engagement
RECYCLE_RULES: dict[str, int] = {
    "not_interested": 30,
    "no_answer": 7,
    "callback": 1,
}


async def get_recyclable_leads() -> list[Lead]:
    """Fetch leads eligible for recycling based on disposition and cooldown.

    Returns:
        List of leads whose cooldown period has elapsed.
    """
    now = datetime.now(timezone.utc)
    recyclable: list[Lead] = []

    async with get_session() as session:
        for disposition, cooldown_days in RECYCLE_RULES.items():
            cutoff = now - timedelta(days=cooldown_days)
            result = await session.execute(
                select(Lead)
                .where(Lead.disposition == disposition)
                .where(Lead.disposition_updated_at <= cutoff)
                .where(Lead.export_status != "recycled")
            )
            recyclable.extend(result.scalars().all())

    return recyclable


async def recycle_leads() -> int:
    """Re-queue eligible leads for new campaign enrollment.

    Returns:
        Number of leads recycled.
    """
    leads = await get_recyclable_leads()
    recycled = 0

    async with get_session() as session:
        for lead in leads:
            lead.export_status = "pending"
            lead.disposition = None
            lead.disposition_updated_at = None
            session.add(lead)
            recycled += 1

    logger.info("recycle_complete", recycled=recycled)
    return recycled
