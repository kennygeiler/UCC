"""Base for Tier 1 states without a live portal implementation yet."""

from __future__ import annotations

from abc import abstractmethod

from app.scrapers.base import BaseScraper
from app.scrapers.exceptions import ScraperNotReadyError


class Tier1NotReadyScraper(BaseScraper):
    """Registered scraper that refuses to fake HTML stub success.

    Dashboard shows *not implemented*; ``scrape()`` records a failed run with detail.
    """

    @property
    @abstractmethod
    def state_code(self) -> str:
        """Two-letter state code."""

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        # Placeholder for registry/smoke URL checks — ``scrape()`` never HTTP-fetches.
        return f"https://ucc-scraper-not-ready.invalid/{self.state_code.lower()}"

    @property
    def column_map(self) -> dict[str, int]:
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        return []

    async def scrape(self) -> int:
        from app.scrapers.state_config import tier1_not_ready_reason

        reason = tier1_not_ready_reason(self.state_code)
        run = await self._start_run()
        exc = ScraperNotReadyError(self.state_code, reason)
        await self._fail_run(run, exc)
        raise exc
