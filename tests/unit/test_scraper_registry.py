"""Tests for the scraper registry."""

from app.scrapers.base import BaseScraper
from app.scrapers.registry import (
    SCRAPER_REGISTRY,
    get_scraper_class,
    get_states_by_tier,
)


EXPECTED_TIER1 = ["CA", "TX", "FL", "NY", "NJ", "GA", "IL", "PA", "OH", "MD"]
EXPECTED_TIER3 = ["NH", "RI", "DE", "HI", "NV", "UT"]


def test_registry_has_all_tier1_states():
    """Registry must contain all 10 Tier 1 states."""
    for state in EXPECTED_TIER1:
        assert state in SCRAPER_REGISTRY, f"{state} missing from registry"


def test_registry_has_40_entries():
    """Registry should have 40 entries (10 T1 + 24 T2 + 6 T3)."""
    assert len(SCRAPER_REGISTRY) == 40


def test_tier_counts():
    """Each tier should have the expected number of states."""
    assert len(get_states_by_tier(1)) == 10
    assert len(get_states_by_tier(2)) == 24
    assert len(get_states_by_tier(3)) == 6


def test_all_classes_are_base_scraper_subclasses():
    """Every registered class must be a subclass of BaseScraper."""
    for state, info in SCRAPER_REGISTRY.items():
        assert issubclass(info["class"], BaseScraper), f"{state} class invalid"


def test_get_scraper_class_returns_correct_class():
    """get_scraper_class should return the right class for known states."""
    cls = get_scraper_class("CA")
    assert cls is not None
    scraper = cls()
    assert scraper.state_code == "CA"


def test_get_scraper_class_returns_none_for_unknown():
    """get_scraper_class should return None for unregistered states."""
    assert get_scraper_class("ZZ") is None


def test_get_states_by_tier_returns_all_tier1():
    """get_states_by_tier(1) should return all 10 Tier 1 state codes."""
    states = get_states_by_tier(1)
    assert set(states) == set(EXPECTED_TIER1)


def test_get_states_by_tier_returns_all_tier3():
    """get_states_by_tier(3) should return all 6 Tier 3 state codes."""
    states = get_states_by_tier(3)
    assert set(states) == set(EXPECTED_TIER3)


def test_each_scraper_instantiates():
    """Every registered scraper class should be instantiable."""
    for state, info in SCRAPER_REGISTRY.items():
        scraper = info["class"]()
        assert scraper.state_code == state
        assert scraper.tier == info["tier"]
