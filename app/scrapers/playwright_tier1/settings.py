"""Env-backed scrape caps for Playwright Tier 1 states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import Settings

PageOrder = Literal["forward", "reverse", "recent_only"]
VALID_PAGE_ORDERS: frozenset[str] = frozenset({"forward", "reverse", "recent_only"})
from app.scrapers.playwright_tier1.profiles import (
    DEFAULT_LEGACY_PROFILE,
    DEFAULT_NY_SEARCH_PROFILES,
    NY_SEARCH_PROFILES,
    default_prefix_terms,
    parse_prefix_terms,
    parse_profile_list,
)


@dataclass(frozen=True)
class PlaywrightScrapeSettings:
    """Runtime caps for one Playwright Tier 1 state scrape."""

    max_pages: int
    max_terms: int
    fetch_detail: bool
    mca_term_limit: int
    extra_search_terms: tuple[str, ...]
    page_cap_per_run: int | None = None
    search_profiles: tuple[str, ...] = ()
    prefix_terms: tuple[str, ...] = ()
    profile_filter: str | None = None
    page_order: PageOrder = "forward"
    recent_pages: int = 10


def load_playwright_scrape_settings(state_code: str) -> PlaywrightScrapeSettings:
    """Load caps: ``PLAYWRIGHT_SCRAPE_*`` with ``{STATE}_SCRAPE_*`` overrides."""
    code = state_code.strip().upper()
    prefix = f"{code}_SCRAPE"
    try:
        settings = Settings()
    except Exception:
        settings = None

    def _get_int(generic_attr: str, state_attr: str, default: int) -> int:
        if settings is None:
            return default
        state_v = getattr(settings, state_attr, None)
        if state_attr in type(settings).model_fields and state_v is not None:
            return int(state_v)
        return int(getattr(settings, generic_attr, default))

    def _get_bool(generic_attr: str, state_attr: str, default: bool) -> bool:
        if settings is None:
            return default
        if state_attr in type(settings).model_fields:
            return bool(getattr(settings, state_attr))
        return bool(getattr(settings, generic_attr, default))

    def _terms() -> tuple[str, ...]:
        if settings is None:
            return ()
        raw = ""
        if f"{prefix}_SEARCH_TERMS" in type(settings).model_fields:
            raw = (getattr(settings, f"{prefix}_SEARCH_TERMS") or "").strip()
        if not raw:
            raw = (getattr(settings, "PLAYWRIGHT_SCRAPE_SEARCH_TERMS", "") or "").strip()
        if not raw:
            return ()
        return tuple(t.strip() for t in raw.split(",") if t.strip())

    def _search_profiles() -> tuple[str, ...]:
        if settings is None:
            return () if code != "NY" else DEFAULT_NY_SEARCH_PROFILES
        attr = f"{prefix}_SEARCH_PROFILES"
        if attr in type(settings).model_fields:
            raw = (getattr(settings, attr) or "").strip()
            if code == "NY":
                parsed = parse_profile_list(raw, valid=NY_SEARCH_PROFILES)
                return parsed or DEFAULT_NY_SEARCH_PROFILES
            if raw:
                return tuple(p.strip() for p in raw.split(",") if p.strip())
        if code == "NY":
            return DEFAULT_NY_SEARCH_PROFILES
        return ()

    def _prefix_terms() -> tuple[str, ...]:
        if settings is None:
            return default_prefix_terms()
        attr = f"{prefix}_PREFIX_TERMS"
        if attr in type(settings).model_fields:
            raw = getattr(settings, attr) or ""
            return parse_prefix_terms(str(raw))
        return default_prefix_terms()

    max_pages = _get_int("PLAYWRIGHT_SCRAPE_MAX_PAGES", f"{prefix}_MAX_PAGES", 50)
    max_terms = _get_int("PLAYWRIGHT_SCRAPE_MAX_TERMS", f"{prefix}_MAX_TERMS", 20)
    mca_default = 200 if code == "NY" else 20
    mca_limit = _get_int("PLAYWRIGHT_SCRAPE_MCA_TERM_LIMIT", f"{prefix}_MCA_TERM_LIMIT", mca_default)
    fetch_detail = _get_bool("PLAYWRIGHT_SCRAPE_FETCH_DETAIL", f"{prefix}_FETCH_DETAIL", True)
    page_cap = None
    if settings and f"{prefix}_PAGE_CAP_PER_RUN" in type(settings).model_fields:
        raw_cap = getattr(settings, f"{prefix}_PAGE_CAP_PER_RUN")
        if raw_cap is not None:
            page_cap = int(raw_cap)

    profiles = _search_profiles()
    if not profiles and code not in ("NY",):
        profiles = (DEFAULT_LEGACY_PROFILE,)

    page_order: PageOrder = "forward"
    recent_pages = 10
    if settings and code == "NY":
        raw_order = (getattr(settings, "NY_SCRAPE_PAGE_ORDER", None) or "forward").strip().lower()
        if raw_order in VALID_PAGE_ORDERS:
            page_order = raw_order  # type: ignore[assignment]
        recent_pages = int(getattr(settings, "NY_SCRAPE_RECENT_PAGES", 10) or 10)

    return PlaywrightScrapeSettings(
        max_pages=max_pages,
        max_terms=max_terms,
        fetch_detail=fetch_detail,
        mca_term_limit=mca_limit,
        extra_search_terms=_terms(),
        page_cap_per_run=page_cap,
        search_profiles=profiles,
        prefix_terms=_prefix_terms(),
        profile_filter=None,
        page_order=page_order,
        recent_pages=recent_pages,
    )
