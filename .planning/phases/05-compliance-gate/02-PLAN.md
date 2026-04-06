---
phase: 5
plan: 02
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Internal DNC append-only + manager reversal audit (C-12)
requirements: [COMPLY-02]
depends_on_plans: [01-PLAN.md]
files_touch_estimate:
  - app/compliance/internal_dnc.py
  - app/models/dnc.py
  - migrations/versions/
  - tests/unit/test_internal_dnc.py
---

# Plan 02 — Internal DNC (C-12)

## Objective

**COMPLY-02:** **Internal DNC is evaluated before any paid compliance API** (already true in `run_compliance_gate` layer order). **Append-only** DNC adds remain; **reversal** of a block is **manager-only** with an **audit record** (new table or append-only audit row — choose minimal migration).

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-5-03 | Silent delete from `internal_dnc` | No `DELETE` in application code; reversals append audit + optional `is_active` flag if schema requires. |
| T-5-04 | DNC check uses different normalization than storage | Document phone/email normalization for checks vs inserts (reuse one helper). |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-5.03 | `add_to_dnc` cannot remove rows | COMPLY-02 |
| UAT-5.04 | Reversal function requires `added_by` manager id + writes audit row | COMPLY-02 |

## Dependencies between plans

- Depends on **Plan 01** for stable gate tests.

---

## Wave 0 — Schema + API

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Add Alembic migration: e.g. `dnc_reversal_audit` (id, target_dnc_id or phone/email hash, reversed_by, reversed_at, reason) **or** document using `PipelineEvent` for MVP — **pick one** in migration docstring. | `alembic upgrade head` in dev | migration file present |
| **0.2** Add `reverse_dnc_block(...)` (manager-only signature) that **never deletes** `InternalDNC` rows; records audit. | `grep reverse_dnc` in `internal_dnc.py` | unit test calls it |

---

## Wave 1 — Tests

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** `tests/unit/test_internal_dnc.py`: append-only behavior; reversal creates audit; `check_internal_dnc` matches stored phone/email. | `pytest tests/unit/test_internal_dnc.py -q` | green |

---

## must_haves

1. No `DELETE FROM internal_dnc` in app code.
2. Manager reversal path exists with audit artifact.
3. Gate layer 1 still runs before paid layers.
