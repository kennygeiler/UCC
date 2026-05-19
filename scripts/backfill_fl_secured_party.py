"""One-shot backfill for FL ``ucc_filings`` rows missing ``secured_party``.

Queries every ``state='FL'`` row with ``secured_party IS NULL`` and calls the
:meth:`FloridaScraper._fetch_secured_party` detail endpoint with a configurable
concurrency cap. Updates rows in place.

Usage::

    python -m scripts.backfill_fl_secured_party [--concurrency 5] [--limit 500]
"""

from __future__ import annotations

import argparse
import asyncio

import httpx
from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.filing import UCCFiling
from app.scrapers.states.florida import FloridaScraper
from app.scrapers.user_agents import get_random_user_agent

logger = get_logger("backfill_fl")


async def backfill_secured_party(
    concurrency: int = 5,
    limit: int | None = None,
    fetch_filing_date: bool = False,
) -> tuple[int, int]:
    """Backfill ``secured_party`` for FL filings missing it.

    Args:
        concurrency: Max parallel detail-API requests.
        limit: Max number of rows to attempt this run.
        fetch_filing_date: When true, also backfill ``filing_date`` via the
            top-level filing-detail endpoint (extra HTTP call per row).

    Returns:
        ``(attempted, updated)`` — how many rows we looked at and how many
        gained a non-null ``secured_party``.
    """
    scraper = FloridaScraper(
        enrich_concurrency=concurrency,
        fetch_filing_date=fetch_filing_date,
    )

    async with get_session() as session:
        stmt = select(UCCFiling).where(
            UCCFiling.state == "FL",
            UCCFiling.secured_party.is_(None),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = list((await session.execute(stmt)).scalars().all())
        targets = [
            {
                "id": row.id,
                "filing_number": row.filing_number,
            }
            for row in rows
        ]

    if not targets:
        logger.info("backfill_fl_noop", reason="no_rows")
        return 0, 0

    sem = asyncio.Semaphore(max(1, concurrency))
    results: dict[int, dict] = {}

    async def _one(client: httpx.AsyncClient, target: dict) -> None:
        async with sem:
            sp = await scraper._fetch_secured_party(client, target["filing_number"])
            update: dict = {}
            if sp:
                update["secured_party"] = sp
            if fetch_filing_date:
                meta = await scraper._fetch_filing_metadata(client, target["filing_number"])
                if meta:
                    date_str = meta.get("date") or meta.get("createDate")
                    if isinstance(date_str, str):
                        parsed = FloridaScraper._parse_iso_date(date_str)
                        if parsed is not None:
                            update["filing_date"] = parsed
            results[target["id"]] = update

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": get_random_user_agent()},
    ) as client:
        await asyncio.gather(*[_one(client, t) for t in targets])

    updated = 0
    async with get_session() as session:
        for row_id, update in results.items():
            if not update:
                continue
            row = await session.get(UCCFiling, row_id)
            if row is None:
                continue
            if update.get("secured_party"):
                row.secured_party = update["secured_party"]
            if update.get("filing_date") and row.filing_date is None:
                row.filing_date = update["filing_date"]
            updated += 1
    logger.info("backfill_fl_complete", attempted=len(targets), updated=updated)
    return len(targets), updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--fetch-filing-date",
        action="store_true",
        help="Also backfill filing_date via the filing-detail endpoint.",
    )
    args = parser.parse_args()
    attempted, updated = asyncio.run(
        backfill_secured_party(
            concurrency=args.concurrency,
            limit=args.limit,
            fetch_filing_date=args.fetch_filing_date,
        )
    )
    print(f"Backfill complete: attempted={attempted} updated={updated}")


if __name__ == "__main__":
    main()
