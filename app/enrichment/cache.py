"""Enrichment cache — permanent Postgres cache, no TTL (C-08)."""

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.dnc import EnrichmentCache

logger = get_logger("enrichment_cache")


async def get_cached(source_api: str, input_key: str) -> dict | None:
    """Check cache for a previous enrichment result.

    Args:
        source_api: Source name (e.g. 'pdl', 'apollo').
        input_key: Lookup key (e.g. business name + state).

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
        return json.loads(cached.result_json) if isinstance(cached.result_json, str) else cached.result_json
    return None


async def store_cached(source_api: str, input_key: str, result: dict) -> None:
    """Store an enrichment result in the permanent cache.

    Args:
        source_api: Source name.
        input_key: Lookup key.
        result: Result data to cache.
    """
    async with get_session() as session:
        entry = EnrichmentCache(
            source_api=source_api,
            input_key=input_key,
            result_json=result,
            fetched_at=datetime.now(timezone.utc),
        )
        session.add(entry)
    logger.info("cache_store", source=source_api, key=input_key)
