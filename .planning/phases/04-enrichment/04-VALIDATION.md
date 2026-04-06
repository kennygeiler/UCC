---
phase: 4
slug: enrichment
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-06
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest -m "not slow" -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5–15 seconds (unit); integration skip if no Postgres |

---

## Sampling Rate

- **After every task commit:** Run `pytest -m "not slow" -q`
- **After every plan wave:** Run `pytest -m "not slow" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for quick run

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | ENRICH-01 | T-4-01 | No secret logging | unit | `pytest tests/unit/test_waterfall.py -q` | ⬜ W0 | ⬜ pending |
| 4-02-01 | 02 | 0 | ENRICH-02 | T-4-02 | Cache stores JSON only | unit | `pytest tests/unit/test_enrichment_cache.py -q` | ⬜ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | ENRICH-03 | T-4-03 | HALT without PII | unit/integration | `pytest tests/unit/test_enrichment_halt.py -q` | ⬜ W0 | ⬜ pending |
| 4-03-01 | 03 | 0 | ENRICH-04 | — | N/A | unit | `pytest tests/unit/test_enrichment_retry.py -q` | ⬜ W0 | ⬜ pending |
| 4-04-01 | 04 | 0 | ENRICH-05 | — | Fixtures only, no live keys | contract | `pytest tests/contract/test_enrichment_contracts.py -q` | ⬜ W0 | ⬜ pending |
| 4-04-02 | 04 | 1 | ENRICH-06 | T-4-06 | Incomplete leads stay non-complete | unit | `pytest tests/unit/test_enrichment_pipeline.py -q` | ⬜ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Existing `pyproject.toml` markers — `integration`, `slow`
- [x] `tests/conftest.py` — env + engine cache clear

*Wave 0 adds new test files as listed in plans 01–04.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live PDL/Apollo responses | ENRICH-05 | Keys + billing | Run contract tests with fixtures; optional staging smoke outside CI |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s for quick run
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
