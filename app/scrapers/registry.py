"""Explicit registry mapping state codes to scraper classes and tiers."""

# Tier 1 — Top 10 MCA states (~80% volume), daily scrape
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

# Tier 2 — 24 states, daily-to-48h scrape
from app.scrapers.states.alabama import AlabamaScraper
from app.scrapers.states.arizona import ArizonaScraper
from app.scrapers.states.arkansas import ArkansasScraper
from app.scrapers.states.colorado import ColoradoScraper
from app.scrapers.states.connecticut import ConnecticutScraper
from app.scrapers.states.indiana import IndianaScraper
from app.scrapers.states.iowa import IowaScraper
from app.scrapers.states.kansas import KansasScraper
from app.scrapers.states.kentucky import KentuckyScraper
from app.scrapers.states.louisiana import LouisianaScraper
from app.scrapers.states.massachusetts import MassachusettsScraper
from app.scrapers.states.michigan import MichiganScraper
from app.scrapers.states.minnesota import MinnesotaScraper
from app.scrapers.states.mississippi import MississippiScraper
from app.scrapers.states.missouri import MissouriScraper
from app.scrapers.states.nebraska import NebraskaScraper
from app.scrapers.states.north_carolina import NorthCarolinaScraper
from app.scrapers.states.oklahoma import OklahomaScraper
from app.scrapers.states.oregon import OregonScraper
from app.scrapers.states.south_carolina import SouthCarolinaScraper
from app.scrapers.states.tennessee import TennesseeScraper
from app.scrapers.states.virginia import VirginiaScraper
from app.scrapers.states.washington import WashingtonScraper
from app.scrapers.states.wisconsin import WisconsinScraper

# Tier 3 — 6 problem states needing proxy rotation, 48h+ scrape
from app.scrapers.states.delaware import DelawareScraper
from app.scrapers.states.hawaii import HawaiiScraper
from app.scrapers.states.nevada import NevadaScraper
from app.scrapers.states.new_hampshire import NewHampshireScraper
from app.scrapers.states.rhode_island import RhodeIslandScraper
from app.scrapers.states.utah import UtahScraper

# Explicit mapping — no dynamic imports (P-019)
SCRAPER_REGISTRY: dict[str, dict] = {
    # Tier 1
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
    # Tier 2
    "AL": {"class": AlabamaScraper, "tier": 2},
    "AZ": {"class": ArizonaScraper, "tier": 2},
    "AR": {"class": ArkansasScraper, "tier": 2},
    "CO": {"class": ColoradoScraper, "tier": 2},
    "CT": {"class": ConnecticutScraper, "tier": 2},
    "IN": {"class": IndianaScraper, "tier": 2},
    "IA": {"class": IowaScraper, "tier": 2},
    "KS": {"class": KansasScraper, "tier": 2},
    "KY": {"class": KentuckyScraper, "tier": 2},
    "LA": {"class": LouisianaScraper, "tier": 2},
    "MA": {"class": MassachusettsScraper, "tier": 2},
    "MI": {"class": MichiganScraper, "tier": 2},
    "MN": {"class": MinnesotaScraper, "tier": 2},
    "MS": {"class": MississippiScraper, "tier": 2},
    "MO": {"class": MissouriScraper, "tier": 2},
    "NE": {"class": NebraskaScraper, "tier": 2},
    "NC": {"class": NorthCarolinaScraper, "tier": 2},
    "OK": {"class": OklahomaScraper, "tier": 2},
    "OR": {"class": OregonScraper, "tier": 2},
    "SC": {"class": SouthCarolinaScraper, "tier": 2},
    "TN": {"class": TennesseeScraper, "tier": 2},
    "VA": {"class": VirginiaScraper, "tier": 2},
    "WA": {"class": WashingtonScraper, "tier": 2},
    "WI": {"class": WisconsinScraper, "tier": 2},
    # Tier 3
    "NH": {"class": NewHampshireScraper, "tier": 3},
    "RI": {"class": RhodeIslandScraper, "tier": 3},
    "DE": {"class": DelawareScraper, "tier": 3},
    "HI": {"class": HawaiiScraper, "tier": 3},
    "NV": {"class": NevadaScraper, "tier": 3},
    "UT": {"class": UtahScraper, "tier": 3},
}


def get_scraper_class(state_code: str) -> type | None:
    """Return the scraper class for a given state code, or None.

    Args:
        state_code: Two-letter state code.
    """
    entry = SCRAPER_REGISTRY.get(state_code)
    return entry["class"] if entry else None


def get_states_by_tier(tier: int) -> list[str]:
    """Return all state codes for a given tier.

    Args:
        tier: Tier number (1, 2, or 3).
    """
    return [code for code, info in SCRAPER_REGISTRY.items() if info["tier"] == tier]
