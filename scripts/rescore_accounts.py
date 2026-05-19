#!/usr/bin/env python3
"""Re-run consolidation rollup + rescore for FL business accounts."""

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


async def main(state: str) -> int:
    from app.consolidation.rollup import classify_filings, rescore_accounts, rollup_accounts

    classified = 0
    while True:
        batch = await classify_filings(state, batch_size=500)
        classified += batch
        if batch < 500:
            break
    accounts = await rollup_accounts(state)
    rescored = await rescore_accounts(state)
    print(
        f"state={state} classified={classified} accounts={accounts} rescored={rescored}"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rescore business accounts")
    parser.add_argument("--state", default="FL", help="State code (default FL)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.state.upper())))
