---
phase: 5
plan: 04
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Export cannot bypass gate + negative scenarios (M10)
requirements: [COMPLY-05, COMPLY-06]
depends_on_plans: [01-PLAN.md, 02-PLAN.md, 03-PLAN.md]
files_touch_estimate:
  - app/export/adapter.py
  - app/export/ghl_adapter.py
  - tests/unit/test_export_compliance_guard.py
  - tests/unit/test_compliance_negative.py
---

# Plan 04 — Export guard + negative tests

## Objective

**COMPLY-05:** **Prove** no export path calls campaign upsert unless **`compliance_status == "cleared"`** (or gate re-run policy documented). Implement guard in **`CampaignPlatformAdapter`** base or concrete `upsert_lead` / `enqueue_export` entrypoint used by pipeline.

**COMPLY-06:** **Negative tests:** internal DNC hit blocks; DataMerch returns blocked; DNC scrub blocked; litigator blocked — each with **mocked** HTTP / monkeypatched layer returning blocked.

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-5-07 | Adapter bypass for “hot” tier | Guard checks status string, not tier. |
| T-5-08 | Test uses production keys | All negative tests mock httpx or patch gate functions. |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-5.07 | `upsert_lead` raises or no-ops when `compliance_status != cleared` | COMPLY-05 |
| UAT-5.08 | At least four negative tests (one per layer family) | COMPLY-06 |

## Dependencies between plans

- Depends on **Plans 01–03**.

---

## Wave 0 — Export guard

**Read first:** `app/export/adapter.py`, `app/export/ghl_adapter.py`.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Add `assert_compliance_cleared(lead: Lead)` (or inline check) at start of `upsert_lead` / primary export method on `CampaignPlatformAdapter` implementation; raise **`ComplianceNotClearedError`** (new small exception in `app/compliance/` or `app/export/errors.py`). | `grep compliance_status` in `ghl_adapter.py` or adapter | unit test raises |

---

## Wave 1 — Negative + bypass tests

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** `tests/unit/test_compliance_negative.py` — patch `check_internal_dnc` etc. or inject Lead state to simulate blocks; assert `run_compliance_gate` returns False and compliance_status updated. | 4 scenarios minimum | `pytest tests/unit/test_compliance_negative.py -q` |
| **1.2** `tests/unit/test_export_compliance_guard.py` — Lead with `compliance_status=pending` cannot export. | `pytest tests/unit/test_export_compliance_guard.py -q` | green |

---

## must_haves

1. Adapter enforces compliance before network I/O to GHL.
2. Negative coverage for each layer’s block path (mocked).
