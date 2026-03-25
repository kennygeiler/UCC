"""Tests for the waterfall executor."""

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
