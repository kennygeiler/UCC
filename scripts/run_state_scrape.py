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
        help="FL only: small page caps for tests.",
    )
    return parser.parse_args()


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
