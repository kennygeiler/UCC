"""Checkpoint helpers for Playwright Tier 1 pagination (reuses scraper_checkpoints)."""

from __future__ import annotations

from app.consolidation.checkpoints import get_checkpoint, save_checkpoint


def search_profile_key(search_term: str) -> str:
    """Checkpoint profile for a single search term."""
    return f"search|{search_term.strip().upper()}"


async def get_page_checkpoint(state: str, search_term: str) -> int:
    """Last completed page index (0 = none)."""
    return await get_checkpoint(state, search_profile_key(search_term))


async def save_page_checkpoint(state: str, search_term: str, page_index: int) -> None:
    """Persist last completed page index for this term."""
    await save_checkpoint(state, search_profile_key(search_term), page_index)
