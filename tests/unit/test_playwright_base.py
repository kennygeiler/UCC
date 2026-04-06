"""Unit tests for PlaywrightBaseScraper (mocked Playwright, no browser)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.playwright_base import PlaywrightBaseScraper
from app.scrapers.rate_limiter import RateLimiter


class _MinimalPW(PlaywrightBaseScraper):
    @property
    def state_code(self) -> str:
        return "TS"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return "https://example.test/ucc"

    @property
    def column_map(self) -> dict[str, int]:
        return {"filing_number": 0, "debtor_name": 1}

    def build_search_url(self) -> str:
        return f"{self.base_url}?q=1"

    def parse_response(self, html: str) -> list[dict]:
        return []


class _FakeAsyncPlaywrightCtx:
    """Stand-in for ``async with async_playwright() as p``."""

    def __init__(self, playwright_api: MagicMock) -> None:
        self._playwright_api = playwright_api

    async def __aenter__(self):
        return self._playwright_api

    async def __aexit__(self, *args):
        return None


def _patch_playwright(mock_p: MagicMock):
    """Return a patch target so ``async_playwright()`` yields ``mock_p``."""

    def _factory():
        return _FakeAsyncPlaywrightCtx(mock_p)

    return patch("app.scrapers.playwright_base.async_playwright", side_effect=_factory)


@pytest.mark.asyncio
async def test_fetch_calls_rate_limiter_wait_before_launch():
    """_fetch waits on rate limiter before Playwright launch."""
    rl = RateLimiter(base_delay=0.0, jitter_pct=0.0)
    scraper = _MinimalPW(rate_limiter=rl)
    wait_mock = AsyncMock()
    scraper.rate_limiter.wait = wait_mock

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html></html>")

    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_p = MagicMock()
    mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

    with _patch_playwright(mock_p):
        await scraper._fetch()

    wait_mock.assert_awaited_once()
    mock_p.chromium.launch.assert_awaited_once()


@pytest.mark.asyncio
async def test_playwright_chromium_session_yields_page():
    """playwright_chromium_session yields a page and closes the browser."""
    scraper = _MinimalPW(rate_limiter=RateLimiter(base_delay=0.0, jitter_pct=0.0))
    mock_page = MagicMock()

    mock_browser = AsyncMock()
    mock_browser.close = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_p = MagicMock()
    mock_p.chromium.launch = AsyncMock(return_value=mock_browser)

    with _patch_playwright(mock_p):
        async with scraper.playwright_chromium_session() as page:
            assert page is mock_page

    mock_browser.close.assert_awaited()
