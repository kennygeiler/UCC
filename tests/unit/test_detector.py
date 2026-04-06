"""Tests for MCA detector module."""

import pytest

from app.mca.detector import (
    check_collateral_keywords,
    check_shell_patterns,
    detect_mca,
    normalize_name,
)


def test_normalize_strips_llc():
    """Normalize removes LLC suffix."""
    assert normalize_name("Yellowstone Capital LLC") == "yellowstone capital"


def test_normalize_strips_inc():
    """Normalize removes Inc suffix."""
    assert normalize_name("OnDeck Capital Inc.") == "ondeck capital"


def test_normalize_strips_corp():
    """Normalize removes Corp suffix."""
    assert normalize_name("Fox Capital Corp") == "fox capital"


def test_normalize_collapses_whitespace():
    """Normalize collapses multiple spaces."""
    assert normalize_name("  Pearl   Capital  ") == "pearl capital"


def test_collateral_keywords_match():
    """Collateral with MCA keywords returns True."""
    assert check_collateral_keywords("All assets and future receipts") is True


def test_collateral_keywords_no_match():
    """Collateral without MCA keywords returns False."""
    assert check_collateral_keywords("Equipment located at 123 Main St") is False


def test_collateral_keywords_none():
    """None collateral returns False."""
    assert check_collateral_keywords(None) is False


def test_shell_pattern_match():
    """Shell company pattern returns confidence > 0."""
    assert check_shell_patterns("ABC Cash Advance Group") == 0.7


def test_shell_pattern_no_match():
    """Non-shell company returns 0."""
    assert check_shell_patterns("General Electric") == 0.0


@pytest.mark.asyncio
async def test_detect_mca_exact_alias_injected_map():
    """Exact normalized match uses alias map without DB."""
    amap = {"yellowstone capital": ("Yellowstone MCA", 0.95)}
    ok, canon, conf = await detect_mca("Yellowstone Capital LLC", None, alias_map=amap)
    assert ok is True
    assert canon == "Yellowstone MCA"
    assert conf == 0.95


@pytest.mark.asyncio
async def test_detect_mca_shell_path_injected_map():
    """Shell pattern matches when alias map misses."""
    amap: dict[str, tuple[str, float]] = {}
    ok, canon, conf = await detect_mca("ABC Cash Advance Group", None, alias_map=amap)
    assert ok is True
    assert conf == 0.7


@pytest.mark.asyncio
async def test_detect_mca_collateral_path_injected_map():
    """Collateral keywords match when secured party is present."""
    amap: dict[str, tuple[str, float]] = {}
    ok, canon, conf = await detect_mca(
        "Some Random Bank LLC",
        "Equipment and all assets and future receipts",
        alias_map=amap,
    )
    assert ok is True
    assert conf == 0.5


@pytest.mark.asyncio
async def test_detect_mca_negative_injected_map():
    """No MCA signal returns false."""
    amap: dict[str, tuple[str, float]] = {}
    ok, _, _ = await detect_mca(
        "General Electric Company",
        "Industrial equipment only",
        alias_map=amap,
    )
    assert ok is False


@pytest.mark.asyncio
async def test_detect_mca_fuzzy_typo_above_cutoff(monkeypatch):
    """Fuzzy alias: minor typo still matches configured alias."""
    monkeypatch.setenv("MCA_FUZZY_SCORE_CUTOFF", "80")
    monkeypatch.setenv("MCA_FUZZY_MIN_ALIAS_LEN", "5")
    amap = {"yellowstone capital": ("Yellowstone MCA", 0.95)}
    ok, canon, conf = await detect_mca(
        "Yellowstone Capitl LLC",
        None,
        alias_map=amap,
    )
    assert ok is True
    assert canon == "Yellowstone MCA"
    assert conf < 0.95


