"""Env-backed scrape caps for Playwright Tier 1 states."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class PlaywrightScrapeSettings:
    """Runtime caps for one Playwright Tier 1 state scrape."""

    max_pages: int
    max_terms: int
    fetch_detail: bool
    mca_term_limit: int
    extra_search_terms: tuple[str, ...]
    page_cap_per_run: int | None = None


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
        if state_v is not None and state_attr in type(settings).model_fields:
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

    max_pages = _get_int("PLAYWRIGHT_SCRAPE_MAX_PAGES", f"{prefix}_MAX_PAGES", 50)
    max_terms = _get_int("PLAYWRIGHT_SCRAPE_MAX_TERMS", f"{prefix}_MAX_TERMS", 20)
    mca_limit = _get_int("PLAYWRIGHT_SCRAPE_MCA_TERM_LIMIT", f"{prefix}_MCA_TERM_LIMIT", 20)
    fetch_detail = _get_bool("PLAYWRIGHT_SCRAPE_FETCH_DETAIL", f"{prefix}_FETCH_DETAIL", True)
    page_cap = None
    if settings and f"{prefix}_PAGE_CAP_PER_RUN" in type(settings).model_fields:
        raw_cap = getattr(settings, f"{prefix}_PAGE_CAP_PER_RUN")
        if raw_cap is not None:
            page_cap = int(raw_cap)

    return PlaywrightScrapeSettings(
        max_pages=max_pages,
        max_terms=max_terms,
        fetch_detail=fetch_detail,
        mca_term_limit=mca_limit,
        extra_search_terms=_terms(),
        page_cap_per_run=page_cap,
    )
