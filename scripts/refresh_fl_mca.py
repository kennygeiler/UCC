#!/usr/bin/env python3
"""Re-run MCA detection and consolidation for Florida after detector fixes.

Idempotent and FL-scoped: re-classifies filings, removes invalid MCA leads,
clears stale ``is_mca`` flags, re-runs MCA pipeline + account rescoring.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


async def main() -> int:
    from app.mca.refresh import refresh_mca_classification

    result = await refresh_mca_classification("FL")
    print("=== FL MCA refresh ===")
    print(f"filings reclassified:     {result['filings_reclassified']}")
    print(f"is_mca cleared:           {result['is_mca_cleared']}")
    print(f"invalid leads removed:    {result['invalid_leads_removed']}")
    print(f"accounts rolled up:       {result['accounts_rolled_up']}")
    print(f"accounts rescored:      {result['accounts_rescored']}")
    print(f"new leads from pipeline:  {result['new_filing_leads']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
