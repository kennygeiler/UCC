#!/usr/bin/env python3
"""Run Florida UCC scrape manually (no scheduler)."""

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
    parser = argparse.ArgumentParser(description="Manual Florida UCC scrape + post pipeline.")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Small page caps (2–3 pages per index) for tests; skips filing-date enrichment.",
    )
    parser.add_argument(
        "--no-consolidation",
        action="store_true",
        help="Skip post-scrape classify/rollup/MCA pipeline.",
    )
    return parser.parse_args()


async def main() -> int:
    from app.scrapers.states.florida import FloridaScraper, DEFAULT_INDEX_PROFILES

    args = _parse_args()
    kwargs: dict = {"run_consolidation": not args.no_consolidation}
    if args.quick:
        kwargs.update(
            max_pages=3,
            page_cap_per_run=2,
            index_profiles=DEFAULT_INDEX_PROFILES[:2],
            fetch_filing_date=False,
            enrich_concurrency=2,
        )
        print("Quick mode: 2 pages/index, 2 org profiles, no filing-date fetch")

    scraper = FloridaScraper(**kwargs)
    count = await scraper.scrape()
    print(f"FL scrape complete: {count} new filings inserted")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
