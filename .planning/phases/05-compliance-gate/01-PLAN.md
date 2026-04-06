---
phase: 5
plan: 01
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Compliance gate ordering, ComplianceCheck audit rows, Lead persistence
requirements: [COMPLY-01, COMPLY-04]
depends_on_plans: []
files_touch_estimate:
  - app/compliance/gate.py
  - tests/unit/test_compliance_gate.py
---

# Plan 01 — Gate execution + audit trail

## Objective

**COMPLY-01:** Four layers run **strictly in order**; first **blocked** result stops the gate, persists **`compliance_status`**, and returns `False`. **COMPLY-04:** Every layer invocation produces a **`compliance_checks`** row (`pass` or `blocked`) for that `lead_id` and `gate_name`.

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-5-01 | Detached `Lead` updates silently no-op | Use `session.get(Lead, id)` before mutating in `_mark_blocked` / `_mark_compliant`. |
| T-5-02 | Layer skipped without log row | Assert test: row count == 4 for full pass, early stop logs block row then stop. |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-5.01 | Order is internal_dnc → datamerch → dnc_scrub → blacklist_alliance | COMPLY-01 |
| UAT-5.02 | Each layer writes `ComplianceCheck` before short-circuit | COMPLY-04 |

## Dependencies between plans

- **Plan 03** may extend HTTP clients; this plan stabilizes orchestration + DB writes.

---

## Wave 0 — Fix Lead persistence + logging order

**Read first:** `app/compliance/gate.py`, `app/models/lead.py`, `app/models/dnc.py` (`ComplianceCheck`).

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** In `_mark_blocked` and `_mark_compliant`, load `Lead` with `await session.get(Lead, lead.id)` (or merge) before setting `compliance_status`; avoid mutating a detached instance without merge. | `grep -n session.get(Lead` in `gate.py` | `pytest tests/unit/test_compliance_gate.py -q` |
| **0.2** Ensure `_log_check` runs for the blocking layer **before** `_mark_blocked` (order already close — verify in code review + test). | Test asserts `ComplianceCheck` exists for blocking gate when blocked | `pytest tests/unit/test_compliance_gate.py -q` |

---

## Wave 1 — Unit tests (async, mocked layers)

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add `tests/unit/test_compliance_gate.py`: monkeypatch each layer to controlled return values; assert **call order** and **number of ComplianceCheck rows** (use in-memory SQLite or mock `get_session` per project patterns). | At least one test for **full pass** (4 checks) and one for **block on layer 2** (2 checks: internal_dnc pass logged, datamerch blocked). | `pytest tests/unit/test_compliance_gate.py -q` |

---

## must_haves

1. `run_compliance_gate` is the single orchestrator for layer order.
2. `ComplianceCheck` rows exist for each executed layer up to termination.
3. Lead rows persist `compliance_status` updates reliably.
