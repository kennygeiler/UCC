"""Search profile definitions for Playwright Tier 1 multi-mode scrapes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PartySearchMode(str, Enum):
    """Which party field the portal search targets."""

    DEBTOR = "debtor"
    SECURED = "secured"


class TermSource(str, Enum):
    """How search terms are chosen for a profile."""

    MCA_ALIASES = "mca"
    PREFIX_QUEUE = "prefix"


@dataclass(frozen=True)
class SearchProfileSpec:
    """One named portal search configuration."""

    name: str
    party_mode: PartySearchMode
    search_logic: str  # SW = starts with, BW = begins with (portal-specific)
    term_source: TermSource


# NY Cenuity lien search profiles (see new_york.py portal recon comments).
# The NY public portal only supports Filing-Number and Debtor-Name search —
# there is no secured-party search. Profiles are therefore debtor-only; the
# secured party is read from each lien's detail page.
NY_SEARCH_PROFILES: dict[str, SearchProfileSpec] = {
    "debtor_org_sw": SearchProfileSpec(
        name="debtor_org_sw",
        party_mode=PartySearchMode.DEBTOR,
        search_logic="SW",
        term_source=TermSource.PREFIX_QUEUE,
    ),
    "debtor_org_bw": SearchProfileSpec(
        name="debtor_org_bw",
        party_mode=PartySearchMode.DEBTOR,
        search_logic="BW",
        term_source=TermSource.PREFIX_QUEUE,
    ),
}

DEFAULT_NY_SEARCH_PROFILES: tuple[str, ...] = ("debtor_org_sw",)

# Legacy single-profile key for NJ/CA/TX until they enable *_SCRAPE_SEARCH_PROFILES.
DEFAULT_LEGACY_PROFILE = "search"


def default_prefix_terms() -> tuple[str, ...]:
    """A–Z, 0–9, and common org suffix tokens for debtor prefix sweeps."""
    letters = tuple(chr(c) for c in range(ord("A"), ord("Z") + 1))
    digits = tuple(str(d) for d in range(10))
    suffixes = ("LLC", "INC", "CORP")
    return letters + digits + suffixes


def parse_profile_list(raw: str, *, valid: dict[str, SearchProfileSpec]) -> tuple[str, ...]:
    """Parse comma-separated profile names; ignore unknown entries."""
    if not raw.strip():
        return ()
    names: list[str] = []
    for part in raw.split(","):
        key = part.strip()
        if key and key in valid and key not in names:
            names.append(key)
    return tuple(names)


def parse_prefix_terms(raw: str) -> tuple[str, ...]:
    """Parse ``NY_SCRAPE_PREFIX_TERMS`` (comma-separated)."""
    if not raw.strip():
        return default_prefix_terms()
    return tuple(t.strip().upper() for t in raw.split(",") if t.strip())
