"""Illinois SOS UCC filing scraper — not yet implemented (Tier 1 placeholder)."""

from app.scrapers.tier1_not_ready import Tier1NotReadyScraper


class IllinoisScraper(Tier1NotReadyScraper):
    """Illinois UCC scraper placeholder until IL SOS portal integration."""

    @property
    def state_code(self) -> str:
        return "IL"
