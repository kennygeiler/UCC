#!/usr/bin/env python3
"""Run all Tier 1 scrapers that are ready (sequential, rate-limited)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_DELAY_SECONDS = 30.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sequential manual scrape for runnable Tier 1 states."
    )
    parser.add_argument(
        "--states",
        default="",
        help="Comma-separated subset (default: all ready Tier 1).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Seconds between states (default {DEFAULT_DELAY_SECONDS}).",
    )
    parser.add_argument(
        "--no-consolidation",
        action="store_true",
        help="Skip post-scrape pipeline (not recommended).",
    )
    return parser.parse_args()


async def main() -> int:
    from app.scrapers.exceptions import ScraperNotReadyError
    from app.scrapers.registry import get_scraper_class
    from app.scrapers.state_config import list_tier1_ready_states

    args = _parse_args()
    if args.states.strip():
        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    else:
        states = list_tier1_ready_states()

    kwargs = {"run_consolidation": not args.no_consolidation}
    exit_code = 0

    for i, state in enumerate(states):
        if i > 0 and args.delay > 0:
            print(f"Waiting {args.delay}s before {state}…")
            await asyncio.sleep(args.delay)

        scraper_cls = get_scraper_class(state)
        if scraper_cls is None:
            print(f"SKIP {state}: not registered", file=sys.stderr)
            exit_code = 1
            continue

        print(f"Starting {state} scrape…")
        try:
            try:
                scraper = scraper_cls(**kwargs)
            except TypeError:
                scraper = scraper_cls()
            count = await scraper.scrape()
            print(f"  {state}: {count} new filings")
        except ScraperNotReadyError as exc:
            print(f"  {state}: NOT READY — {exc}", file=sys.stderr)
            exit_code = 2
        except Exception as exc:
            print(f"  {state}: FAILED — {exc}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
