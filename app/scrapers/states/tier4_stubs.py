"""Tier 4 placeholder scrapers (DC, NYC) — no live SOS ingestion in v1 (C-17).

Registered for visibility and future work; `scrape()` returns immediately without HTTP.
"""

from app.scrapers.base import BaseScraper
from app.logging import get_logger

logger = get_logger("tier4_stub")


class DistrictColumbiaStubScraper(BaseScraper):
    """District of Columbia — Tier 4 stub (portal not implemented in v1)."""

    @property
    def state_code(self) -> str:
        return "DC"

    @property
    def tier(self) -> int:
        return 4

    @property
    def base_url(self) -> str:
        return "https://example.invalid/tier4-dc"

    @property
    def column_map(self) -> dict[str, int]:
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        return []

    async def scrape(self) -> int:
        """No-op: Tier 4 is not scheduled for production scrapes."""
        logger.info(
            "tier4_skipped",
            component="scraper",
            status="skipped",
            state=self.state_code,
        )
        return 0


class NewYorkCityStubScraper(BaseScraper):
    """NYC-specific portal (distinct from NY state) — Tier 4 stub for v1."""

    @property
    def state_code(self) -> str:
        return "NYC"

    @property
    def tier(self) -> int:
        return 4

    @property
    def base_url(self) -> str:
        return "https://example.invalid/tier4-nyc"

    @property
    def column_map(self) -> dict[str, int]:
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        return []

    async def scrape(self) -> int:
        """No-op: Tier 4 is not scheduled for production scrapes."""
        logger.info(
            "tier4_skipped",
            component="scraper",
            status="skipped",
            state=self.state_code,
        )
        return 0
