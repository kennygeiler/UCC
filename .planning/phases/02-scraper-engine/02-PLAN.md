---
phase: 2
plan: 02
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Integration test — scrape path persists ucc_filings + scraper_runs; session detach fixes
requirements: [SCRAPE-02]
depends_on_plans: ["01-PLAN.md"]
files_touch_estimate:
  - app/scrapers/base.py
  - tests/integration/test_scraper_persist.py
  - tests/conftest.py
---

# Plan 02 — Scraper → DB integration (filings + runs)

## Objective

Prove SCRAPE-02 end-to-end: a scrape cycle inserts or deduplicates `ucc_filings` and writes a coherent `scraper_runs` audit row for success and failure paths. Fix any SQLAlchemy async session issues where `ScraperRun` is created in one `get_session()` block and mutated in another (`_start_run` returns a detached instance—`_finish_run` / `_fail_run` must `merge()` or re-load by `run_id` before update).

## Security considerations

| Topic | Requirement |
|-------|-------------|
| Rate limits | Integration test must use a **subclass** of `BaseScraper` that overrides `_fetch` to return fixture HTML—**no live SOS** calls in CI. |
| Logging | Do not log full HTML fixtures at INFO; use DEBUG only if needed, truncated. |
| Proxy / credentials | Test scraper must not read `PROXY_URL` for httpx (override fetch). |

## UAT criteria (traceability)

| UAT ID | Criterion | SCRAPE-* |
|--------|-----------|----------|
| UAT-2.10 | After a controlled scrape, Postgres contains expected `ucc_filings` rows and one `scraper_runs` row with `status=completed` and matching `records_found`. | SCRAPE-02 |
| UAT-2.11 | On forced parse/fetch failure, `scraper_runs.status=failed` and `error_detail` bounded; no orphan `running` rows left indefinitely in test. | SCRAPE-02 |

## Dependencies between plans

- **Depends on Plan 01:** Wave 2 regression uses `pytest -m "not slow"`, which requires registered `slow`/`smoke` markers and CI-aligned behavior.
- Prefer **not** using `CaliforniaScraper` or other Playwright scrapers in this test (avoids browser deps). Plan 04 refactors do not block this plan.

---

## Wave 1 — Integration test (httpx path, mocked fetch)

**Goal:** Red test defining contracts; green with minimal scraper implementation in test module or `tests/fixtures/`.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add `tests/integration/test_scraper_persist.py` marked `@pytest.mark.integration`. Define `FakeTier1Scraper(BaseScraper)` with fixed `state_code` (e.g. `ZZ` **only if** allowed by registry constraints—prefer using a real Tier 1 code with a **test-only** subclass not registered, e.g. module-local class with `state_code="CA"` but not the production class, **or** register a test double in conftest only). `build_search_url` returns `https://example.test/search`. `_fetch` override returns static HTML; `parse_response` returns 1–2 dicts matching `UCCFiling` required fields. | Test inserts filings; asserts `ScraperRun` completed with correct `records_found`. | `pytest tests/integration/test_scraper_persist.py -x -v -m integration` |
| **1.2** Add negative path test: `parse_response` raises or `_fetch` raises; assert `failed` run and no unbounded error strings in DB. | Failure path persists failed run. | Same file, `pytest ... -k fail` |

**Note:** If using a synthetic `state_code`, ensure it does not collide with production uniqueness rules; use valid `UCCFiling` field shapes per `app/models/filing.py`.

---

## Wave 2 — Fix `BaseScraper` run lifecycle for cross-session updates

**Goal:** All ORM updates to `ScraperRun` attach to the active session correctly (merge or `select` by id).

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Refactor `_finish_run` and `_fail_run` to load or merge `ScraperRun` by `run.id` inside the new session block; keep functions under ~50 lines (C-01); docstring notes detach safety. | Integration tests pass; no `DetachedInstanceError` in logs. | `pytest tests/integration/test_scraper_persist.py -x -v -m integration` |
| **2.2** Run regression: `pytest tests/unit/test_scraper_base.py -x -v` (or nearest base scraper tests) plus `pytest -x -v -m "not slow"` for full non-smoke suite. | No regressions. | `pytest -x -v -m "not slow"` |

---

## Success criteria (plan complete)

1. Integration test demonstrates successful scrape → DB rows.
2. Failure path writes failed `scraper_runs` row.
3. `_finish_run` / `_fail_run` are safe across async sessions.

## Output artifact

After execution: `.planning/phases/02-scraper-engine/2-02-SUMMARY.md`
