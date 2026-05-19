"""Unit tests for Playwright Tier 1 shared package."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from app.scrapers.playwright_tier1.checkpoints import search_profile_key
from app.scrapers.playwright_tier1.detail_fetch import parse_detail_fields_from_text
from app.scrapers.playwright_tier1.prefix_queue import slice_prefix_terms
from app.scrapers.playwright_tier1.profiles import (
    NY_SEARCH_PROFILES,
    PartySearchMode,
    parse_profile_list,
)
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings, load_playwright_scrape_settings
from app.scrapers.states.new_york import NewYorkScraper


def test_search_profile_key_includes_profile_and_term():
    assert search_profile_key("secured_party_org_sw", "  ondeck  ") == (
        "secured_party_org_sw|ONDECK"
    )


def test_ny_row_to_filing_parses_grid_cells():
    scraper = NewYorkScraper()
    profile = NY_SEARCH_PROFILES["debtor_org_sw"]
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
    filing = scraper._row_to_filing(
        cells, profile=profile, search_term="A", secured_party_col=None
    )
    assert filing is not None
    assert filing["filing_number"] == "2024000123"
    assert filing["debtor_name"] == "ACME LLC"
    assert filing["state"] == "NY"
    assert filing["filing_date"] is not None


def test_ny_secured_party_profile_sets_sp_from_term():
    scraper = NewYorkScraper()
    profile = NY_SEARCH_PROFILES["secured_party_org_sw"]
    cells = [
        "2024000123",
        "1",
        "UC",
        "ACME LLC",
        "123 Main",
        "Org",
        "3/15/2024",
        "",
        "Active",
    ]
    filing = scraper._row_to_filing(
        cells,
        profile=profile,
        search_term="yellowstone",
        secured_party_col=None,
    )
    assert filing["secured_party"] == "YELLOWSTONE"


def test_ny_row_parses_secured_party_column_from_grid():
    scraper = NewYorkScraper()
    profile = NY_SEARCH_PROFILES["debtor_org_sw"]
    cells = [
        "2024000999",
        "1",
        "UC",
        "ACME LLC",
        "123 Main",
        "Org",
        "3/15/2024",
        "YELLOWSTONE CAPITAL LLC",
        "Active",
    ]
    filing = scraper._row_to_filing(
        cells,
        profile=profile,
        search_term="A",
        secured_party_col=7,
    )
    assert filing["secured_party"] == "YELLOWSTONE CAPITAL LLC"


def test_ny_row_to_filing_rejects_header_like_rows():
    scraper = NewYorkScraper()
    profile = NY_SEARCH_PROFILES["debtor_org_sw"]
    assert (
        scraper._row_to_filing(
            ["Lien Number", "Serial"],
            profile=profile,
            search_term="A",
            secured_party_col=None,
        )
        is None
    )


def test_parse_ny_profiles_from_env_string():
    parsed = parse_profile_list(
        "secured_party_org_sw, debtor_org_sw, unknown",
        valid=NY_SEARCH_PROFILES,
    )
    assert parsed == ("secured_party_org_sw", "debtor_org_sw")


def test_prefix_queue_slice_rotates():
    terms = ("A", "B", "C", "D")
    batch, nxt = slice_prefix_terms(terms, offset=2, max_terms=2)
    assert batch == ["C", "D"]
    assert nxt == 0


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
        assert await get_page_checkpoint("NY", "debtor_org_sw", "ONDECK") == 0
        await save_page_checkpoint("NY", "debtor_org_sw", "ONDECK", 2)
        save_cp.assert_called_once_with(
            "NY", search_profile_key("debtor_org_sw", "ONDECK"), 2
        )
        get_cp.assert_called_once()


def test_load_playwright_scrape_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("NY_SCRAPE_MAX_PAGES", "7")
    monkeypatch.setenv("NY_SCRAPE_MAX_TERMS", "4")
    monkeypatch.setenv(
        "NY_SCRAPE_SEARCH_PROFILES", "secured_party_org_sw,debtor_org_sw"
    )
    settings = load_playwright_scrape_settings("NY")
    assert settings.max_pages == 7
    assert settings.max_terms == 4
    assert settings.search_profiles == ("secured_party_org_sw", "debtor_org_sw")
    assert settings.mca_term_limit == 100


def test_ny_fixture_html_has_grid():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "fixtures/playwright_tier1/ny_grid_page1.html"
    )
    soup = BeautifulSoup(path.read_text(), "html.parser")
    rows = soup.select("#xhtml_grid tbody tr")
    assert len(rows) == 2
    assert "Page 1 / 2" in path.read_text()


def test_ny_grid_sp_column_fixture():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "fixtures/playwright_tier1/ny_grid_with_sp_column.html"
    )
    soup = BeautifulSoup(path.read_text(), "html.parser")
    headers = [th.get_text(strip=True).lower() for th in soup.select("#xhtml_grid thead th")]
    assert any("secured" in h for h in headers)
    scraper = NewYorkScraper()
    col = scraper._secured_party_column(headers)
    assert col == 7


def test_detail_fixture_parses_secured_party():
    path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "fixtures/playwright_tier1/ny_detail.html"
    )
    parsed = parse_detail_fields_from_text(path.read_text())
    assert parsed["secured_party"] == "YELLOWSTONE CAPITAL LLC"
    assert parsed["filing_date"] is not None


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
            search_profiles=("secured_party_org_sw",),
        )
    )
    assert scraper._effective_max_pages() == 3


@pytest.mark.asyncio
async def test_ny_pagination_mock_two_pages():
    """Mock grid extraction across two pages without Chromium."""
    scraper = NewYorkScraper(
        scrape_settings=PlaywrightScrapeSettings(
            max_pages=10,
            max_terms=1,
            fetch_detail=False,
            mca_term_limit=5,
            extra_search_terms=(),
            search_profiles=("debtor_org_sw",),
            profile_filter="debtor_org_sw",
        )
    )
    profile = NY_SEARCH_PROFILES["debtor_org_sw"]
    page_calls = {"n": 0, "eval": 0}
    grid_pages = [
        {
            "headers": [],
            "rows": [
                [
                    "2024000001",
                    "1",
                    "UC",
                    "ACME",
                    "",
                    "Org",
                    "3/15/2024",
                    "",
                    "Active",
                ]
            ],
        },
        {
            "headers": [],
            "rows": [
                [
                    "2024000002",
                    "2",
                    "UC",
                    "BETA",
                    "",
                    "Org",
                    "4/01/2024",
                    "",
                    "Active",
                ]
            ],
        },
    ]

    page = MagicMock()

    async def _evaluate(js: str):
        if "tbody tr" in js and "headers" not in js:
            return True
        page_calls["eval"] += 1
        return grid_pages[min(page_calls["eval"] - 1, 1)]

    page.evaluate = _evaluate

    async def _next(_page):
        page_calls["n"] += 1
        return page_calls["n"] < 2

    with patch(
        "app.scrapers.states.new_york.get_page_checkpoint",
        AsyncMock(return_value=0),
    ), patch(
        "app.scrapers.states.new_york.save_page_checkpoint",
        AsyncMock(),
    ), patch(
        "app.scrapers.states.new_york.xhtml_grid_next_page",
        side_effect=_next,
    ), patch.object(
        scraper, "_submit_lien_search", AsyncMock()
    ):
        rows, pages = await scraper._search_term_paginated(
            page, profile, "A", pages_remaining=5
        )

    assert pages == 2
    assert len(rows) == 2
    assert {r["filing_number"] for r in rows} == {"2024000001", "2024000002"}
