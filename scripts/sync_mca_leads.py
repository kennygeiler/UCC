#!/usr/bin/env python3
"""Align MCA classification and account rollup after alias / lender list changes.

Thin CLI wrapper around ``app.mca.refresh.refresh_mca_classification``.
"""

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
    from app.dashboard.queries import count_mca_lead_accounts
    from app.mca.refresh import refresh_mca_classification

    parser = argparse.ArgumentParser(description="Reclassify filings and refresh MCA lead accounts")
    parser.add_argument("--state", default="FL", help="State code (default FL)")
    args = parser.parse_args()
    state = args.state.strip().upper()

    before = await count_mca_lead_accounts(state=state)
    result = await refresh_mca_classification(state)
    after = await count_mca_lead_accounts(state=state)

    print(f"=== MCA sync ({state}) ===")
    for key, val in result.items():
        print(f"  {key}: {val}")
    print(f"mca_lead_accounts: {before} → {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
