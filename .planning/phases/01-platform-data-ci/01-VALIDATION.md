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

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | PLAT-* | — | N/A | unit/integration | `pytest` | ⬜ | ⬜ pending |

*Populate after PLAN.md tasks are numbered. Status: ⬜ pending · ✅ green · ❌ red*

---

## Wave 0 Requirements

- [ ] `tests/integration/test_job_queue_concurrency.py` — concurrent `claim()` proof (PLAT-05) if not created in-plan
- [ ] CI step or documented manual gate: `alembic upgrade head` against Postgres (PLAT-04)
- [ ] Sentry init assertion tests for three entrypoints (PLAT-08)

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
