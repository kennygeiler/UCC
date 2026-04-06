---
phase: 3
plan: 03
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Lead canonical debtor fields, filing-scoped pipeline idempotency, tier persistence
requirements: [MCA-02, MCA-03]
depends_on_plans: [01]
files_touch_estimate:
  - app/models/lead.py
  - app/mca/pipeline.py
  - migrations/versions/
  - tests/integration/test_mca_pipeline.py
  - app/export/ghl_adapter.py
  - app/export/csv_fallback.py
---

# Plan 03 — Canonical identity + pipeline correctness

## Objective

Satisfy **MCA-03** and **C-10** hooks: persist **canonical/normalized debtor identity** on `Lead` (minimum: `debtor_name_normalized` using existing `normalize_name` from `app/mca/detector.py`; document optional future `canonical_business_id` as nullable placeholder column **only if** it simplifies downstream export—otherwise skip second column to avoid empty schema noise). Fix **`get_unprocessed_filings`** so “processed” is **per filing** (not global `debtor_name` match across states): add **`source_filing_id`** FK `leads.source_filing_id → ucc_filings.id` with **unique constraint** on `source_filing_id` (nullable for legacy rows). Persist **`mca_tier`** (`hot`/`warm`/`cold`) on `Lead` so **MCA-02** success criterion “observable on stored lead records” holds (export adapters already expect `tier` in dict—wire ORM field so serialization includes it). Update **`process_filing`** to populate new fields, skip insert if filing already linked, and align **`find_high_converting_parties`** in `alias_updater.py` if join logic must become state-safe (same debtor name across states).

## Security considerations

| Topic | Requirement |
|-------|-------------|
| Data integrity | Migration must backfill `debtor_name_normalized` from `normalize_name(debtor_name)` for existing leads where feasible. |
| Idempotency | Unique on `source_filing_id` prevents duplicate leads from same filing on pipeline retries. |
| Export | Ensure GHL/CSV paths read tier from model without logging full PII payloads. |

## UAT criteria (traceability)

| UAT ID | Criterion (operator-visible) | REQ |
|--------|------------------------------|-----|
| UAT-3.06 | New lead rows include normalized debtor key suitable for dedup phase. | MCA-03 / C-10 |
| UAT-3.07 | Same debtor name in two states can each produce leads when filings differ; same filing never creates two MCA leads. | MCA-03 |
| UAT-3.08 | Stored lead shows hot/warm/cold tier consistent with scorer. | MCA-02 |

## Dependencies between plans

- **Depends on Plan 01** — integration tests for scoring/tiers assume state-scoped `count_positions`.

## MCA-01–MCA-05 coverage (phase)

| Requirement | Plan(s) | Notes |
|-------------|---------|--------|
| MCA-01 | 02 | — |
| MCA-02 | 01, 03 | Tier column + correct counts. |
| MCA-03 | 03 | Primary delivery. |
| MCA-04 | 04 | — |
| MCA-05 | 03 | Pipeline integration tests. |

---

## Wave 0 — Alembic migration

**Goal:** Schema for identity + filing link + tier.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** New revision: add `leads.debtor_name_normalized` (Text, NOT NULL default `''` **or** nullable with backfill in migration—prefer NOT NULL after backfill), `leads.source_filing_id` (Integer FK → `ucc_filings.id`, nullable, **UniqueConstraint**), `leads.mca_tier` (Text, nullable with backfill from score if possible **or** nullable until new rows only—executor chooses simplest consistent approach). | `alembic upgrade head` on clean DB succeeds. | `alembic upgrade head` |
| **0.2** Create index on `debtor_name_normalized` if dedup phase will query it (recommended). | Index exists in migration. | Inspect migration file |

---

## Wave 1 — ORM + pipeline

**Goal:** Write path matches schema and MCA rules.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Update `app/models/lead.py` with new columns; update `process_filing` to set `debtor_name_normalized`, `source_filing_id=filing.id`, `mca_tier=scoring["tier"]`. | Model matches DB. | `pytest tests/ -k lead --maxfail=1 -q` (adjust) |
| **1.2** Rewrite `get_unprocessed_filings`: select filings where **no** lead exists with `Lead.source_filing_id == UCCFiling.id` (prefer `NOT EXISTS` or `outerjoin` on **filing id**, not debtor name). | Two states same debtor: both filings eligible. | Integration test in Wave 2 |
| **1.3** Idempotency: if lead already exists for `filing.id`, return existing or no-op without error (define behavior in docstring). | Second `process_filing` does not insert duplicate. | Integration test |

---

## Wave 2 — Integration tests + export wiring

**Goal:** Prove end-to-end MCA-03 and tier visibility.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Add `tests/integration/test_mca_pipeline.py`: seed filings + run `process_filing` / `get_unprocessed_filings`; assert canonical fields, tier, and single-lead-per-filing. | Uses `@pytest.mark.integration` if Postgres required. | `pytest tests/integration/test_mca_pipeline.py -m integration -x -q` |
| **2.2** Update `app/export/ghl_adapter.py` and `app/export/csv_fallback.py` (or shared serialization) so `tier` comes from `Lead.mca_tier` when building `lead_data`—grep `lead_data` / `tier` and align. | No regression in unit tests for export. | `pytest tests/ -k ghl -q` **or** `pytest tests/ -k csv -q` |

---

## Completion checklist

- [ ] Migration applied; ORM updated.
- [ ] Pipeline idempotent per filing; unprocessed query state-safe.
- [ ] Export reads stored tier.

## Output

After execution, add phase summary artifact per GSD workflow.
