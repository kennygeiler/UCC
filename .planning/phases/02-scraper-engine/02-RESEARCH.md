# Phase 2: Scraper engine — Research

**Researched:** 2026-04-06  
**Domain:** Brownfield scraper subsystem (`app/scrapers/`) vs Kiln Milestone 2 and SCRAPE-01–SCRAPE-06  
**Confidence:** HIGH for repo-local gaps; MEDIUM for external SOS behavior (not probed live)

## Summary

The repo already implements a large slice of Milestone 2: an explicit `SCRAPER_REGISTRY` with **40 states** (10 Tier 1 + 24 Tier 2 + 6 Tier 3), `BaseScraper` with httpx fetch, optional proxy rotation for Tier 3, `RateLimiter` (delay, jitter, backoff, Tier-3 10s floor), `user_agents` rotation, `parsers.py` for table/date normalization, `ScraperRun` / `UCCFiling` persistence in `base.py`, and `create_scheduler()` using APScheduler tier intervals (24h / 36h / 48h). [VERIFIED: workspace files `app/scrapers/registry.py`, `base.py`, `rate_limiter.py`, `scheduler.py`, `user_agents.py`, `parsers.py`]

Gaps versus `.kiln/master-plan.md` M2 and written requirements are mostly **integration, coverage, and verification**: the pipeline FastAPI app does not start the scheduler; **no scraper subclasses `PlaywrightBaseScraper`** (Playwright is inlined in at least CA and likely others—`PlaywrightBaseScraper` is unused [VERIFIED: ripgrep `PlaywrightBaseScraper`]); **Tier 4 (DC, NYC) stubs** are absent from the registry; there is **no dedicated “session manager” module** for cookies/ViewState (master-plan deliverable)—state modules handle flows ad hoc (e.g. TX/NJ comments [VERIFIED: grep ViewState]); **unit tests focus on Tier 1** parse/fetch mocks with **no parallel matrix for Tier 2/3** [VERIFIED: `tests/unit/test_state_scrapers.py`]; **no integration test** proving `scrape()` → `ucc_filings` + `scraper_runs` in one flow [VERIFIED: grep `tests/` for `scrape(`]; smokes are **Tier 1 only** and only assert `build_search_url()` (no full scheduled-profile scrape) [VERIFIED: `tests/smoke/test_scraper_smoke.py`]; CI runs **plain `pytest`** and does **not** install Playwright browsers, so JS/WAF scraper paths are not CI-gated [VERIFIED: `.github/workflows/ci.yml`]. [VERIFIED: workspace]

**Primary recommendation:** Treat Phase 2 planning as **close-the-gaps**: wire `create_scheduler()` into a documented lifespan/entrypoint, extend automated tests (Tier 2/3 parsers, rate-limit timing assertions, DB integration), align smokes with SCRAPE-06 (per-state, scheduled profile, excluded from PR CI), add Tier 4 registry stubs marked skipped, and optionally consolidate Playwright behind `PlaywrightBaseScraper` for C-01.

<user_constraints>
## User Constraints (from CONTEXT.md)

No phase `*-CONTEXT.md` was present under `.planning/phases/02-scraper-engine/` at research time.

**Authoritative constraints (AGENTS.md / Kiln — planner must honor):**

