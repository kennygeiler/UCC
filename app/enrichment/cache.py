"""Enrichment cache — permanent Postgres cache, no TTL (C-08).

Cache rows use a stable ``source_api`` (``aggregate``) plus a normalized
``input_key`` so reads and writes always match.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.dnc import EnrichmentCache

logger = get_logger("enrichment_cache")

# Single bucket for post-waterfall normalized payloads (canonical dict per debtor+state).
ENRICHMENT_CACHE_SOURCE = "aggregate"


def enrichment_cache_key(debtor_name: str, state: str) -> str:
    """Stable key for cache lookups: lower name + upper state."""
    return f"{debtor_name.strip().lower()}|{state.strip().upper()}"


async def get_cached(source_api: str, input_key: str) -> dict | None:
    """Check cache for a previous enrichment result.

    Args:
        source_api: Source name (e.g. ``aggregate``, ``pdl``).
        input_key: Lookup key (e.g. normalized ``name|STATE``).

    Returns:
        Cached result dict or None.
    """
    async with get_session() as session:
        result = await session.execute(
            select(EnrichmentCache).where(
                EnrichmentCache.source_api == source_api,
                EnrichmentCache.input_key == input_key,
            )
        )
        cached = result.scalar_one_or_none()
    if cached:
        logger.info("cache_hit", source=source_api, key=input_key)
        raw = cached.result_json
        if isinstance(raw, str):
            return json.loads(raw)
        if isinstance(raw, dict):
            return raw
    return None


async def store_cached(source_api: str, input_key: str, result: dict) -> None:
    """Store an enrichment result in the permanent cache (upsert by source + key)."""
    async with get_session() as session:
        existing = await session.execute(
            select(EnrichmentCache).where(
                EnrichmentCache.source_api == source_api,
                EnrichmentCache.input_key == input_key,
            )
        )
        row = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if row:
            row.result_json = result
            row.fetched_at = now
        else:
            session.add(
                EnrichmentCache(
                    source_api=source_api,
                    input_key=input_key,
                    result_json=result,
                    fetched_at=now,
                )
            )
    logger.info("cache_store", source=source_api, key=input_key)
