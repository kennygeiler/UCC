"""Ohio SOS UCC filing scraper — not yet implemented (Tier 1 placeholder)."""

from app.scrapers.tier1_not_ready import Tier1NotReadyScraper


class OhioScraper(Tier1NotReadyScraper):
    """Ohio UCC scraper placeholder until OH SOS portal integration."""

    @property
    def state_code(self) -> str:
        return "OH"
