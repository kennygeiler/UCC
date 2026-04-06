---
phase: 2
plan: 04
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Playwright consolidation, parser/C-01 audit, ViewState session helper or ADR deferral
requirements: [SCRAPE-01, SCRAPE-05]
depends_on_plans: []
files_touch_estimate:
  - app/scrapers/playwright_base.py
  - app/scrapers/states/california.py
  - app/scrapers/parsers.py
  - app/scrapers/states/*.py
  - tests/unit/test_playwright_base.py
  - .kiln/docs/decisions.md
  - app/scrapers/session_context.py
---

# Plan 04 — Playwright path consolidation + parsing maintainability

## Objective

Close SCRAPE-01 gap: **one supported pattern** for Playwright-based scrapers (subclass `PlaywrightBaseScraper` or document rare exceptions). Close SCRAPE-05: parsers and hot-path state modules respect C-01 (function length, docstrings, structlog fields). Either deliver a small shared helper for ASP.NET ViewState / cookie carry-over **or** record an explicit ADR that session management stays per-state until Tier 2/3 consolidation stabilizes—**no silent deferral**.

## Security considerations

| Topic | Requirement |
|-------|-------------|
| Rate limits | Playwright paths must call `await self.rate_limiter.wait(self.state_code, tier=self.tier)` before navigation/network; align with `BaseScraper` contract. |
| Credentials | Do not log page HTML, cookies, or ViewState at INFO; cap error detail (existing `_fail_run` truncation). |
| Proxy | `PlaywrightBaseScraper` must honor `rate_limiter.get_proxy(tier=self.tier)` when launching browser context—document matrix: httpx vs playwright proxy wiring. |

## UAT criteria (traceability)

| UAT ID | Criterion | SCRAPE-* |
|--------|-----------|----------|
| UAT-2.30 | At least one production Playwright state uses `PlaywrightBaseScraper` (expected: CA); grep shows no duplicate `async_playwright` launch blocks in that module. | SCRAPE-01 |
| UAT-2.31 | Any state that cannot migrate documents **Exception** in module docstring + one-line entry in plan summary / ADR table with reason. | SCRAPE-01 |
| UAT-2.32 | Parsers and refactored scraper functions ≤50 lines where touched; public helpers have docstrings. | SCRAPE-05 |
| UAT-2.33 | Either `session_context` helper exists with unit tests **or** ADR-XXX “ViewState/session deferred” with scope and trigger to revisit. | SCRAPE-01/05 |

## Dependencies between plans

- **None (can parallel Plan 02).** If execution touches `app/scrapers/base.py`, run **after** Plan 02 so `_finish_run` / `_fail_run` session fixes land first; otherwise parallel is fine.

---

## Wave 1 — Playwright consolidation

**Goal:** SCRAPE-01 single browser entrypoint.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Refactor `CaliforniaScraper` to subclass `PlaywrightBaseScraper` (or invert: move shared launch/navigation from CA into `playwright_base.py`). Remove duplicated `async_playwright` startup from CA if present. | CA imports path uses base class; behavior unchanged for happy path (manual or existing smoke). | `pytest tests/unit/test_state_scrapers.py -k california -x -v` (extend if needed) |
| **1.2** Add `tests/unit/test_playwright_base.py`: mock Playwright where possible; assert rate-limiter `wait` invoked before navigation hook; assert user-agent policy (if rotating UA for httpx, document fixed UA for Playwright or align with `user_agents` module per product choice). | Tests pass without browser when mocked. | `pytest tests/unit/test_playwright_base.py -x -v` |
| **1.3** Ripgrep audit: list other `async_playwright` / `sync_playwright` usages in `app/scrapers/states/`. For each, migrate or add **documented exception** in module docstring (reason: WAF shape, PDF download, etc.). | Audit list attached to SUMMARY.md. | `rg "playwright" app/scrapers/states/` |

---

## Wave 2 — Parsers + C-01 hot-path audit

**Goal:** SCRAPE-05 maintainability.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** Run C-01 pass on **highest-churn** files: `parsers.py`, any state touched in Wave 1, and any function >50 lines in Tier 1–2 states (use `wc -l` / ripgrep for `def ` blocks). Split into private helpers; preserve behavior. | No new functions >50 lines in edited files; docstrings on new public helpers. | `pytest tests/unit/test_parsers.py -x -v` |
| **2.2** Ensure parser paths use shared `parsers.py` helpers instead of ad hoc regex for table extraction where applicable (per RESEARCH.md). | No regression in parser tests. | `pytest tests/unit/test_parsers.py tests/unit/test_state_scrapers.py -x -v` |

---

## Wave 3 — ViewState / cookie helper **or** ADR

**Goal:** Explicit decision per scope_reduction rules.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **3.1** **Option A:** Add `app/scrapers/session_context.py` (name negotiable) with small functions: e.g. extract `__VIEWSTATE` from HTML, merge cookie jar for httpx follow-up—only what TX/NJ (or one pilot) needs; add unit tests with fixture HTML. **Option B:** Add ADR to `.kiln/docs/decisions.md`: title “Scraper session/ViewState handling deferred”, rationale, states affected, exit criteria for future phase. **Pick one;** if Option B, do not ship a stub module. | Option A: tests pass. Option B: ADR committed with ID. | Option A: `pytest tests/unit/test_session_context.py -x -v`. Option B: file diff review |
| **3.2** Document Playwright install for Railway/Docker in `README.md` or `AGENTS.md` one paragraph (link to Playwright docs)—SCRAPE-01 operational completeness. | Doc exists. | Manual |

---

## Success criteria (plan complete)

1. Primary Playwright state(s) use `PlaywrightBaseScraper` or documented exceptions.
2. Parser/hot-path edits meet C-01 in touched files.
3. ViewState/session either has tested helper or ADR with clear deferral scope.

## Output artifact

After execution: `.planning/phases/02-scraper-engine/2-04-SUMMARY.md`
