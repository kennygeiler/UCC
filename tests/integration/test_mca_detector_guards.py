"""Integration-style tests for MCA detector government/CSC guards (no DB)."""

import pytest

from app.mca.detector import detect_mca


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detector_rejects_sba_with_mca_alias_map():
    """SBA must not match even when alias map contains similar MCA names."""
    amap = {
        "world business lenders": ("World Business Lenders", 0.95),
        "yellowstone capital": ("Yellowstone Capital", 0.95),
    }
    ok, canon, conf, match_type = await detect_mca(
        "U.S. SMALL BUSINESS ADMINISTRATION",
        None,
        alias_map=amap,
        alias_class_map={},
    )
    assert ok is False
    assert match_type is None
    assert canon is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detector_accepts_real_mca_exact():
    amap = {"ondeck capital": ("OnDeck Capital", 0.95)}
    ok, canon, conf, match_type = await detect_mca(
        "OnDeck Capital LLC",
        None,
        alias_map=amap,
        alias_class_map={},
    )
    assert ok is True
    assert match_type == "exact"
    assert canon == "OnDeck Capital"
    assert conf >= 0.9
