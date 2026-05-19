#!/usr/bin/env python3
"""Post-scrape SQL snapshot for Florida data quality checks."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


async def main() -> int:
    from sqlalchemy import func, select, text

    from app.db import get_engine, get_session
    from app.models.account import BusinessAccount
    from app.models.filing import UCCFiling
    from app.models.lead import Lead

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError as exc:
        print(f"Postgres not reachable: {exc}")
        return 1

    async with get_session() as session:
        filings = (
            await session.execute(
                select(func.count()).select_from(UCCFiling).where(UCCFiling.state == "FL")
            )
        ).scalar_one()
        with_date = (
            await session.execute(
                select(func.count())
                .select_from(UCCFiling)
                .where(UCCFiling.state == "FL", UCCFiling.filing_date.is_not(None))
            )
        ).scalar_one()
        accounts = (
            await session.execute(
                select(func.count())
                .select_from(BusinessAccount)
                .where(BusinessAccount.state == "FL")
            )
        ).scalar_one()
        leads = (
            await session.execute(
                select(func.count()).select_from(Lead).where(Lead.state == "FL")
            )
        ).scalar_one()

        dupes = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT state, filing_number, COUNT(*) AS c
                        FROM ucc_filings
                        WHERE state = 'FL'
                        GROUP BY state, filing_number
                        HAVING COUNT(*) > 1
                    ) d
                    """
                )
            )
        ).scalar_one()

        tiers = (
            await session.execute(
                text(
                    """
                    SELECT consolidation_tier, COUNT(*) AS c
                    FROM business_accounts
                    WHERE state = 'FL'
                    GROUP BY consolidation_tier
                    ORDER BY c DESC
                    """
                )
            )
        ).all()

        top_accounts = (
            await session.execute(
                select(
                    BusinessAccount.display_name,
                    BusinessAccount.consolidation_score,
                    BusinessAccount.consolidation_tier,
                )
                .where(BusinessAccount.state == "FL")
                .order_by(BusinessAccount.consolidation_score.desc().nullslast())
                .limit(10)
            )
        ).all()

        match_types = (
            await session.execute(
                text(
                    """
                    SELECT mca_match_type, COUNT(*) AS c
                    FROM leads
                    WHERE state = 'FL'
                    GROUP BY mca_match_type
                    ORDER BY c DESC
                    """
                )
            )
        ).all()

        gov_leads = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM leads l
                    JOIN ucc_filings f ON f.id = l.source_filing_id
                    WHERE l.state = 'FL' AND (
                      f.secured_party ILIKE '%SBA%'
                      OR f.secured_party ILIKE '%SMALL BUSINESS ADMIN%'
                    )
                    """
                )
            )
        ).scalar_one()

        fuzzy_leads = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM leads WHERE state = 'FL' AND mca_match_type = 'fuzzy'"
                )
            )
        ).scalar_one()

        last_run = (
            await session.execute(
                text(
                    """
                    SELECT status, records_found, started_at, finished_at, error_detail
                    FROM scraper_runs
                    WHERE state = 'FL'
                    ORDER BY started_at DESC NULLS LAST
                    LIMIT 1
                    """
                )
            )
        ).first()

    pct_date = (100.0 * with_date / filings) if filings else 0.0
    fuzzy_pct = (100.0 * fuzzy_leads / leads) if leads else 0.0
    print("=== Florida data snapshot ===")
    print(f"ucc_filings (FL):     {filings}")
    print(f"filing_date non-null: {with_date} ({pct_date:.1f}%)")
    print(f"business_accounts:    {accounts}")
    print(f"leads (FL state):     {leads}")
    print(f"fuzzy leads:          {fuzzy_leads} ({fuzzy_pct:.1f}% of leads)")
    print(f"gov/SBA false leads:  {gov_leads}")
    print(f"duplicate (state, filing_number) groups: {dupes}")
    print("leads by mca_match_type:")
    for mt, count in match_types:
        print(f"  {mt or '(null)'}: {count}")
    print("consolidation_tier distribution:")
    for tier, count in tiers:
        label = tier if tier is not None else "(null)"
        print(f"  {label}: {count}")
    print("top 10 accounts by consolidation_score:")
    for name, score, tier in top_accounts:
        label = name or "(unnamed)"
        sc = score if score is not None else 0.0
        print(f"  {sc:.1f} [{tier}] {label}")
    if last_run:
        status, found, started, finished, err = last_run
        print("last scraper_run:")
        print(f"  status={status} filings_found={found}")
        if started:
            print(f"  started={started}")
        if finished:
            print(f"  finished={finished}")
        if err:
            print(f"  error={err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
