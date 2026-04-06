---
phase: 4
plan: 04
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Contract tests + enrichment completeness gate (ENRICH-05/06)
requirements: [ENRICH-05, ENRICH-06]
depends_on_plans: [01-PLAN.md, 02-PLAN.md, 03-PLAN.md]
files_touch_estimate:
  - app/enrichment/normalize.py
  - app/enrichment/pipeline.py
  - tests/contract/test_enrichment_contracts.py
  - tests/fixtures/enrichment/
  - tests/unit/test_enrichment_pipeline.py
---

# Plan 04 — Contracts + partial enrichment safety

## Objective

**ENRICH-05:** Contract tests lock **production-path** JSON shapes for PDL, Apollo, OpenCorporates (minimum: fields the mapper reads — `phone`, `email`, revenue, owner fields as applicable). Tests use **checked-in fixtures**, not live HTTP in default CI.

**ENRICH-06:** A lead is **`enrichment_status="complete"`** only when **required fields** are present after normalization (define explicitly: e.g. non-empty `phone`, `email`, `owner_name`, `estimated_revenue` — adjust to product minimum, but **must** match a single function `enrichment_meets_bar(data: dict) -> bool` used by `_apply_enrichment`). Otherwise status stays **`pending`**, **`failed`**, or **`incomplete`** (pick one string and document; avoid `complete`).

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-4-06 | Marking complete with missing contact info exports bad leads | Gate in `_apply_enrichment` + unit tests for partial payloads. |
| T-4-07 | Fixture files contain real PII | Use synthetic values only in `tests/fixtures/enrichment/*.json`. |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-4.07 | Mapper raises or returns partial dict; lead **not** complete until bar met. | ENRICH-06 |
| UAT-4.08 | Contract test fails if fixture field removed (schema lock). | ENRICH-05 |

## Dependencies between plans

- Depends on **Plans 01–03** (stable pipeline and retry paths).

---

## Wave 0 — Normalization + completeness bar

**Read first:** `app/enrichment/sources.py`, `app/enrichment/pipeline.py`.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Add `app/enrichment/normalize.py` with `normalize_vendor_response(source: str, raw: dict) -> dict` returning canonical keys: `phone`, `email`, `owner_name`, `estimated_revenue` (types: `str | None`, `float | None`). | Each vendor path covered by unit test with minimal raw JSON. | `pytest tests/unit/test_enrichment_normalize.py -q` |
| **0.2** Implement `enrichment_meets_bar(data: dict) -> bool` — **all four** keys present and non-empty after strip (or document if revenue optional). | Docstring states policy. | Unit tests: partial dict → False |
| **0.3** Change `_apply_enrichment` to set `enrichment_status="complete"` **only if** `enrichment_meets_bar(data)`; else set **`incomplete`** or **`failed`** (choose one; **`incomplete`** preferred for retry eligibility). | Grep `enrichment_status` assignments | `pytest tests/unit/test_enrichment_pipeline.py -q` |

---

## Wave 1 — Contract tests

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add `tests/fixtures/enrichment/pdl_sample.json` (synthetic). Test: `normalize_vendor_response("pdl", json.load(...))` returns expected canonical fields. | Fixture committed | `pytest tests/contract/test_enrichment_contracts.py -q` |
| **1.2** Repeat for `apollo_sample.json`, `opencorporates_sample.json` (minimal viable keys). | Three fixtures + tests | `pytest tests/contract/ -q` |
| **1.3** Run `pytest -m "not slow" -q` full quick suite green. | CI parity | exit 0 |

---

## must_haves

1. No `enrichment_status="complete"` without `enrichment_meets_bar` True.
2. At least three contract fixtures aligned with mapper.
3. Canonical normalization isolated from raw httpx response handling (call normalize from pipeline after waterfall returns).
