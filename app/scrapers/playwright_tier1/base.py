"""Playwright Tier 1 scraper base — browser session, terms, checkpoints."""

from __future__ import annotations

from app.scrapers.base_enriched import PostScrapeScraper
from app.scrapers.playwright_base import PlaywrightBaseScraper
from app.scrapers.playwright_tier1.search_terms import build_search_term_list
from app.scrapers.playwright_tier1.settings import (
    PlaywrightScrapeSettings,
    load_playwright_scrape_settings,
)
from app.logging import get_logger

logger = get_logger("playwright_tier1")


class PlaywrightTier1Scraper(PostScrapeScraper, PlaywrightBaseScraper):
    """Shared Playwright Tier 1 flow: terms, caps, upsert, post-scrape pipeline."""

    scrape_settings: PlaywrightScrapeSettings

    def __init__(
        self,
        rate_limiter=None,
        *,
        run_consolidation: bool = True,
        scrape_settings: PlaywrightScrapeSettings | None = None,
    ) -> None:
        PostScrapeScraper.__init__(self, rate_limiter=rate_limiter)
        PlaywrightBaseScraper.__init__(self, rate_limiter=rate_limiter)
        self.run_consolidation = run_consolidation
        self.scrape_settings = scrape_settings or load_playwright_scrape_settings(
            self.state_code
        )

    async def _load_search_terms(self) -> list[str]:
        s = self.scrape_settings
        return await build_search_term_list(
            mca_limit=s.mca_term_limit,
            extra_terms=s.extra_search_terms,
            max_terms=s.max_terms,
        )

    async def scrape(self) -> int:
        """Execute scrape with persist + post-scrape pipeline."""
        run = await self._start_run()
        try:
            filings = await self._fetch_filings_playwright()
            return await self._finish_scrape_run(run, filings)
        except Exception as exc:
            await self._fail_run(run, exc)
            raise

    async def _fetch_filings_playwright(self) -> list[dict]:
        """Subclasses implement portal-specific collection."""
        raise NotImplementedError

    def _effective_max_pages(self) -> int:
        s = self.scrape_settings
        if s.page_cap_per_run is not None:
            return min(s.max_pages, s.page_cap_per_run)
        return s.max_pages
