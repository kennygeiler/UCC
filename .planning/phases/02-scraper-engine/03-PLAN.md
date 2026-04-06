---
phase: 2
plan: 03
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Tier 2/3 unit + smoke breadth; per-state smoke contract; scheduled profile docs
requirements: [SCRAPE-03, SCRAPE-06]
depends_on_plans: ["01-PLAN.md"]
files_touch_estimate:
  - tests/unit/test_state_scrapers.py
  - tests/unit/test_tier23_scrapers.py
  - tests/smoke/test_scraper_smoke.py
  - tests/smoke/conftest.py
  - .github/workflows/scraper-smokes-scheduled.yml
  - README.md
---

# Plan 03 — Tier 2/3 coverage, smokes, scheduled workflow

## Objective

Meet SCRAPE-03 breadth with **representative** Tier 2 and Tier 3 unit tests (fixture HTML / mocked fetch, not live network in unit tier). Meet SCRAPE-06 by defining a **per-state smoke contract**: each registered production scraper has a smoke entry point (URL build, or full scheduled profile behind `slow`), with PR CI excluding `slow` (from Plan 01) and scheduled/dispatch workflow running the slow suite.

## Security considerations

| Topic | Requirement |
|-------|-------------|
| Rate limits | Smoke tests that hit live SOS must remain `@pytest.mark.slow`; never add live fetches to default CI. |
| Logging | Smokes must not print full responses; keep assertions to status codes or truncated snippets. |
| Proxy | Tier 3 smokes: document optional `PROXY_URL` for scheduled runners; do not fail PR when unset. |

## UAT criteria (traceability)

| UAT ID | Criterion | SCRAPE-* |
|--------|-----------|----------|
| UAT-2.20 | Unit tests cover at least **two Tier 2** and **two Tier 3** states’ `parse_response` / `build_search_url` with fixtures. | SCRAPE-03 |
| UAT-2.21 | Smoke module enumerates every **non-stub** registry state (tiers 1–3) with a defined test or explicit `pytest.param(..., marks=pytest.mark.skip(reason=...))` with reason (documented exception). | SCRAPE-06 |
| UAT-2.22 | Scheduled GitHub Action (or doc-only fallback if repo policy forbids) runs slow smokes daily or on demand. | SCRAPE-06 |

## Dependencies between plans

- **Depends on Plan 01:** CI must already exclude `-m "not slow"`; markers registered.

---

## Wave 1 — Tier 2/3 unit tests (fixtures)

**Goal:** SCRAPE-03 automated proof without live network.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add `tests/unit/test_tier23_scrapers.py` (or extend `test_state_scrapers.py` if cleaner). Pick **two Tier 2** (e.g. `CO`, `MI`) and **two Tier 3** (e.g. `DE`, `NV`)—align with available sample HTML in `tests/fixtures/` or inline minimal HTML strings. Test `parse_response` column mapping and edge cases; mock `_fetch` if base tests require it. | Four states covered; tests deterministic. | `pytest tests/unit/test_tier23_scrapers.py -x -v` |
| **1.2** Add `build_search_url()` assertions (valid `https` scheme, required path/query tokens per state if documented). | URL shape regressions caught. | Same command |

---

## Wave 2 — Per-state smoke contract

**Goal:** SCRAPE-06 explicit coverage matrix for smokes.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Refactor `tests/smoke/test_scraper_smoke.py`: parametrize over **all tier 1–3** registry codes (derive from `SCRAPER_REGISTRY` excluding Tier 4 stubs). Tier 1: keep live `build_search_url` check or shallow fetch as today. Tier 2/3: either same contract (URL only) **or** mark full scrape as `slow` + optional `pytest.mark.skip` for Playwright-only until browsers exist on runner—**document** in module docstring. | Every production state has a smoke row or explicit skip with reason. | `pytest tests/smoke/ -m slow --collect-only` |
| **2.2** Tag all smoke tests `@pytest.mark.smoke` and `@pytest.mark.slow` where network applies. | Markers consistent with Plan 01. | `pytest --markers` |

---

## Wave 3 — Scheduled workflow + documentation

**Goal:** Operators know how to run scheduled profile; automation exists where allowed.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **3.1** Add **the single canonical** `.github/workflows/scraper-smokes-scheduled.yml` (Plan 01 intentionally does **not** create this file). Include `on.schedule` (daily cron) + `workflow_dispatch`; checkout, Python, `pip install -e ".[dev]"`, migrations; optional `playwright install chromium` only if smoke contract requires it—otherwise comment that browser smokes need a manual/browser-equipped runner. Run `pytest tests/smoke/ -m slow -v --maxfail=1`; document optional `PROXY_URL` secret for Tier 3. | One workflow file; valid YAML; no duplicate workflow under another name for the same job. | `python -c "import yaml; yaml.safe_load(open('.github/workflows/scraper-smokes-scheduled.yml'))"` |
| **3.2** Document in `README.md` (short): PR runs `pytest -m "not slow"` (Plan 01); daily/on-demand smokes via this workflow; local `pytest tests/smoke/ -m slow`. | Doc matches behavior. | Manual read |

---

## Success criteria (plan complete)

1. Tier 2/3 unit coverage exists (≥2 states each tier).
2. Smoke file acts as contract for all tier 1–3 registry entries.
3. Scheduled/dispatch workflow documented and present (sole owner of `scraper-smokes-scheduled.yml`).

## Output artifact

After execution: `.planning/phases/02-scraper-engine/2-03-SUMMARY.md`
