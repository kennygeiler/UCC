"""Maryland SDAT UCC filing scraper — not yet implemented (Tier 1 placeholder)."""

from app.scrapers.tier1_not_ready import Tier1NotReadyScraper


class MarylandScraper(Tier1NotReadyScraper):
    """Maryland UCC scraper placeholder until SDAT portal integration."""

    @property
    def state_code(self) -> str:
        return "MD"
