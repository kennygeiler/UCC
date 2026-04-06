---
phase: 3
plan: 04
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Nightly MCA alias updater — scheduler job, idempotency, structured logging, tests
requirements: [MCA-04, MCA-05]
depends_on_plans: []
files_touch_estimate:
  - app/config.py
  - app/scrapers/scheduler.py
  - app/main.py
  - app/mca/alias_updater.py
  - tests/unit/test_scheduler.py
  - tests/integration/test_alias_updater.py
---

# Plan 04 — Scheduled alias updater

## Objective

Implement **MCA-04**: register a **nightly** (or interval-driven) APScheduler job in `create_scheduler()` that calls `run_alias_update` from `app/mca/alias_updater.py`, guarded by a **settings flag** (mirror `SCRAPER_SCHEDULER_ENABLED` pattern: e.g. `MCA_ALIAS_UPDATE_ENABLED` default `true`, tests set `false` in `conftest` if needed). Harden **idempotency**: `MCAlias` has **unique `alias_name`**—updater must **not** rely solely on in-memory `existing` set across transactions; use **INSERT … ON CONFLICT DO NOTHING** pattern **or** catch `IntegrityError` **or** query-before-insert inside the same session that commits—pick one clear approach and document. Add **structlog** events: job start, duration, `new_aliases`, errors with `component`, `status`, `error_type`, `context` (C-01). **MCA-05**: extend `tests/unit/test_scheduler.py` to assert alias job registered when flag on; add `tests/integration/test_alias_updater.py` for idempotent double-run.

## Security considerations

| Topic | Requirement |
|-------|-------------|
| Tampering / bad aliases | Log `source="auto_updater"` inserts; optional cap on new aliases per run via config (Claude’s discretion—if added, test). |
| Secrets | Job logs must not dump secured-party lists at DEBUG in production; use counts or hashed samples only. |
| Scheduler DoS | Use `AsyncIOScheduler` job with `max_instances=1` / `coalesce=True` to prevent overlap storms on slow DB. |

## UAT criteria (traceability)

| UAT ID | Criterion (operator-visible) | REQ |
|--------|------------------------------|-----|
| UAT-3.09 | With scheduler enabled, logs show alias update job registered and completing on interval. | MCA-04 |
| UAT-3.10 | Re-running updater does not create duplicate `mca_aliases` rows for the same `alias_name`. | MCA-04 |
| UAT-3.11 | Tests prove registration + idempotency without manual steps. | MCA-05 |

## Dependencies between plans

- **None** required; **Plan 02** fuzzy matching improves usefulness of aliases but is independent.

## MCA-01–MCA-05 coverage (phase)

| Requirement | Plan(s) | Notes |
|-------------|---------|--------|
| MCA-01 | 02 | — |
| MCA-02 | 01, 03 | — |
| MCA-03 | 03 | — |
| MCA-04 | 04 | Primary delivery. |
| MCA-05 | 01, 02, 03, 04 | Scheduler + updater integration tests here; see 01–03 for matcher/scorer/pipeline tests. |

---

## Wave 0 — Config and job wrapper

**Goal:** Feature flag + safe async entrypoint.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Add `MCA_ALIAS_UPDATE_ENABLED` and `MCA_ALIAS_UPDATE_INTERVAL_HOURS` (default 24) to `app/config.py`. | Settings validate. | `pytest tests/unit/test_config.py -q` (or add test) |
| **0.2** Add `async def run_alias_update_job()` in `alias_updater.py` (or scheduler module) that wraps `run_alias_update`, catches exceptions, logs failure with structured fields, **re-raises** only if product wants fail visibility—prefer log + metric, no crash of scheduler (document choice). | Unit test can mock `run_alias_update` to raise and assert log path. | `pytest tests/unit/test_alias_updater.py -q` **or** integration |

---

## Wave 1 — Scheduler registration

**Goal:** Job appears alongside scrape jobs when enabled.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** In `app/scrapers/scheduler.py` `create_scheduler()`, if `MCA_ALIAS_UPDATE_ENABLED`, `add_job` with stable `id` (e.g. `mca_alias_update`), `IntervalTrigger(hours=...)`, `replace_existing=True`, concurrency controls as in Security table. | `get_jobs()` contains alias job. | `pytest tests/unit/test_scheduler.py -x -q` |
| **1.2** Ensure `app/main.py` lifespan still starts one shared scheduler (no second scheduler instance). | Single `create_scheduler()` used. | `rg -n "create_scheduler" app/main.py app/scrapers/scheduler.py` |

---

## Wave 2 — Idempotency + integration tests

**Goal:** MCA-04/05 hardening.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Implement DB-level idempotency for auto inserts (see Objective). | Two sequential `run_alias_update()` calls: second adds 0 new rows for same inputs. | `pytest tests/integration/test_alias_updater.py -m integration -x -q` |
| **2.2** Fix `run_alias_update` session usage if needed: today all inserts share one `get_session` block—verify **commit** persists all rows; add explicit flush if required for `IntegrityError` handling. | Integration test proves rows visible after run. | Same as above |
| **2.3** Extend scheduler unit test: when `MCA_ALIAS_UPDATE_ENABLED` false, alias job absent (if design toggles registration only via settings). | Toggle behavior covered. | `pytest tests/unit/test_scheduler.py -q` |

---

## Completion checklist

- [ ] Config flags documented in README or AGENTS if that is project pattern for env vars.
- [ ] Scheduler registers job; tests green.
- [ ] Idempotent alias inserts verified.

## Output

After execution, add phase summary artifact per GSD workflow.
