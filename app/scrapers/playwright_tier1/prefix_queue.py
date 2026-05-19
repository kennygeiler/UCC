"""Rotate prefix search terms across runs via scraper_checkpoints."""

from __future__ import annotations

from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint

_PREFIX_CURSOR = "__prefix_offset__"


async def get_prefix_offset(state: str, profile: str) -> int:
    """Index into the prefix term list for the next run."""
    return await get_page_checkpoint(state, profile, _PREFIX_CURSOR)


async def save_prefix_offset(state: str, profile: str, offset: int) -> None:
    """Persist prefix queue cursor after a run."""
    await save_page_checkpoint(state, profile, _PREFIX_CURSOR, offset)


def slice_prefix_terms(
    all_terms: tuple[str, ...],
    *,
    offset: int,
    max_terms: int | None,
) -> tuple[list[str], int]:
    """Return terms for this run and the next offset (wraps at end)."""
    if not all_terms:
        return [], 0
    n = len(all_terms)
    start = offset % n
    if max_terms is None or max_terms >= n:
        batch = list(all_terms[start:]) + list(all_terms[:start]) if start else list(all_terms)
        take = max_terms if max_terms is not None else len(batch)
        return batch[:take], (start + take) % n

    batch: list[str] = []
    idx = start
    for _ in range(max_terms):
        batch.append(all_terms[idx])
        idx = (idx + 1) % n
    return batch, idx