- **C-01:** Short functions (~50 lines), docstrings, tests; no metaprogramming/dynamic imports; structlog with `component`, `status`, `error_type`, `context`.
- **C-09:** Per-state rate limiting with backoff and jitter.
- **C-14:** Python only; no client-side SPA build for product surfaces.
- **C-17:** Tiered scraping strategy (tiers 1–3 + Tier 4 handling at MVP).
- **Registry:** Explicit imports—no dynamic imports for state scrapers (`registry.py` pattern) [VERIFIED: `app/scrapers/registry.py` comment P-019].
- **M2 scope boundary (master plan):** Raw filing ingestion only—no MCA, enrichment, or compliance in this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research support |
|----|-------------|------------------|
| SCRAPE-01 | Tiered framework: httpx + Playwright, registration, per-state rate limits | `BaseScraper` + httpx path exists; `PlaywrightBaseScraper` exists but **unused**; CA uses Playwright directly on `BaseScraper` [VERIFIED: `california.py`]. Rate limits: `RateLimiter` + tier arg on `wait()`. **Gap:** unify Playwright path; prove per-state configurability beyond single global `base_delay`. |
| SCRAPE-02 | Tier 1 → `ucc_filings` + `scraper_runs` | `BaseScraper.scrape()` implements run lifecycle and persist [VERIFIED: `base.py`]. **Gap:** no integration test proving end-to-end DB writes; verify detached `ScraperRun` merge behavior under async sessions. |
| SCRAPE-03 | Tier 2/3 breadth + tests/smokes per master plan | **40** states registered (matches 10+24+6 breakdown) [VERIFIED: `registry.py`]. **Gap:** automated tests/smokes largely Tier-1-centric; Tier 2/3 parsing/fetch not mirrored in `test_state_scrapers.py`. |
| SCRAPE-04 | APScheduler (or equivalent) tier cadence | `create_scheduler()` + `IntervalTrigger` hours per tier [VERIFIED: `scheduler.py`]. **Gap:** not wired into `app/main.py` lifespan or a documented runner—jobs not “observable” in running pipeline without additional wiring. |
| SCRAPE-05 | HTML parsing normalization; C-01 | Shared `parsers.py` (`parse_html_table`, `parse_date`, etc.) [VERIFIED]. **Gap:** some Tier 1 scrapers skip table parsing (API/Playwright JSON) [VERIFIED: comments in `test_state_scrapers.py`]; audit function lengths across `states/*.py` for C-01. |
| SCRAPE-06 | Per-state smoke on scheduled profile; not necessarily every PR | File exists but **only Tier 1**, **only URL check**, `pytest.mark.slow` **not registered** in `pyproject.toml` markers [VERIFIED: `pyproject.toml`, `test_scraper_smoke.py`]. **Gap:** CI runs all tests unless excluded—risk of live network on PRs; no scheduled workflow; no Tier 2/3 smokes. |
</phase_requirements>

## Brownfield gap analysis (vs M2 + SCRAPE-01–06)

| Source expectation | Current repo evidence | Gap / action |
|--------------------|----------------------|--------------|
| M2: Abstract base + registry + tiers | `BaseScraper`, `SCRAPER_REGISTRY` | **LOW:** Tier 4 DC/NYC **stubs missing** from registry (master plan: stub/skip at MVP). |
| M2: Session manager for cookies/ViewState | Ad hoc in states (e.g. TX/NJ) | **HIGH:** No shared session/cookie/ViewState module; planner should add or document intentional deferral. |
| M2: httpx Tier 1 + Playwright support | httpx in `BaseScraper._fetch`; `playwright_base.py` | **MEDIUM:** Playwright support **fragmented** (unused base class; CA imports `async_playwright` directly). |
| M2: Tier 3 proxy rotation | `RateLimiter.get_proxy()` + `PROXY_URL` | **LOW:** Implemented; **verify** all Tier 3 scrapers use tier-aware fetch path (proxy only if httpx path used). |
| M2: User-Agent rotation | `get_random_user_agent()` in `_fetch` | **MET** for httpx path [VERIFIED: `base.py`]. **Gap:** `PlaywrightBaseScraper` uses fixed UA string [VERIFIED: `playwright_base.py`]. |
| M2: `scraper_runs` logging | `_start_run` / `_finish_run` / `_fail_run` | **MET** at code level [VERIFIED: `base.py`]. **Gap:** integration proof + failure-path DB consistency. |
| M2: APScheduler cadence | `scheduler.py` | **PARTIAL:** Code exists; **not started** from pipeline entrypoint [VERIFIED: `app/main.py` has no scheduler]. |
| M2: Smoke per state, daily not on push | `tests/smoke/test_scraper_smoke.py` | **HIGH:** Only Tier 1; shallow assertion; marker/config/CI separation incomplete. |
| M2: Unit tests parsing + integration scraper→DB | `tests/unit/test_state_scrapers.py`, etc. | **MEDIUM:** Tier 1 unit coverage; **missing** Tier 2/3 analogous tests; **missing** scraper→DB integration test. |
| M2: Playwright on Railway | `playwright` dependency | **MEDIUM:** CI does not `playwright install`; document/install in Docker/Railway build or accept untested browser path in CI. [VERIFIED: `ci.yml`] |
| ~45 states / SC-01 wording | 40 production tiers + 0 Tier 4 stubs | **CLARIFY:** 40 matches master-plan **10+24+6**; remaining “45+” may mean Tier 4 placeholders or future states—**confirm** with product whether additional SOS portals are in v1. [ASSUMED] |

