"""Integration: concurrent job claim proves SKIP LOCKED behavior (PLAT-05)."""

import asyncio

import pytest
from sqlalchemy import delete

from app.db import get_session
from app.models.job import JobQueue
from app.services.job_queue import claim, enqueue

pytestmark = pytest.mark.integration

_JOB_TYPE = "integration_concurrency_test"


@pytest.mark.asyncio
async def test_concurrent_claim_single_pending_job():
    """Two workers cannot both claim the same pending job row."""
    from app.db import get_engine
    from sqlalchemy import text

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")

    async with get_session() as session:
        await enqueue(session, _JOB_TYPE, {"probe": True})

    async def try_claim(worker: str):
        async with get_session() as session:
            return await claim(session, [_JOB_TYPE], worker)

    results = await asyncio.gather(try_claim("w1"), try_claim("w2"))
    claimed = [r for r in results if r is not None]
    assert len(claimed) == 1
    assert claimed[0].status == "running"

    async with get_session() as session:
        await session.execute(delete(JobQueue).where(JobQueue.job_type == _JOB_TYPE))
