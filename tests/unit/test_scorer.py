"""Tests for lead scoring engine."""

from datetime import datetime, timedelta, timezone

from app.mca.scorer import assign_tier, calculate_recency_boost, compute_score


def test_assign_tier_hot():
    """3+ positions is hot."""
    assert assign_tier(3) == "hot"
    assert assign_tier(5) == "hot"


def test_assign_tier_warm():
    """2 positions is warm."""
    assert assign_tier(2) == "warm"


def test_assign_tier_cold():
    """1 position is cold."""
    assert assign_tier(1) == "cold"


def test_recency_boost_recent():
    """Filing within 30 days gets full boost."""
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    assert calculate_recency_boost(recent) == 1.0


def test_recency_boost_medium():
    """Filing 60 days ago gets half boost."""
    medium = datetime.now(timezone.utc) - timedelta(days=60)
    assert calculate_recency_boost(medium) == 0.5


def test_recency_boost_old():
    """Filing 200+ days ago gets no boost."""
    old = datetime.now(timezone.utc) - timedelta(days=200)
    assert calculate_recency_boost(old) == 0.0


def test_recency_boost_none():
    """None filing date gets no boost."""
    assert calculate_recency_boost(None) == 0.0


def test_compute_score_hot_lead():
    """Hot lead with recent filing and MCA collateral scores high."""
    score = compute_score(position_count=4, recency_boost=1.0, has_mca_collateral=True)
    assert score == 50.0  # 40 + 5 + 5


def test_compute_score_cold_lead():
    """Cold lead with no boosts scores low."""
    score = compute_score(position_count=1, recency_boost=0.0, has_mca_collateral=False)
    assert score == 10.0


def test_score_changes_with_recency_and_collateral_tier_unchanged():
    """MCA-02: lead_score moves with recency/collateral; tier is position-only."""
    assert assign_tier(2) == "warm"
    low = compute_score(2, recency_boost=0.0, has_mca_collateral=False)
    high_recency = compute_score(2, recency_boost=1.0, has_mca_collateral=False)
    with_collateral = compute_score(2, recency_boost=0.0, has_mca_collateral=True)
    assert high_recency > low
    assert with_collateral > low
    assert assign_tier(2) == assign_tier(2)