## Standard stack (httpx / Playwright / scheduling)

### Core

| Library | Version (declared) | Purpose | Notes |
|---------|-------------------|---------|-------|
| httpx | `>=0.27.0` | Async HTTP for `BaseScraper._fetch` | [VERIFIED: `pyproject.toml`] |
| playwright | `>=1.40.0` | Headless browser where portals require JS/WAF | [VERIFIED: `pyproject.toml`]; runtime needs `playwright install chromium` (or equivalent) — [ASSUMED: Playwright upstream install docs] |
| apscheduler | `>=3.10.0` | Tiered interval jobs | [VERIFIED: `pyproject.toml`, `scheduler.py`] |
| beautifulsoup4 | `>=4.12.0` | HTML parsing in scrapers / helpers | [VERIFIED: `pyproject.toml`]; `parsers.py` uses stdlib `html.parser` — BS4 may be used in state modules (verify per file). |

**Prescriptive guidance for the planner:** Keep **`BaseScraper` as the single orchestration surface** (run lifecycle, persist, rate limit); route **either** httpx (`_fetch`) **or** Playwright by subclassing `PlaywrightBaseScraper` or overriding `_fetch` with shared rate-limit + logging patterns—avoid duplicating Playwright launch boilerplate in each state (C-01).

## Architecture patterns

### Recommended shape (target end-state)

```
app/scrapers/
├── base.py              # lifecycle, httpx fetch, persist
├── playwright_base.py   # JS portals — should be used by concrete states
├── rate_limiter.py      # per-state delay, jitter, backoff, tier-3 floor, proxies
├── registry.py          # explicit SCRAPER_REGISTRY
├── scheduler.py         # APScheduler job factory
├── parsers.py           # shared HTML/table/date helpers
├── user_agents.py       # rotation for httpx
└── states/*.py          # one module per state (thin parse + URL builders)
```

### Pattern: tier-aware rate limiting

Call `await self.rate_limiter.wait(self.state_code, tier=self.tier)` before every network interaction; on failure `record_error`, on success `record_success` [VERIFIED: `base.py`, `rate_limiter.py`].

### Anti-patterns to avoid

- **Unregistered pytest markers / smokes in default CI:** `@pytest.mark.slow` without `addopts`/workflow split risks live SOS traffic on every PR [VERIFIED: `test_scraper_smoke.py`, `ci.yml`].
- **Detached ORM instance across sessions:** `_start_run` returns `ScraperRun` created in one `get_session` block and mutates in another—confirm SQLAlchemy merge/refresh strategy works in integration tests [ASSUMED: needs verification in Phase 2 execution].

## Don’t hand-roll

| Problem | Avoid | Use instead |
|---------|--------|-------------|
| HTML table extraction | Regex on full pages | `parsers.parse_html_table` + state `column_map` [VERIFIED: `parsers.py`] |
| Scheduling scrape loops | ad-hoc `while True` in scrapers | APScheduler + explicit job ids per state [VERIFIED: `scheduler.py`] |
| Per-request delays | `time.sleep` in hot path | `RateLimiter.wait` (async, per-state) [VERIFIED: `rate_limiter.py`] |

## Common pitfalls (C-01, C-09, C-17)

