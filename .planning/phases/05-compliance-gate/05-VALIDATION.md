---
phase: 5
slug: compliance-gate
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-06
---

# Phase 5 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Quick run command** | `pytest -m "not slow" -q` |
| **Full suite command** | `pytest -q` |

## Sampling Rate

- After each task commit: `pytest -m "not slow" -q`
- Before `/gsd-verify-work`: full quick suite green

## Per-Task Verification Map

| Task ID | Plan | Requirement | Test Type | Command |
|---------|------|---------------|-----------|---------|
| 5-01-01 | 01 | COMPLY-01 | unit | `pytest tests/unit/test_compliance_gate.py -q` |
| 5-02-01 | 02 | COMPLY-02 | unit | `pytest tests/unit/test_internal_dnc.py -q` |
| 5-03-01 | 03 | COMPLY-03 | unit | `pytest tests/unit/test_datamerch_fallback.py -q` |
| 5-04-01 | 04 | COMPLY-05 | unit + grep | `pytest tests/unit/test_export_compliance_guard.py -q` |

## Validation Sign-Off

- [ ] All tasks have automated verify
- [ ] `nyquist_compliant: true` in frontmatter

**Approval:** pending
