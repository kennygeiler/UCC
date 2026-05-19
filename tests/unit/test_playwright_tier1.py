"""Unit tests for Playwright Tier 1 shared package."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from app.scrapers.playwright_tier1.checkpoints import search_profile_key
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings, load_playwright_scrape_settings
from app.scrapers.states.new_york import NewYorkScraper


def test_search_profile_key_normalizes_term():
    assert search_profile_key("  ondeck  ") == "search|ONDECK"


def test_ny_row_to_filing_parses_grid_cells():
    scraper = NewYorkScraper()
    cells = [
        "2024000123",
        "1",
        "UC",
        "ACME LLC",
        "123 Main",
        "Org",
        "3/15/2024 10:00:00 AM",
        "",
        "Active",
    ]
    filing = scraper._row_to_filing(cells)
    assert filing is not None
    assert filing["filing_number"] == "2024000123"
    assert filing["debtor_name"] == "ACME LLC"
    assert filing["state"] == "NY"
    assert filing["filing_date"] is not None


def test_ny_row_to_filing_rejects_header_like_rows():
    scraper = NewYorkScraper()
    assert scraper._row_to_filing(["Lien Number", "Serial"]) is None


@pytest.mark.asyncio
async def test_build_search_terms_mca_and_extra(monkeypatch):
    from app.scrapers.playwright_tier1 import search_terms as st

    monkeypatch.setattr(
        st,
        "load_mca_search_terms",
        AsyncMock(return_value=["ONDECK CAPITAL", "CREDIBLY"]),
    )
    terms = await st.build_search_term_list(
        mca_limit=20,
        extra_terms=("CUSTOM TERM",),
        max_terms=5,
    )
    assert terms == ["ONDECK CAPITAL", "CREDIBLY", "CUSTOM TERM"]


@pytest.mark.asyncio
async def test_checkpoint_save_and_resume():
    from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint

    with patch(
        "app.scrapers.playwright_tier1.checkpoints.get_checkpoint",
        AsyncMock(return_value=0),
    ) as get_cp, patch(
        "app.scrapers.playwright_tier1.checkpoints.save_checkpoint",
        AsyncMock(),
    ) as save_cp:
        assert await get_page_checkpoint("NY", "ONDECK") == 0
        await save_page_checkpoint("NY", "ONDECK", 2)
        save_cp.assert_called_once_with("NY", search_profile_key("ONDECK"), 2)
        get_cp.assert_called_once()


def test_load_playwright_scrape_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("NY_SCRAPE_MAX_PAGES", "7")
    monkeypatch.setenv("NY_SCRAPE_MAX_TERMS", "4")
    settings = load_playwright_scrape_settings("NY")
    assert settings.max_pages == 7
    assert settings.max_terms == 4


def test_ny_fixture_html_has_grid():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "fixtures/playwright_tier1/ny_grid_page1.html"
    )
    soup = BeautifulSoup(path.read_text(), "html.parser")
    rows = soup.select("#xhtml_grid tbody tr")
    assert len(rows) == 2
    assert "Page 1 / 2" in path.read_text()


@pytest.mark.asyncio
async def test_playwright_tier1_effective_max_pages_page_cap():
    scraper = NewYorkScraper(
        scrape_settings=PlaywrightScrapeSettings(
            max_pages=50,
            max_terms=10,
            fetch_detail=False,
            mca_term_limit=10,
            extra_search_terms=(),
            page_cap_per_run=3,
        )
    )
    assert scraper._effective_max_pages() == 3
