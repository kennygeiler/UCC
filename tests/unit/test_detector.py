"""Tests for MCA detector module."""

from app.mca.detector import (
    check_collateral_keywords,
    check_shell_patterns,
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
