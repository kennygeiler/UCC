---
phase: 4
plan: 03
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Enrichment retry queue — backoff + scheduler
requirements: [ENRICH-04]
depends_on_plans: [01-PLAN.md, 02-PLAN.md]
files_touch_estimate:
  - app/enrichment/pipeline.py
  - app/enrichment/retry_worker.py
  - app/scrapers/scheduler.py
  - app/config.py
  - tests/unit/test_enrichment_retry.py
---

# Plan 03 — Retry queue processing

## Objective

**ENRICH-04:** Failed enrichments are stored in `enrichment_retry_queue` with **documented backoff**: **1h → 4h → 24h → 72h** (attempt 1→2→3→4+ per arch-constraints). A **scheduler job** periodically claims due rows and re-attempts enrichment (respecting `check_pipeline_halt`).

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-4-04 | Duplicate concurrent retries for same lead | Use `SELECT FOR UPDATE SKIP LOCKED` or single-flight by `lead_id` + transaction; document choice. |
| T-4-05 | Retry storm when API is down | HALT from Plan 02 stops new work; retries still check `check_pipeline_halt` before processing. |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-4.05 | After failure, `next_retry_at` equals now + **1 hour** for first retry (test with frozen time). | ENRICH-04 |
| UAT-4.06 | Fourth failure schedules **72h** next step. | ENRICH-04 |

## Dependencies between plans

- Depends on **Plans 01–02** (waterfall + HALT).
- **Plan 04** may add integration tests that include retry rows.

---

## Wave 0 — Backoff helper + DB updates

**Read first:** `app/models/job.py` (`EnrichmentRetryQueue`), `app/enrichment/pipeline.py` (`_queue_retry`).

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Implement `next_backoff_seconds(attempt_count: int) -> int` mapping: `1→3600`, `2→14400`, `3→86400`, `>=4→259200` (document as 1h/4h/24h/72h). | Function lives in `app/enrichment/` (new module or `pipeline.py` if small). | Unit test table-driven |
| **0.2** Update `_queue_retry` to set `next_retry_at` using helper, increment `attempt_count`, store `last_error` (truncated, no secrets). | `grep _queue_retry app/enrichment/pipeline.py` shows backoff | `pytest tests/unit/test_enrichment_retry.py -q` |

---

## Wave 1 — Scheduler job

**Read first:** `app/scrapers/scheduler.py`, `app/config.py` (pattern from `MCA_ALIAS_UPDATE_*`).

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add `async def process_enrichment_retries(batch_size: int) -> int` that: selects due retries (`next_retry_at <= now`), **skips if** `check_pipeline_halt()`, re-runs `enrich_lead` for associated lead (reload `Lead` by id). | Structured log `enrichment_retry_processed` or similar with `component`, `status`, `error_type`, `context`. | `pytest tests/unit/test_enrichment_retry.py -q` |
| **1.2** Register APScheduler job when `ENRICH_RETRY_JOB_ENABLED` (default `True`, tests `False` in `tests/conftest.py` mirroring MCA alias pattern). Interval: hourly or configurable `ENRICH_RETRY_INTERVAL_MINUTES`. | `grep ENRICH_RETRY scheduler.py` | `pytest tests/unit/test_scheduler.py -q` |

---

## must_haves

1. Backoff schedule matches constraint doc (1h, 4h, 24h, 72h).
2. Scheduler registration is test-covered and disabled in tests by default.
3. HALT prevents retry batch from running (or runs zero work).
