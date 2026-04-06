"""Tests for the waterfall executor."""

import pybreaker
import pytest

from app.enrichment.waterfall import WaterfallExecutor, WaterfallExhaustedError


@pytest.mark.asyncio
async def test_waterfall_returns_first_success():
    """Waterfall returns result from first successful strategy."""
    async def fail(**kw):
        raise ValueError("nope")
    async def succeed(**kw):
        return {"phone": "555-0100"}

    executor = WaterfallExecutor([("bad", fail), ("good", succeed)])
    source, result = await executor.execute(name="test")
    assert source == "good"
    assert result["phone"] == "555-0100"


@pytest.mark.asyncio
async def test_waterfall_raises_when_all_fail():
    """Waterfall raises WaterfallExhaustedError when all strategies fail."""
    async def fail(**kw):
        raise ValueError("nope")

    executor = WaterfallExecutor([("a", fail), ("b", fail)])
    with pytest.raises(WaterfallExhaustedError):
        await executor.execute(name="test")


@pytest.mark.asyncio
async def test_waterfall_stops_at_first_success():
    """Waterfall does not call subsequent strategies after success."""
    call_log = []
    async def first(**kw):
        call_log.append("first")
        return {"ok": True}
    async def second(**kw):
        call_log.append("second")
        return {"ok": True}

    executor = WaterfallExecutor([("first", first), ("second", second)])
    await executor.execute()
    assert call_log == ["first"]


@pytest.mark.asyncio
async def test_waterfall_skips_open_breaker():
    """Middle strategy not awaited when its breaker is open."""
    calls: list[str] = []

    async def first(**kw):
        calls.append("first")
        raise ValueError("fail")

    async def mid(**kw):
        calls.append("mid")
        return {"ok": True}

    async def third(**kw):
        calls.append("third")
        return {"ok": True}

    br = pybreaker.CircuitBreaker(fail_max=1)
    br.open()
    executor = WaterfallExecutor(
        [("first", first), ("mid", mid), ("third", third)],
        breakers={"mid": br},
    )
    source, _ = await executor.execute()
    assert source == "third"
    assert "mid" not in calls


@pytest.mark.asyncio
async def test_waterfall_exhausted_when_all_breakers_open():
    """WaterfallExhaustedError when every strategy is skipped by open breakers."""
    async def never(**kw):
        raise AssertionError("should not run")

    b = pybreaker.CircuitBreaker(fail_max=1)
    b.open()
    executor = WaterfallExecutor(
        [("a", never), ("b", never)],
        breakers={"a": b, "b": b},
    )
    with pytest.raises(WaterfallExhaustedError) as excinfo:
        await executor.execute()
    assert excinfo.value.skipped
