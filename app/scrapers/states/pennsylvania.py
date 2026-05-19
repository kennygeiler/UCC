"""Pennsylvania DOS UCC filing scraper — not yet implemented (Tier 1 placeholder)."""

from app.scrapers.tier1_not_ready import Tier1NotReadyScraper


class PennsylvaniaScraper(Tier1NotReadyScraper):
    """Pennsylvania UCC scraper placeholder until PA DOS portal integration."""

    @property
    def state_code(self) -> str:
        return "PA"
