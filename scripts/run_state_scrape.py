#!/usr/bin/env python3
"""Run a single state UCC scrape manually (no scheduler)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

_PLAYWRIGHT_STATES = frozenset({"CA", "TX", "NY", "NJ"})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual state scrape + post pipeline.")
    parser.add_argument("--state", required=True, help="Two-letter state code (e.g. FL, CA).")
    parser.add_argument(
        "--no-consolidation",
        action="store_true",
        help="Skip post-scrape classify/rollup/MCA pipeline.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Low caps for smoke tests (FL or Playwright Tier 1).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Override max pages per search term (Playwright Tier 1).",
    )
    parser.add_argument(
        "--max-terms",
        type=int,
        default=None,
        help="Override max search terms per run (Playwright Tier 1).",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Run only this search profile (NY: debtor_org_sw, debtor_org_bw).",
    )
    return parser.parse_args()


def _playwright_quick_settings(
    state: str,
    *,
    max_pages: int | None,
    max_terms: int | None,
    profile_filter: str | None = None,
):
    from app.scrapers.playwright_tier1.settings import (
        PlaywrightScrapeSettings,
        load_playwright_scrape_settings,
    )

    base = load_playwright_scrape_settings(state)
    return PlaywrightScrapeSettings(
        max_pages=max_pages if max_pages is not None else 2,
        max_terms=max_terms if max_terms is not None else 3,
        fetch_detail=False,
        mca_term_limit=3,
        extra_search_terms=base.extra_search_terms,
        page_cap_per_run=2,
        search_profiles=base.search_profiles,
        prefix_terms=base.prefix_terms,
        profile_filter=profile_filter,
    )


async def main() -> int:
    from app.scrapers.exceptions import ScraperNotReadyError
    from app.scrapers.registry import get_scraper_class
    from app.scrapers.state_config import is_tier1_runnable, tier1_not_ready_reason

    args = _parse_args()
    state = args.state.strip().upper()

    if not is_tier1_runnable(state):
        print(f"{state} is not runnable: {tier1_not_ready_reason(state)}", file=sys.stderr)
        return 2

    scraper_cls = get_scraper_class(state)
    if scraper_cls is None:
        print(f"No scraper registered for {state}", file=sys.stderr)
        return 1

    kwargs: dict = {}
    if args.no_consolidation:
        kwargs["run_consolidation"] = False

    if state == "FL" and args.quick:
        from app.scrapers.states.florida import DEFAULT_INDEX_PROFILES, FloridaScraper

        kwargs.update(
            max_pages=3,
            page_cap_per_run=2,
            index_profiles=DEFAULT_INDEX_PROFILES[:2],
            fetch_filing_date=False,
            enrich_concurrency=2,
            run_consolidation=not args.no_consolidation,
        )
        scraper = FloridaScraper(**kwargs)
    elif state in _PLAYWRIGHT_STATES and (
        args.quick
        or args.max_pages is not None
        or args.max_terms is not None
        or args.profile is not None
    ):
        from app.scrapers.playwright_tier1.settings import (
            PlaywrightScrapeSettings,
            load_playwright_scrape_settings,
        )

        if args.quick:
            settings = _playwright_quick_settings(
                state,
                max_pages=args.max_pages,
                max_terms=args.max_terms,
                profile_filter=args.profile,
            )
        else:
            base = load_playwright_scrape_settings(state)
            settings = PlaywrightScrapeSettings(
                max_pages=args.max_pages if args.max_pages is not None else base.max_pages,
                max_terms=args.max_terms if args.max_terms is not None else base.max_terms,
                fetch_detail=base.fetch_detail,
                mca_term_limit=base.mca_term_limit,
                extra_search_terms=base.extra_search_terms,
                page_cap_per_run=base.page_cap_per_run,
                search_profiles=base.search_profiles,
                prefix_terms=base.prefix_terms,
                profile_filter=args.profile or base.profile_filter,
            )
        kwargs["scrape_settings"] = settings
        scraper = scraper_cls(**kwargs)
    else:
        try:
            scraper = scraper_cls(**kwargs)
        except TypeError:
            scraper = scraper_cls()

    try:
        count = await scraper.scrape()
    except ScraperNotReadyError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"{state} scrape complete: {count} new filings inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
