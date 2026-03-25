"""Tests for the scraper registry."""

from app.scrapers.base import BaseScraper
from app.scrapers.registry import (
    SCRAPER_REGISTRY,
    get_scraper_class,
    get_tier1_states,
)


EXPECTED_TIER1 = ["CA", "TX", "FL", "NY", "NJ", "GA", "IL", "PA", "OH", "MD"]


def test_registry_has_all_tier1_states():
    """Registry must contain all 10 Tier 1 states."""
    for state in EXPECTED_TIER1:
        assert state in SCRAPER_REGISTRY, f"{state} missing from registry"


def test_registry_has_exactly_10_entries():
    """Registry should have exactly 10 entries for Tier 1."""
    assert len(SCRAPER_REGISTRY) == 10


def test_all_entries_are_tier_1():
    """All current registry entries should be tier 1."""
    for state, info in SCRAPER_REGISTRY.items():
        assert info["tier"] == 1, f"{state} is not tier 1"


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


def test_get_tier1_states_returns_all():
    """get_tier1_states should return all 10 Tier 1 state codes."""
    states = get_tier1_states()
    assert set(states) == set(EXPECTED_TIER1)


def test_each_scraper_instantiates():
    """Every registered scraper class should be instantiable."""
    for state, info in SCRAPER_REGISTRY.items():
        scraper = info["class"]()
        assert scraper.state_code == state
        assert scraper.tier == info["tier"]
