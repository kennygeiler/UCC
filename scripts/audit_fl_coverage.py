#!/usr/bin/env python3
"""Lightweight Florida scrape coverage audit for operators."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

PAGE_SIZE = 20


async def main() -> int:
    from sqlalchemy import func, select, text

    from app.config import Settings
    from app.db import get_engine, get_session
    from app.models.filing import UCCFiling
    from app.scrapers.states.florida import parse_index_profiles

    settings = Settings()
    profiles = parse_index_profiles(settings.FL_SCRAPE_INDEX_PROFILES)
    exact_terms = [t.strip() for t in settings.FL_SCRAPE_EXACT_TERMS.split(",") if t.strip()]

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

        checkpoints = (
            await session.execute(
                text(
                    """
                    SELECT profile_key, row_number, updated_at
                    FROM scraper_checkpoints
                    WHERE state = 'FL'
                    ORDER BY profile_key
                    """
                )
            )
        ).all()

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

    cap = settings.FL_SCRAPE_PAGE_CAP_PER_RUN
    est_rows_standard = len(profiles) * cap * PAGE_SIZE
    est_rows_exact = len(exact_terms) * cap * PAGE_SIZE
    est_rows = est_rows_standard + est_rows_exact

    daily_low, daily_high = 300, 1200
    coverage_low = (filings / daily_high * 100) if daily_high else 0
    coverage_high = (filings / daily_low * 100) if daily_low else 0

    duration_s = None
    if last_run and last_run[2] and last_run[3]:
        duration_s = (last_run[3] - last_run[2]).total_seconds()

    lines = [
        "# Florida scrape coverage audit",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Volume",
        f"- FL filings in DB: **{filings}**",
        f"- Index profiles configured: **{len(profiles)}** (`FL_SCRAPE_PAGE_CAP_PER_RUN={cap}`)",
        f"- Exact MCA terms configured: **{len(exact_terms)}**",
        f"- Estimated max rows this run (pages × {PAGE_SIZE}): **~{est_rows}** "
        f"(Standard ~{est_rows_standard} + Exact ~{est_rows_exact})",
        "",
        "## Indicative daily coverage",
        f"- Rough FL daily filing volume: **{daily_low}–{daily_high}**/day (estimate only)",
        f"- If one day of volume: **{coverage_low:.0f}%–{coverage_high:.0f}%** of filings captured "
        f"(indicative; not a guarantee)",
        "",
        "## Checkpoints",
    ]
    if checkpoints:
        for profile_key, row_number, updated_at in checkpoints:
            lines.append(f"- `{profile_key}`: row **{row_number}** (updated {updated_at})")
    else:
        lines.append("- _(no checkpoints — fresh scrape or quick mode)_")

    lines.extend(["", "## Last scraper run"])
    if last_run:
        status, found, started, finished, err = last_run
        lines.append(f"- Status: **{status}** | filings_found: **{found}**")
        if started:
            lines.append(f"- Started: {started}")
        if finished:
            lines.append(f"- Finished: {finished}")
        if duration_s is not None:
            lines.append(f"- Duration: **{duration_s:.0f}s**")
        if err:
            lines.append(f"- Error: {err}")
    else:
        lines.append("- _(no FL scraper runs logged)_")

    report = "\n".join(lines)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
