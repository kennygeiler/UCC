---
phase: 2
plan: 01
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Scraper scheduler wiring, pytest markers, CI split, Tier 4 registry stubs
requirements: [SCRAPE-04, SCRAPE-06]
depends_on_plans: []
files_touch_estimate:
  - pyproject.toml
  - app/main.py
  - app/scrapers/scheduler.py
  - app/scrapers/registry.py
  - tests/unit/test_scheduler.py
  - .github/workflows/ci.yml
  - README.md
  - AGENTS.md
---

# Plan 01 — Scheduler wiring, CI/pytest markers, Tier 4 stubs

## Objective

Make tiered scrape jobs observable in the running pipeline service (SCRAPE-04), register and enforce `slow`/`smoke` markers so live SOS tests are not run on every PR (SCRAPE-06 foundation), and add optional Tier 4 registry placeholders (DC, NYC) that never execute production scrapes—only explicit skip/no-op behavior per C-17 MVP boundary.

## Security considerations

| Topic | Requirement |
|-------|-------------|
| Rate limits | Scheduler must reuse a **single shared** `RateLimiter` instance across all jobs (same pattern as `create_scheduler()` today); do not instantiate per-job limiters that reset backoff state. |
| Credentials / secrets | Never log `PROXY_URL`, database URLs, or Basic Auth material; scheduler startup logs should only emit job counts and tier intervals. |
| Proxy env | `PROXY_URL` is optional; if absent, Tier 3 jobs still schedule—document that production should set proxy for Tier 3; no logging of proxy host. |
| Untrusted input | N/A for this plan (no new parsers). |

## UAT criteria (traceability)

| UAT ID | Criterion (operator-visible) | SCRAPE-* |
|--------|------------------------------|----------|
| UAT-2.01 | With pipeline running, logs or metrics show scheduler configured and jobs registered per state tier. | SCRAPE-04 |
| UAT-2.02 | Default CI / `pytest` on PR does not execute `@pytest.mark.slow` scraper smokes. | SCRAPE-06 |
| UAT-2.03 | `pytest -m slow` can run smoke suite intentionally; scheduled GitHub workflow is **Plan 03** (single canonical workflow file). | SCRAPE-06 |
| UAT-2.04 | Registry lists DC/NYC (or equivalent Tier 4 keys) as skipped/stub—no accidental full scrape. | SCRAPE-04 / C-17 |

## Dependencies between plans

- **None** (foundational). Plan 03 assumes this plan’s marker + CI behavior and **owns** `.github/workflows/scraper-smokes-scheduled.yml` (avoid duplicate workflow definitions).

## SCRAPE-01–06 coverage (phase)

| Requirement | Plan(s) | Notes |
|-------------|---------|--------|
| SCRAPE-01 | 04 | Playwright path + framework consolidation; httpx path exercised in 02 integration. |
| SCRAPE-02 | 02 | Scrape → `ucc_filings` + `scraper_runs` integration proof. |
| SCRAPE-03 | 03 | Tier 2/3 unit breadth (fixtures). |
| SCRAPE-04 | 01 | APScheduler wired to pipeline lifespan; Tier 4 stubs. |
| SCRAPE-05 | 04 | Parser / C-01 audit on hot paths. |
| SCRAPE-06 | 01, 03 | Markers + PR CI exclude `slow`; per-state smoke contract + scheduled workflow in 03. |

---

## Wave 0 — Pytest markers + scheduler unit test

**Goal:** Registered markers and fast proof that `create_scheduler()` builds the expected job graph.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Add `slow` and `smoke` to `[tool.pytest.ini_options].markers` in `pyproject.toml` with descriptions (live network / scheduled profile). | `pytest --markers` lists `slow` and `smoke` with help text. | `pytest --markers \| grep -E 'slow\|smoke'` |
| **0.2** Add `tests/unit/test_scheduler.py`: construct scheduler via `create_scheduler()`, assert job count equals `len(SCRAPER_REGISTRY)` (after Tier 4 stubs, adjust expected count), and spot-check one Tier 1/2/3 job id and trigger class. Use `AsyncIOScheduler` without starting long-running loops—inspect `get_jobs()` only. | Test file passes; no network. | `pytest tests/unit/test_scheduler.py -x -v` |

---

## Wave 1 — Wire `create_scheduler()` into FastAPI lifespan

**Goal:** SCRAPE-04 satisfied for the pipeline process: scheduler starts with app, stops on shutdown.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** In `app/main.py` `lifespan`: import `create_scheduler`, store scheduler on `app.state` (or module-level), call `scheduler.start()` **before** `yield`, and `scheduler.shutdown(wait=True)` in the shutdown branch **after** `yield`. | Starting uvicorn logs scheduler configured; clean shutdown without dangling tasks. | `pytest tests/unit/test_scheduler.py -x -v` plus optional: `timeout 3 uvicorn app.main:app --host 127.0.0.1 --port 8999` |
| **1.2** Gate scheduler with settings flag if project already has pattern (e.g. `Settings.SCRAPER_SCHEDULER_ENABLED: bool = True`) so tests can disable; **default ON** for production parity. Document env var in `README.md` or `AGENTS.md` one short subsection. | When flag false, lifespan does not start APScheduler. | `pytest` subset covering settings (add small test if needed): `pytest tests/ -k scheduler -x -v` or dedicated test |

---

## Wave 2 — CI excludes slow smokes; Tier 4 stubs (scheduled workflow → Plan 03)

**Goal:** SCRAPE-06 PR safety via marker exclusion; Tier 4 visible but skipped. **Do not** add `scraper-smokes-scheduled.yml` here—Plan 03 delivers the single scheduled/dispatch workflow to prevent duplicate or conflicting workflow files.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Update `.github/workflows/ci.yml` test step to: `pytest -x -v -m "not slow"` (keep `alembic upgrade head` before tests). | CI command excludes slow tests by marker expression. | Local: `pytest -x -v -m "not slow"` |
| **2.2** Tier 4 stubs: add explicit registry keys for **DC** and **NYC** (or `NYC` separate from `NY` if product distinguishes NYC portal—align with master plan). Each maps to a stub class: `scrape()` returns 0 immediately and logs `tier4_skipped` with `component=scraper`, or pytest.skip-style behavior for smokes only—**must not** hit live URLs. Update `create_scheduler()` to **omit** Tier 4 jobs OR register jobs that call no-op immediately—**no** IntervalTrigger hammering absent portals. | Tier 4 entries importable; scheduler unit test updated; no HTTP for Tier 4 stubs. | `pytest tests/unit/test_scheduler.py tests/unit/test_scraper_registry.py -x -v` |

---

## Success criteria (plan complete)

1. `slow`/`smoke` markers registered; PR CI uses `-m "not slow"`.
2. Pipeline lifespan starts and stops APScheduler with documented flag.
3. Tier 4 DC/NYC stubs exist and are not scheduled for real scrapes.
4. Unit test proves scheduler job registration shape.
5. No `.github/workflows/scraper-smokes-scheduled.yml` in this plan’s deliverables (Plan 03 only).

## Output artifact

After execution: `.planning/phases/02-scraper-engine/2-01-SUMMARY.md` (or project’s standard summary name).
