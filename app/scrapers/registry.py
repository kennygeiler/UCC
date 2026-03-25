"""Explicit registry mapping state codes to scraper classes and tiers."""

from app.scrapers.states.california import CaliforniaScraper
from app.scrapers.states.florida import FloridaScraper
from app.scrapers.states.georgia import GeorgiaScraper
from app.scrapers.states.illinois import IllinoisScraper
from app.scrapers.states.maryland import MarylandScraper
from app.scrapers.states.new_jersey import NewJerseyScraper
from app.scrapers.states.new_york import NewYorkScraper
from app.scrapers.states.ohio import OhioScraper
from app.scrapers.states.pennsylvania import PennsylvaniaScraper
from app.scrapers.states.texas import TexasScraper

# Explicit mapping of state codes to (scraper_class, tier).
# No dynamic imports — all Tier 1 states registered here.
SCRAPER_REGISTRY: dict[str, dict] = {
    "CA": {"class": CaliforniaScraper, "tier": 1},
    "TX": {"class": TexasScraper, "tier": 1},
    "FL": {"class": FloridaScraper, "tier": 1},
    "NY": {"class": NewYorkScraper, "tier": 1},
    "NJ": {"class": NewJerseyScraper, "tier": 1},
    "GA": {"class": GeorgiaScraper, "tier": 1},
    "IL": {"class": IllinoisScraper, "tier": 1},
    "PA": {"class": PennsylvaniaScraper, "tier": 1},
    "OH": {"class": OhioScraper, "tier": 1},
    "MD": {"class": MarylandScraper, "tier": 1},
}


def get_scraper_class(state_code: str) -> type | None:
    """Return the scraper class for a given state code, or None if not registered.

    Args:
        state_code: Two-letter state code.

    Returns:
        Scraper class or None.
    """
    entry = SCRAPER_REGISTRY.get(state_code)
    return entry["class"] if entry else None


def get_tier1_states() -> list[str]:
    """Return all state codes registered as tier 1.

    Returns:
        List of two-letter state codes.
    """
    return [code for code, info in SCRAPER_REGISTRY.items() if info["tier"] == 1]
