#!/usr/bin/env python3
"""Reset Florida-scoped pipeline data before a fresh manual scrape."""

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
    parser = argparse.ArgumentParser(
        description="Delete FL filings, accounts, leads, scraper runs, and checkpoints."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only; do not delete.",
    )
    return parser.parse_args()


async def main() -> int:
    from app.operations.fl_reset import reset_fl_data

    args = _parse_args()
    counts = await reset_fl_data(dry_run=args.dry_run)

    mode = "would delete" if args.dry_run else "deleted"
    print(f"FL reset ({mode}):")
    print(f"  compliance_checks:      {counts.compliance_checks}")
    print(f"  enrichment_retry_queue: {counts.enrichment_retry_queue}")
    print(f"  leads:                  {counts.leads}")
    print(f"  business_accounts:      {counts.business_accounts}")
    print(f"  ucc_filings:            {counts.ucc_filings}")
    print(f"  scraper_runs:           {counts.scraper_runs}")
    print(f"  scraper_checkpoints:    {counts.scraper_checkpoints}")
    print(f"  total:                  {counts.total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
