"""Tier 1 scraper readiness, env defaults, and operator metadata."""

from __future__ import annotations

from enum import Enum

# Keep in sync with registry Tier 1 entries (avoid importing registry — circular).
TIER1_STATE_CODES: tuple[str, ...] = (
    "CA",
    "FL",
    "GA",
    "IL",
    "MD",
    "NJ",
    "NY",
    "OH",
    "PA",
    "TX",
)


class ScraperReadiness(str, Enum):
    """Operator-facing scrape capability for a Tier 1 state."""

    READY = "ready"  # Full deep scrape + post-pipeline (Florida REST API)
    PLAYWRIGHT = "playwright"  # Playwright/API scrape + post-pipeline
    NOT_READY = "not_ready"  # Registered placeholder — do not run live scrape


# Per-state readiness (honest UX — no fake HTML stub success).
TIER1_READINESS: dict[str, ScraperReadiness] = {
    "FL": ScraperReadiness.READY,
    "CA": ScraperReadiness.PLAYWRIGHT,
    "TX": ScraperReadiness.PLAYWRIGHT,
    "NY": ScraperReadiness.PLAYWRIGHT,
    "NJ": ScraperReadiness.PLAYWRIGHT,
    "GA": ScraperReadiness.NOT_READY,
    "IL": ScraperReadiness.NOT_READY,
    "OH": ScraperReadiness.NOT_READY,
    "MD": ScraperReadiness.NOT_READY,
    "PA": ScraperReadiness.NOT_READY,
}

TIER1_OPERATOR_NOTES: dict[str, str] = {
    "FL": "REST API deep pagination, secured-party enrichment, checkpoints.",
    "CA": "Playwright + bizfile JSON API; secured_party from search rows.",
    "TX": "Playwright Harris County + optional SOS tracker merge.",
    "NY": "Playwright lien search; secured_party not on results grid (debtor-only).",
    "NJ": "Playwright non-certified search; secured_party not on results grid.",
    "GA": "HTML stub URL not live — needs GA eCorp UCC portal research.",
    "IL": "HTML stub URL not live — needs IL SOS UCC portal research.",
    "OH": "HTML stub URL not live — needs OH SOS UCC portal research.",
    "MD": "HTML stub URL not live — needs MD SDAT UCC portal research.",
    "PA": "HTML stub URL not live — needs PA DOS UCC portal research.",
}

# Env prefix optional overrides (page caps, etc.) — see Settings / scraper __init__.
TIER1_ENV_PREFIX: dict[str, str] = {
    "FL": "FL_SCRAPE",
    "CA": "CA_SCRAPE",
    "TX": "TX_SCRAPE",
    "NY": "NY_SCRAPE",
    "NJ": "NJ_SCRAPE",
}


def tier1_readiness(state_code: str) -> ScraperReadiness | None:
    """Return readiness for a Tier 1 state, or None if not Tier 1."""
    code = state_code.strip().upper()
    return TIER1_READINESS.get(code)


def is_tier1_runnable(state_code: str) -> bool:
    """True when manual scrape + post-pipeline is supported."""
    readiness = tier1_readiness(state_code)
    return readiness in (ScraperReadiness.READY, ScraperReadiness.PLAYWRIGHT)


def tier1_not_ready_reason(state_code: str) -> str:
    """Human-readable blocker for NOT_READY states."""
    code = state_code.strip().upper()
    return TIER1_OPERATOR_NOTES.get(
        code,
        f"{code} scraper is not implemented yet.",
    )


def list_tier1_ready_states() -> list[str]:
    """State codes that can run end-to-end scrape → accounts today."""
    return sorted(
        code
        for code in TIER1_STATE_CODES
        if TIER1_READINESS.get(code) in (ScraperReadiness.READY, ScraperReadiness.PLAYWRIGHT)
    )


def tier1_dashboard_row(state_code: str) -> dict:
    """Single row for dashboard Tier 1 table."""
    code = state_code.strip().upper()
    readiness = TIER1_READINESS.get(code, ScraperReadiness.NOT_READY)
    return {
        "state": code,
        "readiness": readiness.value,
        "runnable": is_tier1_runnable(code),
        "notes": TIER1_OPERATOR_NOTES.get(code, ""),
        "env_prefix": TIER1_ENV_PREFIX.get(code),
    }


def all_tier1_dashboard_rows() -> list[dict]:
    """All Tier 1 states for dashboard (sorted by code)."""
    return [tier1_dashboard_row(code) for code in TIER1_STATE_CODES]
