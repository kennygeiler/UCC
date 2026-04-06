---
phase: 3
slug: mca-detection-scoring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-06
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for MCA detection, scoring, pipeline, and alias updater.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=8) + pytest-asyncio (`asyncio_mode = auto`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/test_detector.py tests/unit/test_scorer.py -q --tb=short` |
| **Full suite command** | `pytest -m "not slow"` |
| **MCA-focused** | `pytest tests/unit/test_detector.py tests/unit/test_scorer.py tests/integration/ -k mca -q` |
| **Estimated runtime** | ~1–4 minutes |

---

## Sampling Rate

- **After every task commit:** Run quick MCA unit tests above
- **After waves touching DB:** Run `pytest -m "not slow"` plus integration tests that apply
- **Before `/gsd-verify-work`:** Full non-slow suite green

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test type | Automated command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| *Filled after PLAN.md files exist* | | | MCA-01–05 | unit / integration | `pytest` | ⬜ pending |

---

## Nyquist Compliance

- [ ] Every task has Requirement ID and automated command
- [ ] `nyquist_compliant: true` only after review
