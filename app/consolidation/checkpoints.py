"""Read/write FL scraper pagination checkpoints."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import get_session
from app.models.account import ScraperCheckpoint


def profile_key(search_option_type: str, search_option_sub_option: str) -> str:
    """Stable checkpoint key for an index profile."""
    return f"{search_option_type}|{search_option_sub_option}"


async def get_checkpoint(state: str, index_profile: str) -> int:
    """Return last saved ``rowNumber`` for this profile (0 if none)."""
    async with get_session() as session:
        row = (
            await session.execute(
                select(ScraperCheckpoint).where(
                    ScraperCheckpoint.state == state,
                    ScraperCheckpoint.index_profile == index_profile,
                )
            )
        ).scalar_one_or_none()
    return row.last_row_number if row else 0


async def save_checkpoint(state: str, index_profile: str, row_number: int) -> None:
    """Persist pagination cursor after each page."""
    async with get_session() as session:
        row = (
            await session.execute(
                select(ScraperCheckpoint).where(
                    ScraperCheckpoint.state == state,
                    ScraperCheckpoint.index_profile == index_profile,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(
                ScraperCheckpoint(
                    state=state,
                    index_profile=index_profile,
                    last_row_number=row_number,
                )
            )
        else:
            row.last_row_number = row_number
            row.updated_at = datetime.now(timezone.utc)
