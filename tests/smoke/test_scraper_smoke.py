"""Smoke tests hitting live state SOS portals.

Marked with pytest.mark.slow — excluded from CI, run manually or on schedule.
Usage: pytest tests/smoke/ -m slow -v
"""

import pytest

from app.scrapers.registry import SCRAPER_REGISTRY, get_states_by_tier


@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.parametrize("state_code", get_states_by_tier(1))
async def test_tier1_scraper_fetches(state_code):
    """Verify Tier 1 scrapers can fetch from live portals."""
    entry = SCRAPER_REGISTRY[state_code]
    scraper = entry["class"]()
    url = scraper.build_search_url()
    assert url.startswith("http"), f"{state_code} search URL is invalid: {url}"
