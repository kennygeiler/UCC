"""Tests for the async rate limiter."""

import asyncio
import time
from unittest.mock import patch

import pytest

from app.scrapers.rate_limiter import TIER3_MIN_DELAY, RateLimiter


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


# --- Tier-3 enforcement (C-09) ---


def test_tier3_enforces_minimum_delay():
    """Tier-3 delay must be at least TIER3_MIN_DELAY (10 s)."""
    rl = RateLimiter(base_delay=3.0, jitter_pct=0.0)
    delay = rl._compute_delay("NH", tier=3)
    assert delay >= TIER3_MIN_DELAY


def test_tier3_backoff_exceeds_minimum():
    """When backoff exceeds the tier-3 floor, backoff wins."""
    rl = RateLimiter(base_delay=3.0, jitter_pct=0.0, max_backoff=60.0)
    # 4 errors -> 3 * 2^4 = 48 s, which is > 10 s floor
    for _ in range(4):
        rl.record_error("RI")
    delay = rl._compute_delay("RI", tier=3)
    assert delay == 48.0


def test_tier1_not_affected_by_tier3_floor():
    """Tier-1 states should NOT get the 10-second floor."""
    rl = RateLimiter(base_delay=3.0, jitter_pct=0.0)
    delay = rl._compute_delay("CA", tier=1)
    assert delay == 3.0


def test_no_tier_not_affected_by_tier3_floor():
    """When tier is None, the tier-3 floor does not apply."""
    rl = RateLimiter(base_delay=3.0, jitter_pct=0.0)
    delay = rl._compute_delay("CA", tier=None)
    assert delay == 3.0


def test_get_proxy_returns_none_without_config():
    """Without PROXY_URL configured, get_proxy returns None."""
    rl = RateLimiter()
    assert rl.get_proxy(tier=3) is None


def test_get_proxy_returns_none_for_non_tier3():
    """Non-tier-3 requests never get a proxy."""
    rl = RateLimiter()
    rl._proxy_cycle = iter(["http://proxy:8080"])
    assert rl.get_proxy(tier=1) is None
    assert rl.get_proxy(tier=2) is None
    assert rl.get_proxy(tier=None) is None


def test_get_proxy_rotates():
    """Tier-3 proxy rotation should cycle through configured proxies."""
    import itertools

    rl = RateLimiter()
    rl._proxy_cycle = itertools.cycle(["http://p1:8080", "http://p2:8080"])
    assert rl.get_proxy(tier=3) == "http://p1:8080"
    assert rl.get_proxy(tier=3) == "http://p2:8080"
    assert rl.get_proxy(tier=3) == "http://p1:8080"


@pytest.mark.asyncio
async def test_tier3_wait_enforces_floor():
    """Tier-3 wait should enforce at least TIER3_MIN_DELAY between requests."""
    rl = RateLimiter(base_delay=0.1, jitter_pct=0.0)
    # Simulate a recent request
    rl._last_request["DE"] = time.monotonic()
    delay = rl._compute_delay("DE", tier=3)
    assert delay >= TIER3_MIN_DELAY
