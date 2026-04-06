---
phase: 1
slug: platform-data-ci
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=8) + pytest-asyncio (`asyncio_mode = auto`) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/ -q --tb=short` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~1–3 minutes (varies with DB integration tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/ -q --tb=short`
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure behavior | Test type | Automated command | Primary artifact | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------------------|--------|
| P1-01-T1 | 01 | 1 | PLAT-01 | T-01-01, T-01-04 | Placeholder DSN only in README; no real secrets in docs | Doc / shell | `test -f README.md && grep -q "pip install -e" README.md && grep -q pytest README.md && grep -q AGENTS.md README.md` | `README.md` | ⬜ pending |
| P1-01-T2 | 01 | 1 | PLAT-01, PLAT-03, PLAT-04 | T-01-01, T-01-03 | No echo of full `DATABASE_URL`; migration failure fails CI | CI config | `grep -q "services:" .github/workflows/ci.yml && grep -q "postgres" .github/workflows/ci.yml && grep -q "alembic upgrade head" .github/workflows/ci.yml` | `.github/workflows/ci.yml` | ⬜ pending |
| P1-01-T3 | 01 | 1 | PLAT-01 | — | Cross-link only | Doc / shell | `grep -q README.md AGENTS.md` | `AGENTS.md` | ⬜ pending |
| P1-02-T1 | 02 | 2 | PLAT-03 | T-02-01 | Minimal fixtures; avoid logging DSN or PII | Integration | `test -f tests/integration/test_db_postgres.py && pytest tests/integration/test_db_postgres.py -q --tb=short` | `tests/integration/test_db_postgres.py` | ⬜ pending |
| P1-02-T2 | 02 | 2 | PLAT-05 | T-02-01, T-02-03 | Synthetic `job_type` / payload only | Integration | `test -f tests/integration/test_job_queue_concurrency.py && pytest tests/integration/test_job_queue_concurrency.py -q --tb=short` | `tests/integration/test_job_queue_concurrency.py` | ⬜ pending |
| P1-02-T3 | 02 | 2 | PLAT-07 | T-02-01 | No secrets in log `context` | Unit | `grep -E "component|status|error_type|context" tests/unit/test_logging.py && pytest tests/unit/test_logging.py -q --tb=short` | `tests/unit/test_logging.py` | ⬜ pending |
| P1-03-T1 | 03 | 3 | PLAT-07 | T-03-02 | No DSN/API keys in structured `context` | Unit + policy | `test 0 -eq "$(grep -r --include='*.py' 'from app' watchdog/ 2>/dev/null | wc -l | tr -d ' ')" && test 0 -eq "$(grep -r --include='*.py' 'from agent' watchdog/ 2>/dev/null | wc -l | tr -d ' ')" && pytest tests/unit/test_watchdog_main.py tests/unit/test_watchdog_logging.py -q --tb=short` | `watchdog/logging_config.py` | ⬜ pending |
| P1-03-T2 | 03 | 3 | PLAT-06 | T-03-01 | Health JSON exposes coarse status only (no connection strings) | Unit + doc | `pytest tests/unit/test_app_main.py tests/unit/test_agent_main.py tests/unit/test_watchdog_main.py -q --tb=short` | `README.md`, `app/main.py`, `agent/main.py`, `watchdog/main.py` | ⬜ pending |
| P1-03-T3 | 03 | 3 | PLAT-02, PLAT-08 | T-03-03, T-03-04 | `send_default_pii=False`; Settings fail-fast unchanged for app/agent | Unit | `test -z "$(grep 'os.environ.get("SENTRY_DSN"' app/main.py agent/main.py 2>/dev/null || true)" && pytest tests/unit/test_config.py tests/unit/test_app_main.py tests/unit/test_agent_main.py tests/unit/test_watchdog_main.py tests/unit/test_sentry_entrypoints.py -q --tb=short` | `app/main.py`, `agent/main.py`, `tests/unit/test_sentry_entrypoints.py` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red*

---

## Wave 0 Requirements

- [x] `tests/integration/test_job_queue_concurrency.py` — delivered by **`02-PLAN.md` Task 2** (PLAT-05)
- [x] CI step: `alembic upgrade head` against Postgres — delivered by **`01-PLAN.md` Task 2** (PLAT-04)
- [x] Sentry init tests for three entrypoints — delivered by **`03-PLAN.md` Task 3** (`tests/unit/test_sentry_entrypoints.py`, PLAT-08)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|---------------------|
| Railway health / restart semantics | PLAT-06 | Needs deploy policy | Confirm `/health` behavior matches `railway.toml` after any health schema change |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] `nyquist_compliant: true` set in frontmatter when plans complete

**Approval:** pending
