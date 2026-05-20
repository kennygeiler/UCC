"""Unit tests for Playwright Tier 1 grid pagination helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.playwright_tier1.pagination import (
    read_pager_info,
    xhtml_grid_goto_last_page,
    xhtml_grid_goto_page,
    xhtml_grid_prev_page,
)
from app.scrapers.playwright_tier1.profiles import NY_SEARCH_PROFILES
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings, load_playwright_scrape_settings
from app.scrapers.states.new_york import NewYorkScraper


@pytest.mark.asyncio
async def test_read_pager_info_parses_page_footer():
    page = MagicMock()
    page.evaluate = AsyncMock(return_value={"current": 2, "total": 5})
    current, total = await read_pager_info(page, "#xhtml_grid")
    assert current == 2
    assert total == 5


@pytest.mark.asyncio
async def test_xhtml_grid_goto_page_waits_for_network():
    page = MagicMock()
    page.evaluate = AsyncMock(return_value=True)
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    assert await xhtml_grid_goto_page(page, 3) is True
    page.evaluate.assert_awaited_once()
    page.wait_for_load_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_xhtml_grid_goto_last_page_jumps_to_total():
    page = MagicMock()
    with patch(
        "app.scrapers.playwright_tier1.pagination.read_pager_info",
        AsyncMock(return_value=(1, 4)),
    ), patch(
        "app.scrapers.playwright_tier1.pagination.xhtml_grid_goto_page",
        AsyncMock(return_value=True),
    ) as goto:
        total = await xhtml_grid_goto_last_page(page)
    assert total == 4
    goto.assert_awaited_once_with(page, 4)


@pytest.mark.asyncio
async def test_xhtml_grid_goto_last_page_single_page_no_click():
    page = MagicMock()
    with patch(
        "app.scrapers.playwright_tier1.pagination.read_pager_info",
        AsyncMock(return_value=(1, 1)),
    ), patch(
        "app.scrapers.playwright_tier1.pagination.xhtml_grid_goto_page",
        AsyncMock(),
    ) as goto:
        total = await xhtml_grid_goto_last_page(page)
    assert total == 1
    goto.assert_not_awaited()


@pytest.mark.asyncio
async def test_xhtml_grid_prev_page_returns_false_when_stuck():
    page = MagicMock()
    page.evaluate = AsyncMock(return_value=False)
    assert await xhtml_grid_prev_page(page) is False


@pytest.mark.asyncio
async def test_ny_reverse_pagination_mock_three_pages():
    """Reverse walk from last page with checkpoint resume semantics."""
    scraper = NewYorkScraper(
        scrape_settings=PlaywrightScrapeSettings(
            max_pages=10,
            max_terms=1,
            fetch_detail=False,
            mca_term_limit=5,
            extra_search_terms=(),
            search_profiles=("debtor_org_sw",),
            profile_filter="debtor_org_sw",
            page_order="reverse",
        )
    )
    profile = NY_SEARCH_PROFILES["debtor_org_sw"]
    pager_state = {"current": 3, "total": 3}
    grid_by_page = {
        3: {"headers": [], "rows": [["2024000003", "3", "UC", "GAMMA", "", "Org", "6/01/2024", "", "Active"]]},
        2: {"headers": [], "rows": [["2024000002", "2", "UC", "BETA", "", "Org", "4/01/2024", "", "Active"]]},
        1: {"headers": [], "rows": [["2024000001", "1", "UC", "ACME", "", "Org", "3/15/2024", "", "Active"]]},
    }
    page = MagicMock()

    async def _evaluate(js: str, *args):
        if "tbody tr" in js and "headers" not in js:
            return True
        if "PAGER_PAGE_INFO" in js or "gridSelector" in js or args:
            if "gridSelector" in str(js) or (args and isinstance(args[0], str)):
                return {"current": pager_state["current"], "total": pager_state["total"]}
        return grid_by_page.get(pager_state["current"], {"headers": [], "rows": []})

    page.evaluate = _evaluate

    async def _goto_last(_page, _sel="#xhtml_grid"):
        pager_state["current"] = pager_state["total"]
        return pager_state["total"]

    async def _goto_page(_page, n: int):
        pager_state["current"] = n
        return True

    async def _prev(_page):
        if pager_state["current"] <= 1:
            return False
        pager_state["current"] -= 1
        return True

    with patch(
        "app.scrapers.states.new_york.get_page_checkpoint",
        AsyncMock(return_value=0),
    ), patch(
        "app.scrapers.states.new_york.save_page_checkpoint",
        AsyncMock(),
    ), patch(
        "app.scrapers.states.new_york.read_pager_info",
        AsyncMock(side_effect=lambda _p, _g: (pager_state["current"], pager_state["total"])),
    ), patch(
        "app.scrapers.states.new_york.xhtml_grid_goto_last_page",
        side_effect=_goto_last,
    ), patch(
        "app.scrapers.states.new_york.xhtml_grid_goto_page",
        side_effect=_goto_page,
    ), patch(
        "app.scrapers.states.new_york.xhtml_grid_prev_page",
        side_effect=_prev,
    ), patch.object(scraper, "_submit_lien_search", AsyncMock()):
        rows, pages = await scraper._search_term_paginated(
            page, profile, "A", pages_remaining=5
        )

    assert pages == 3
    assert len(rows) == 3
    assert {r["filing_number"] for r in rows} == {
        "2024000001",
        "2024000002",
        "2024000003",
    }


@pytest.mark.asyncio
async def test_ny_recent_only_caps_page_budget():
    scraper = NewYorkScraper(
        scrape_settings=PlaywrightScrapeSettings(
            max_pages=50,
            max_terms=1,
            fetch_detail=False,
            mca_term_limit=5,
            extra_search_terms=(),
            search_profiles=("debtor_org_sw",),
            page_order="recent_only",
            recent_pages=2,
        )
    )
    assert scraper._page_budget_for_term(None) == 2


def test_load_ny_page_order_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("NY_SCRAPE_PAGE_ORDER", "recent_only")
    monkeypatch.setenv("NY_SCRAPE_RECENT_PAGES", "7")
    s = load_playwright_scrape_settings("NY")
    assert s.page_order == "recent_only"
    assert s.recent_pages == 7


def test_load_ny_invalid_page_order_falls_back_forward(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("NY_SCRAPE_PAGE_ORDER", "sideways")
    s = load_playwright_scrape_settings("NY")
    assert s.page_order == "forward"
