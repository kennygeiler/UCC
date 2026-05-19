"""Georgia SOS UCC filing scraper — not yet implemented (Tier 1 placeholder)."""

from app.scrapers.tier1_not_ready import Tier1NotReadyScraper


class GeorgiaScraper(Tier1NotReadyScraper):
    """Georgia UCC scraper placeholder until eCorp portal integration."""

    @property
    def state_code(self) -> str:
        return "GA"
