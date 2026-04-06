---
phase: 2
slug: scraper-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution (scraper engine).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=8) + pytest-asyncio (`asyncio_mode = auto`) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/ -q --tb=short` |
| **Full suite command** | `pytest` |
| **Scraper-focused** | `pytest tests/unit/test_state_scrapers.py tests/unit/test_scrapers.py -q` |
| **Estimated runtime** | ~2–5 minutes (DB + optional Playwright) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -q --tb=short`
- **After scraper changes:** Include `tests/unit/test_state_scrapers.py` and relevant `tests/smoke/` when applicable
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 300 seconds (integration + smokes may be slower)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure behavior | Test type | Automated command | Primary artifact | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------------------|--------|
| *Populated after PLAN.md files exist* | | | SCRAPE-01–06 | TBD | Rate limits; no secret leakage in logs | unit / integration | `pytest` | `app/scrapers/` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest` markers: `slow` registered for optional network smokes
- [ ] CI: PR path excludes live SOS unless explicitly opted in
- [ ] Playwright: document or CI-install browsers when Playwright tasks run

---

## Failure Modes

| Symptom | Likely cause | Recovery |
|---------|--------------|----------|
| Flaky Tier 1 parse tests | SOS HTML drift | Update fixtures; keep mocks for CI |
| Scheduler double-start | Lifespan not idempotent | Guard with flag or singleton |
| Integration test DB errors | Session/detached objects | Match Phase 1 async session patterns |

---

## Nyquist Compliance

- [ ] Every task row has **Requirement** and **Automated command**
- [ ] Wave 0 installs or stubs test infrastructure before feature waves
- [ ] `nyquist_compliant: true` only after review
