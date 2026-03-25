"""Tests for the async rate limiter."""

import asyncio
import time

import pytest

from app.scrapers.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_first_wait_is_fast():
    """First wait for a new state should complete quickly (no prior request)."""
    rl = RateLimiter(base_delay=1.0)
    start = time.monotonic()
    await rl.wait("CA")
    elapsed = time.monotonic() - start
    # First call has no prior request, so should be near-instant
    assert elapsed < 1.5


@pytest.mark.asyncio
async def test_second_wait_enforces_delay():
    """Second wait should enforce the base delay."""
    rl = RateLimiter(base_delay=0.1, jitter_pct=0.0)
    await rl.wait("TX")
    start = time.monotonic()
    await rl.wait("TX")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05  # At least some delay enforced


@pytest.mark.asyncio
async def test_different_states_independent():
    """Rate limits for different states should be independent."""
    rl = RateLimiter(base_delay=0.5, jitter_pct=0.0)
    await rl.wait("CA")
    start = time.monotonic()
    await rl.wait("TX")  # Different state, should not wait
    elapsed = time.monotonic() - start
    assert elapsed < 0.6


def test_record_success_resets_backoff():
    """record_success should reset the error count."""
    rl = RateLimiter()
    rl.record_error("CA")
    rl.record_error("CA")
    assert rl._error_count["CA"] == 2
    rl.record_success("CA")
    assert rl._error_count["CA"] == 0


def test_record_error_increments():
    """record_error should increment the error count."""
    rl = RateLimiter()
    rl.record_error("FL")
    assert rl._error_count["FL"] == 1
    rl.record_error("FL")
    assert rl._error_count["FL"] == 2


def test_backoff_respects_max():
    """Computed delay should not exceed max_backoff."""
    rl = RateLimiter(base_delay=1.0, jitter_pct=0.0, max_backoff=10.0)
    for _ in range(20):
        rl.record_error("OH")
    delay = rl._compute_delay("OH")
    assert delay <= 10.0


def test_jitter_varies_delay():
    """Delays with jitter enabled should vary across calls."""
    rl = RateLimiter(base_delay=3.0, jitter_pct=0.20)
    delays = {rl._compute_delay("NY") for _ in range(50)}
    assert len(delays) > 1