### C-01 — Maintainability

**What goes wrong:** State modules grow past 50 lines with duplicated Playwright/browser setup.  
**Mitigation:** Prefer `PlaywrightBaseScraper`; extract search-term loops and API helpers into small private functions in the same module or a state-specific helper submodule.

### C-09 — Rate limits

**What goes wrong:** Tier 2 treated like Tier 1 against fragile SOS endpoints; backoff never resets.  
**Mitigation:** Always pass `tier` into `wait()`; ensure error paths call `record_error` (already on scrape exception via `_fail_run` [VERIFIED: `base.py`]).

### C-17 — Tier strategy

**What goes wrong:** Tier 3 scrapers issued without `PROXY_URL` in production, hitting blocks; Tier 4 accidentally scheduled.  
**Mitigation:** Registry entries for Tier 4 with `skip`/no-op scraper class; structured log when proxy missing for tier 3 [partially present via `get_proxy` returning None].

## Validation Architecture

> Nyquist / phase verification: map requirements to automated commands and explicit gaps.

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=8`, pytest-asyncio [VERIFIED: `pyproject.toml`] |
| Config | `[tool.pytest.ini_options]` in `pyproject.toml` (`asyncio_mode = auto`, `testpaths = ["tests"]`) |
| Markers registered | `integration` only today — **`slow` / `smoke` not registered** [VERIFIED: `pyproject.toml`] |

### Commands (concrete)

| Intent | Command | Notes |
|--------|---------|--------|
| **PR / default CI parity** | `pip install -e ".[dev]" && alembic upgrade head && pytest -x -v` | Matches `.github/workflows/ci.yml` [VERIFIED] |
| **Exclude network-heavy smokes from local quick run** | `pytest -x -v -m "not slow"` | Requires registering `slow` in `[tool.pytest.ini_options]` markers first; otherwise `-m` behavior is unreliable |
| **Run smoke file as documented** | `pytest tests/smoke/ -m slow -v` | Docstring in `test_scraper_smoke.py` [VERIFIED] |
| **Single scraper unit slice** | `pytest tests/unit/test_state_scrapers.py -x -v` | Tier 1 focused [VERIFIED] |
| **Registry invariants** | `pytest tests/unit/test_scraper_registry.py -x -v` | Subclass checks [VERIFIED] |
| **Rate limiter unit** | `pytest tests/unit/test_rate_limiter.py -x -v` | Exists [VERIFIED: workspace] |

### Phase requirements → tests (target map)

| Req ID | Behavior to prove | Test type | Automated command (target) | File / gap |
|--------|-------------------|-----------|------------------------------|------------|
| SCRAPE-01 | httpx + Playwright paths; per-state limits | unit + optional integration | `pytest tests/unit/test_scraper_base.py tests/unit/test_playwright_base.py` | Add `test_playwright_base.py`; refactor states to use base |
| SCRAPE-02 | filings + scraper_runs persisted | integration | `pytest tests/integration/test_scraper_persist.py -m integration` | **Wave 0 gap — create** |
| SCRAPE-03 | Tier 2/3 parse/fetch with fixtures | unit | `pytest tests/unit/test_tier23_scrapers.py` | **Wave 0 gap — create** |
| SCRAPE-04 | scheduler jobs registered / fired | unit or integration | `pytest tests/unit/test_scheduler.py` | **Wave 0 gap — create** (mock AsyncIOScheduler) |
| SCRAPE-05 | parser edge cases | unit | `pytest tests/unit/test_parsers.py -x -v` | Exists [VERIFIED: workspace] — extend if new parsers added |
| SCRAPE-06 | scheduled-profile smoke, not on PR | smoke + CI workflow | `pytest tests/smoke/ -m slow`; separate scheduled GitHub Action | **Wave 0 gap — CI job + marker registration** |

### Sampling rate (recommended for execution plans)

- **Per task / commit:** `pytest -x -q` (fast subset) or targeted file.
- **Pre-merge / phase gate:** full `pytest -v` with Postgres service env (same as CI).
- **Smokes:** daily or `workflow_dispatch` only; never block PR unless explicitly opted in.

### Wave 0 gaps (blocking confident “done”)

- [ ] Register `slow` (and optionally `smoke`) in `pyproject.toml`; set CI to `pytest -m "not slow"` or move smokes to scheduled workflow.
- [ ] `tests/integration/test_scraper_persist.py` — SCRAPE-02, SCRAPE-01 (DB side).
- [ ] Tier 2/3 unit tests — SCRAPE-03, SCRAPE-05 (beyond existing `test_parsers.py`).
- [ ] `tests/unit/test_scheduler.py` — SCRAPE-04.
- [ ] Document/install Playwright browsers for CI or Railway image — Playwright scraper acceptance.

## Environment availability

**Step 2.6 (target machine):** Not shell-probed in this research session.

| Dependency | Required by | Planner note |
|------------|-------------|--------------|
| Postgres + `DATABASE_URL` | `get_session`, migrations | Same as M1 CI service [VERIFIED: `ci.yml`] |
| Playwright browsers | CA / inlined Playwright scrapers | **Likely missing** in CI until `playwright install` step added [VERIFIED: no step in `ci.yml`] |
| `PROXY_URL` (optional) | Tier 3 rotation | Empty → no proxy (acceptable for dev; production needs explicit config) [VERIFIED: `rate_limiter.py`] |

## Security domain (lightweight)

| ASVS area | Applies | Note |
|-----------|---------|------|
| V5 Input validation | yes | Parsing untrusted HTML/JSON from SOS—favor strict schemas for API JSON; bound memory on HTML parsing |
| V10 Malicious controls | partial | Do not log full page HTML with PII at info level; cap `error_detail` (already truncated in `_fail_run` [VERIFIED: `base.py`]) |

## Assumptions log

| # | Claim | Risk if wrong |
|---|--------|----------------|
| A1 | “45+ states” in master-plan synthesis includes Tier 4 placeholders or non-v1 states | Wrong scope → wrong completion criteria |
| A2 | Detached `ScraperRun` updates succeed without `merge()` in all SQLAlchemy configs | Failed or no-op run updates |

## Sources

### Primary (HIGH — workspace)

- `app/scrapers/*.py`, `tests/smoke/test_scraper_smoke.py`, `tests/unit/test_state_scrapers.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `.kiln/master-plan.md`, `.planning/REQUIREMENTS.md`, `AGENTS.md`

### Secondary

- Playwright install expectations: official Playwright Python docs [NOT FETCHED — mark ASSUMED until docs pulled in planning]

---

## Metadata

**Confidence breakdown:** Standard stack HIGH (pyproject + code); gap analysis HIGH (file-backed); external SOS stability MEDIUM; SQLAlchemy detach behavior MEDIUM until integration test exists.

**Valid until:** ~2026-05-06 (revisit if major scraper refactors land)

## RESEARCH COMPLETE

**Phase:** 2 — Scraper engine  
**Confidence:** HIGH for internal gaps; MEDIUM for runtime/SQLAlchemy edge cases

### Key findings

- Registry and core scraping framework are largely implemented for **40 states**; **Tier 4 stubs** and **scheduler wiring** into the running pipeline are the largest structural gaps vs M2.
- **Playwright** exists both as **`PlaywrightBaseScraper` (unused)** and **inlined** in state modules—consolidation supports C-01 and testability.
- **Tests/smokes/CI** do not yet satisfy SCRAPE-03/06 or M2 acceptance breadth: Tier 2/3 tests, integration persist test, smoke scheduling, and Playwright CI install are missing or incomplete.
- **`pytest.mark.slow` is undocumented in config** and CI runs full pytest—**risk of live network tests on every PR** until markers/workflows are fixed.

### File created

`.planning/phases/02-scraper-engine/02-RESEARCH.md`

### Ready for planning

Planner can draft PLAN.md tasks against the brownfield gap table, Wave 0 test infrastructure, and scheduler/smoke/Playwright CI decisions.
