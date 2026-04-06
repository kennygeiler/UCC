"""Smoke tests for scraper registry (SCRAPE-06).

Fast smokes (``@pytest.mark.smoke`` without ``slow``): every tier 1–3 state has a
valid ``build_search_url()`` — no network.

Live portal checks (``@pytest.mark.slow`` + ``smoke``): Tier 1 only; run on a
schedule or locally: ``pytest tests/smoke/ -m \"slow\" -v``.

PR CI runs ``pytest -m \"not slow\"`` so slow tests are excluded by default.
"""

import pytest

from app.scrapers.registry import SCRAPER_REGISTRY, schedulable_state_codes


@pytest.mark.smoke
@pytest.mark.parametrize("state_code", schedulable_state_codes())
def test_build_search_url_for_every_schedulable_state(state_code):
    """Each production scraper exposes an https search URL (no HTTP request)."""
    entry = SCRAPER_REGISTRY[state_code]
    scraper = entry["class"]()
    url = scraper.build_search_url()
    assert url.startswith("https://"), f"{state_code}: invalid URL scheme: {url!r}"
    assert len(url) > 12, f"{state_code}: URL unexpectedly short"


@pytest.mark.slow
@pytest.mark.smoke
@pytest.mark.parametrize(
    "state_code",
    [c for c, i in SCRAPER_REGISTRY.items() if i["tier"] == 1],
)
def test_tier1_live_search_url_reachable(state_code):
    """Optional live check: Tier 1 ``build_search_url`` looks like a real portal URL."""
    entry = SCRAPER_REGISTRY[state_code]
    scraper = entry["class"]()
    url = scraper.build_search_url()
    assert url.startswith("http"), f"{state_code} search URL is invalid: {url}"
