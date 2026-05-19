"""Tier 1 readiness and registry integration."""

import pytest

from app.scrapers.exceptions import ScraperNotReadyError
from app.scrapers.registry import get_tier1_state_codes

EXPECTED_TIER1 = ["CA", "TX", "FL", "NY", "NJ", "GA", "IL", "PA", "OH", "MD"]
from app.scrapers.state_config import (
    TIER1_READINESS,
    ScraperReadiness,
    is_tier1_runnable,
    list_tier1_ready_states,
    tier1_readiness,
)


def test_tier1_codes_match_registry():
    assert set(get_tier1_state_codes()) == set(EXPECTED_TIER1)


@pytest.mark.parametrize(
    "state,expected",
    [
        ("FL", ScraperReadiness.READY),
        ("CA", ScraperReadiness.PLAYWRIGHT),
        ("TX", ScraperReadiness.PLAYWRIGHT),
        ("GA", ScraperReadiness.NOT_READY),
    ],
)
def test_tier1_readiness_labels(state, expected):
    assert tier1_readiness(state) == expected


def test_list_tier1_ready_includes_fl_ca_tx():
    ready = set(list_tier1_ready_states())
    assert {"FL", "CA", "TX", "NY", "NJ"} <= ready
    assert "GA" not in ready


def test_is_tier1_runnable():
    assert is_tier1_runnable("FL")
    assert is_tier1_runnable("CA")
    assert not is_tier1_runnable("GA")


@pytest.mark.asyncio
async def test_not_ready_scraper_raises():
    from unittest.mock import AsyncMock, patch

    from app.scrapers.states.georgia import GeorgiaScraper

    scraper = GeorgiaScraper()
    run = AsyncMock()
    run.id = 1
    with patch.object(scraper, "_start_run", AsyncMock(return_value=run)):
        with patch.object(scraper, "_fail_run", AsyncMock()):
            with pytest.raises(ScraperNotReadyError):
                await scraper.scrape()


def test_all_tier1_have_readiness_entry():
    for code in get_tier1_state_codes():
        assert code in TIER1_READINESS
