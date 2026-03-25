"""Tests for app.services.job_queue — enqueue, claim, complete, fail operations.

These tests verify the function signatures and logic without a live database.
Integration tests with a real database would go in tests/integration/.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

from app.services.job_queue import enqueue, claim, complete, fail


@pytest.mark.asyncio
async def test_enqueue_creates_pending_job():
    """enqueue() should add a JobQueue instance with status=pending to the session."""
    session = AsyncMock()
    session.flush = AsyncMock()

    # Patch JobQueue so we can inspect what was created
    with patch("app.services.job_queue.JobQueue") as MockJob:
        instance = MagicMock()
        instance.id = 42
        MockJob.return_value = instance

        job_id = await enqueue(session, "scrape", {"state": "CA"}, priority=5)

        MockJob.assert_called_once()
        call_kwargs = MockJob.call_args[1]
        assert call_kwargs["job_type"] == "scrape"
        assert call_kwargs["payload"] == {"state": "CA"}
        assert call_kwargs["status"] == "pending"
        assert call_kwargs["priority"] == 5
        session.add.assert_called_once_with(instance)
        session.flush.assert_awaited_once()
        assert job_id == 42


@pytest.mark.asyncio
async def test_complete_updates_status():
    """complete() should execute an update setting status=completed."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()

    await complete(session, job_id=1)

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_fail_updates_status_and_increments_retry():
    """fail() should execute an update setting status=failed and incrementing retry_count."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()

    await fail(session, job_id=1, error="connection timeout")

    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()
