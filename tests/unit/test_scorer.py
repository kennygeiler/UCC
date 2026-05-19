"""Tests for lead scoring engine (Better B)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.mca.scorer import (
    assign_tier,
    calculate_recency_boost,
    compute_score,
    needs_match_review,
)


def test_assign_tier_hot_three_positions():
    assert assign_tier(3, []) == "hot"


def test_assign_tier_hot_two_with_recent_filing():
    recent = [datetime.now(timezone.utc) - timedelta(days=10)]
    assert assign_tier(2, recent) == "hot"


def test_assign_tier_warm_two_without_recent():
    old = [datetime.now(timezone.utc) - timedelta(days=120)]
    assert assign_tier(2, old) == "warm"


def test_assign_tier_warm_one_recent():
    recent = [datetime.now(timezone.utc) - timedelta(days=5)]
    assert assign_tier(1, recent) == "warm"


def test_assign_tier_cold_one_stale():
    old = [datetime.now(timezone.utc) - timedelta(days=60)]
    assert assign_tier(1, old) == "cold"


def test_recency_boost_recent():
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    assert calculate_recency_boost(recent) == 1.0


def test_recency_boost_medium():
    medium = datetime.now(timezone.utc) - timedelta(days=60)
    assert calculate_recency_boost(medium) == 0.5


def test_recency_boost_old():
    old = datetime.now(timezone.utc) - timedelta(days=200)
    assert calculate_recency_boost(old) == 0.0


def test_recency_boost_none():
    assert calculate_recency_boost(None) == 0.0


def test_compute_score_confidence_multiplier():
    """Score scales with match confidence."""
    high = compute_score(2, 0.0, False, 0.95, "exact")
    low = compute_score(2, 0.0, False, 0.5, "exact")
    assert high > low


def test_compute_score_fuzzy_penalty():
    exact = compute_score(2, 0.0, False, 0.9, "exact")
    fuzzy = compute_score(2, 0.0, False, 0.9, "fuzzy")
    assert fuzzy < exact


def test_compute_score_collateral_bonus():
    base = compute_score(1, 0.0, False, 1.0, "exact")
    with_collateral = compute_score(1, 0.0, True, 1.0, "exact")
    assert with_collateral > base


def test_needs_match_review_fuzzy():
    assert needs_match_review(0.99, "fuzzy") is True


def test_needs_match_review_low_confidence():
    assert needs_match_review(0.7, "exact") is True


def test_needs_match_review_high_exact():
    assert needs_match_review(0.9, "exact") is False


def test_score_tier_uses_recency_not_score_alone():
    """Tier warm from recency even when position count alone would be cold."""
    recent = [datetime.now(timezone.utc) - timedelta(days=3)]
    assert assign_tier(1, recent) == "warm"
    assert assign_tier(1, []) == "cold"
