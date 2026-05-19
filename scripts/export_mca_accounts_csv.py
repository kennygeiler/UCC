#!/usr/bin/env python3
"""Export MCA funder business accounts to CSV (same columns as dashboard download)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


async def main() -> int:
    from app.export.csv_export import build_mca_accounts_csv, mca_export_filename

    parser = argparse.ArgumentParser(description="Export MCA funder accounts to CSV")
    parser.add_argument("--state", default="FL", help="State code (default FL)")
    parser.add_argument("--tier", default=None, help="Consolidation tier filter (priority, work, …)")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path (default: ucc-mca-leads-{STATE}-{date}.csv in cwd)",
    )
    args = parser.parse_args()
    state = args.state.strip().upper()
    tier = (args.tier or "").strip().lower() or None

    csv_text = await build_mca_accounts_csv(state=state, tier=tier, consolidation_tier=tier)
    out_path = Path(args.output) if args.output else Path(mca_export_filename(state=state))
    out_path.write_text(csv_text, encoding="utf-8")
    row_count = max(0, csv_text.count("\n") - 1)
    print(f"Wrote {row_count} rows to {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
