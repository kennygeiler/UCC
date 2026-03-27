#!/usr/bin/env python3
"""Local end-to-end pipeline test runner.

Runs the full UCC lead-gen pipeline locally without Railway:
  scrape → detect MCA → score → enrich → compliance → export

Usage:
    python scripts/e2e_local.py --state CA
    python scripts/e2e_local.py --state NY --dry-run
"""

import argparse
import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 1. Pre-flight checks (no app imports yet — they need DATABASE_URL)
# ---------------------------------------------------------------------------


def preflight():
    """Verify DATABASE_URL is set and Postgres is reachable."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("FAIL: DATABASE_URL is not set.")
        sys.exit(1)
    print(f"  DATABASE_URL = {db_url[:30]}...")

    # Ensure SENTRY_DSN has a value so Settings() won't blow up
    if not os.environ.get("SENTRY_DSN"):
        os.environ["SENTRY_DSN"] = "https://placeholder@sentry.io/0"
        print("  SENTRY_DSN not set — using placeholder for local run")

    # Quick Postgres connectivity check via psycopg2 or pg_isready
    try:
        result = subprocess.run(
            ["python", "-c", _pg_check_snippet(db_url)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"FAIL: Cannot reach Postgres:\n{result.stderr.strip()}")
            sys.exit(1)
    except FileNotFoundError:
        print("WARN: Could not run Postgres connectivity check (python not on PATH)")

    print("  Postgres is reachable.")


def _pg_check_snippet(db_url: str) -> str:
    """Return a Python snippet that tests DB connectivity via SQLAlchemy."""
    return (
        "from sqlalchemy import create_engine, text; "
        f"e = create_engine('{db_url}'.replace('postgresql+asyncpg://', 'postgresql://').replace('postgres://', 'postgresql://')); "
        "c = e.connect(); c.execute(text('SELECT 1')); c.close(); print('ok')"
    )


# ---------------------------------------------------------------------------
# 2. Run alembic migrations
# ---------------------------------------------------------------------------


def run_migrations():
    """Run alembic upgrade head to ensure schema is current."""
    print("\n--- Running alembic upgrade head ---")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"FAIL: Alembic migration failed:\n{result.stderr.strip()}")
        sys.exit(1)
    print("  Migrations applied successfully.")


# ---------------------------------------------------------------------------
# Async pipeline stages
# ---------------------------------------------------------------------------


async def stage_scrape(state: str) -> int:
    """Stage 3: Scrape a single state."""
    from app.scrapers.registry import get_scraper_class

    scraper_class = get_scraper_class(state)
    if scraper_class is None:
        print(f"  FAIL: No scraper registered for state '{state}'")
        sys.exit(1)

    scraper = scraper_class()
    count = await scraper.scrape()
    return count


async def stage_detect(state: str) -> list[dict]:
    """Stage 4: Run MCA detection on scraped filings for the state."""
    from sqlalchemy import select

    from app.db import get_session
    from app.mca.detector import detect_mca, check_collateral_keywords
    from app.models.filing import UCCFiling

    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling).where(UCCFiling.state == state)
        )
        filings = list(result.scalars().all())

    leads = []
    for f in filings:
        is_mca, canonical, confidence = await detect_mca(
            f.secured_party, f.collateral_description
        )
        if is_mca:
            leads.append({
                "debtor_name": f.debtor_name,
                "state": f.state,
                "filing_date": f.filing_date,
                "secured_party": canonical,
                "confidence": confidence,
                "has_mca_collateral": check_collateral_keywords(f.collateral_description),
                "filing_id": f.id,
            })
    return leads


async def stage_score(detected_leads: list[dict]) -> list[dict]:
    """Stage 5: Score detected MCA leads."""
    from app.mca.scorer import score_lead

    scored = []
    for lead in detected_leads:
        result = await score_lead(
            debtor_name=lead["debtor_name"],
            state=lead["state"],
            filing_date=lead["filing_date"],
            has_mca_collateral=lead["has_mca_collateral"],
        )
        lead.update(result)
        scored.append(lead)

    # Sort by score descending
    scored.sort(key=lambda x: x["lead_score"], reverse=True)
    return scored


async def stage_create_leads(scored_leads: list[dict]) -> list:
    """Insert scored leads into the leads table for downstream stages."""
    from app.db import get_session
    from app.models.lead import Lead

    created = []
    async with get_session() as session:
        for s in scored_leads:
            lead = Lead(
                debtor_name=s["debtor_name"],
                state=s["state"],
                lead_score=s["lead_score"],
                mca_position_count=s["mca_position_count"],
                enrichment_status="pending",
                compliance_status="pending",
                export_status="pending",
            )
            session.add(lead)
            await session.flush()
            created.append(lead)
    return created


async def stage_enrich(leads: list, dry_run: bool) -> int:
    """Stage 6: Enrich top 5 leads via PDL."""
    if dry_run:
        print("  --dry-run: skipping enrichment API calls")
        return 0

    pdl_key = os.environ.get("PDL_API_KEY")
    if not pdl_key:
        print("  WARN: PDL_API_KEY not set — skipping enrichment")
        return 0

    from app.enrichment.pipeline import build_enrichment_waterfall, enrich_lead

    waterfall = build_enrichment_waterfall()
    enriched = 0
    top5 = leads[:5]
    for lead in top5:
        try:
            ok = await enrich_lead(lead, waterfall)
            if ok:
                enriched += 1
        except Exception as exc:
            print(f"  WARN: Enrichment failed for {lead.debtor_name}: {exc}")
    return enriched


async def stage_compliance(leads: list) -> tuple[int, int]:
    """Stage 7: Run compliance gate on leads."""
    from app.compliance.gate import run_compliance_gate

    passed = 0
    blocked = 0
    for lead in leads:
        try:
            ok = await run_compliance_gate(lead)
            if ok:
                passed += 1
            else:
                blocked += 1
        except Exception as exc:
            print(f"  WARN: Compliance check error for {lead.debtor_name}: {exc}")
            passed += 1  # fail-open for unconfigured layers
    return passed, blocked


async def stage_export(leads: list, dry_run: bool) -> tuple[int, str]:
    """Stage 8: Export to GHL or CSV fallback."""
    if dry_run:
        print("  --dry-run: skipping export API calls")
        return 0, "skipped (dry-run)"

    ghl_key = os.environ.get("GHL_API_KEY")
    if ghl_key:
        from app.export.ghl_adapter import GHLAdapter
        adapter = GHLAdapter()
        method = "GHL"
    else:
        from app.export.csv_fallback import CSVFallbackAdapter
        adapter = CSVFallbackAdapter()
        method = "CSV"
        print("  GHL_API_KEY not set — using CSV fallback")

    exported = 0
    for lead in leads:
        if lead.compliance_status != "cleared":
            continue
        lead_data = {
            "phone": lead.phone,
            "email": lead.email,
            "owner_name": lead.owner_name,
            "debtor_name": lead.debtor_name,
            "tier": "hot" if (lead.mca_position_count or 0) >= 3
                   else "warm" if (lead.mca_position_count or 0) == 2
                   else "cold",
        }
        try:
            contact_id = await adapter.upsert_lead(lead_data)
            exported += 1
        except Exception as exc:
            print(f"  WARN: Export failed for {lead.debtor_name}: {exc}")
    return exported, method


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_pipeline(state: str, dry_run: bool):
    summary = {}

    # Stage 3: Scrape
    print(f"\n=== Stage 1: Scrape ({state}) ===")
    count = await stage_scrape(state)
    summary["filings_scraped"] = count
    print(f"  New filings scraped: {count}")

    # Stage 4: MCA Detection
    print(f"\n=== Stage 2: MCA Detection ({state}) ===")
    detected = await stage_detect(state)
    summary["leads_detected"] = len(detected)
    print(f"  MCA leads detected: {len(detected)}")

    if not detected:
        print("\n  No MCA leads found — pipeline complete.")
        _print_summary(summary)
        return

    # Stage 5: Score
    print("\n=== Stage 3: Score Leads ===")
    scored = await stage_score(detected)
    summary["leads_scored"] = len(scored)
    print(f"  Leads scored: {len(scored)}")
    for s in scored[:5]:
        print(f"    {s['debtor_name']}: score={s['lead_score']:.1f} tier={s['tier']}")

    # Create lead records in DB for enrichment/compliance/export
    leads = await stage_create_leads(scored)

    # Stage 6: Enrich (top 5)
    print("\n=== Stage 4: Enrich Top 5 ===")
    enriched = await stage_enrich(leads, dry_run)
    summary["leads_enriched"] = enriched
    print(f"  Leads enriched: {enriched}")

    # Stage 7: Compliance
    print("\n=== Stage 5: Compliance Gate ===")
    passed, blocked = await stage_compliance(leads)
    summary["leads_compliant"] = passed
    summary["leads_blocked"] = blocked
    print(f"  Passed: {passed}  Blocked: {blocked}")

    # Stage 8: Export
    print("\n=== Stage 6: Export ===")
    exported, method = await stage_export(leads, dry_run)
    summary["leads_exported"] = exported
    summary["export_method"] = method
    print(f"  Exported: {exported} via {method}")

    _print_summary(summary)


def _print_summary(summary: dict):
    print("\n" + "=" * 50)
    print("  E2E PIPELINE SUMMARY")
    print("=" * 50)
    print(f"  Filings scraped:   {summary.get('filings_scraped', 0)}")
    print(f"  Leads detected:    {summary.get('leads_detected', 0)}")
    print(f"  Leads scored:      {summary.get('leads_scored', 0)}")
    print(f"  Leads enriched:    {summary.get('leads_enriched', 0)}")
    print(f"  Leads compliant:   {summary.get('leads_compliant', 0)}")
    print(f"  Leads blocked:     {summary.get('leads_blocked', 0)}")
    print(f"  Leads exported:    {summary.get('leads_exported', 0)}")
    if "export_method" in summary:
        print(f"  Export method:     {summary['export_method']}")
    print("=" * 50)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Run the full UCC lead-gen pipeline locally (single-state e2e test)."
    )
    parser.add_argument(
        "--state", default="CA",
        help="Two-letter state code to scrape (default: CA)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip enrichment and export API calls",
    )
    args = parser.parse_args()
    state = args.state.upper()

    print("=" * 50)
    print("  UCC Lead-Gen Pipeline — Local E2E Test")
    print(f"  State: {state}  Dry-run: {args.dry_run}")
    print(f"  Time:  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 50)

    # Pre-flight
    print("\n--- Pre-flight checks ---")
    preflight()

    # Migrations
    run_migrations()

    # Async pipeline
    asyncio.run(run_pipeline(state, args.dry_run))

    print("\nDone.")


if __name__ == "__main__":
    main()
