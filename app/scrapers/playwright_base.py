"""Playwright-based scraper base for JS-rendered SOS portals.

Extends BaseScraper to use Playwright instead of httpx for states
that require JavaScript execution to render search results.
Actual Playwright scraper implementations are a future concern.
"""

from app.scrapers.base import BaseScraper


class PlaywrightBaseScraper(BaseScraper):
    """Base class for scrapers requiring a headless browser.

    Overrides _fetch to use Playwright instead of httpx.
    Subclasses still implement parse_response, build_search_url, etc.
    """

    async def _fetch(self) -> str:
        """Fetch HTML using Playwright headless browser.

        Returns:
            Rendered HTML content after JavaScript execution.

        Raises:
            NotImplementedError: Playwright integration pending M10.
        """
        raise NotImplementedError(
            "Playwright scraper support is stubbed for future implementation. "
            "Use httpx-based scrapers for Tier 1-3 states."
        )
