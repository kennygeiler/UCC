"""Playwright-based scraper base for JS-rendered SOS portals.

Extends BaseScraper to use Playwright instead of httpx for states
that require JavaScript execution to render search results.
"""

from contextlib import asynccontextmanager

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper
from app.logging import get_logger

logger = get_logger("playwright_scraper")

_DEFAULT_PLAYWRIGHT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class PlaywrightBaseScraper(BaseScraper):
    """Base class for scrapers requiring a headless browser.

    Overrides _fetch to use Playwright instead of httpx.
    Subclasses still implement parse_response, build_search_url, etc.
    """

    # Subclasses can override to wait for a specific selector before extracting HTML
    wait_for_selector: str | None = None
    # Max time in ms to wait for page load / selector
    page_timeout: int = 30_000

    @asynccontextmanager
    async def playwright_chromium_session(
        self,
        *,
        launch_args: list[str] | None = None,
        user_agent: str | None = None,
    ):
        """Yield a Playwright ``Page`` for custom scrape flows (WAF + in-page API).

        Does not call ``rate_limiter.wait`` — callers run it before entering
        this context (e.g. California multi-step scrape).
        """
        async with async_playwright() as p:
            launch_kw: dict = {"headless": True}
            if launch_args:
                launch_kw["args"] = launch_args
            browser = await p.chromium.launch(**launch_kw)
            try:
                ua = user_agent or _DEFAULT_PLAYWRIGHT_UA
                context = await browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()
                yield page
            finally:
                await browser.close()

    async def _fetch(self) -> str:
        """Fetch HTML using Playwright headless Chromium.

        Navigates to the search URL, waits for JS rendering,
        and returns the fully rendered DOM as HTML.

        Returns:
            Rendered HTML content after JavaScript execution.
        """
        await self.rate_limiter.wait(self.state_code, tier=self.tier)
        url = self.build_search_url()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=self.page_timeout)
                if self.wait_for_selector:
                    await page.wait_for_selector(
                        self.wait_for_selector, timeout=self.page_timeout
                    )
                html = await page.content()
            finally:
                await browser.close()

        self.rate_limiter.record_success(self.state_code)
        logger.info(
            "playwright_fetch_complete",
            state=self.state_code,
            url=url,
        )
        return html
