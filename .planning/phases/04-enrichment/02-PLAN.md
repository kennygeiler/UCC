---
phase: 4
plan: 02
version: 1
status: draft
wave_count: 3
created: 2026-04-06
title: Permanent cache correctness + HALT semantics (C-03, C-08)
requirements: [ENRICH-02, ENRICH-03]
depends_on_plans: [01-PLAN.md]
files_touch_estimate:
  - app/enrichment/cache.py
  - app/enrichment/pipeline.py
  - app/config.py
  - app/models/operations.py
  - tests/unit/test_enrichment_cache.py
  - tests/unit/test_enrichment_halt.py
---

# Plan 02 — Enrichment cache + HALT

## Objective

**ENRICH-02:** Cache reads/writes use a **consistent** `(source_api, input_key)` scheme; results remain **permanent** (no TTL, no deletes). **ENRICH-03:** When enrichment sources exceed the **documented failure policy** (see `.kiln/docs/arch-constraints.md`: **>20% errors in 5 minutes**), the pipeline enters **HALT**: `check_pipeline_halt()` returns true, `PipelineEvent` records HALT, export-bound work must not proceed (enrichment batch processes zero leads while halted).

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-4-02 | Stale cache returns wrong vendor data | Key includes `source_api` + stable business key; document key format in `cache.py` docstring. |
| T-4-03 | HALT spam | Log once per transition to HALT or rate-limit identical events (implementation choice — document in code comment). |

## UAT criteria

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-4.03 | Same `(source_api, input_key)` hit on second lead skips HTTP (mock httpx). | ENRICH-02 |
| UAT-4.04 | Simulated error rate over threshold triggers HALT flag / event within the design. | ENRICH-03 |

## Dependencies between plans

- Depends on **Plan 01** (waterfall/breaker wiring).
- **Plan 03** will call `check_pipeline_halt` from retry runner — keep function stable.

---

## Wave 0 — Cache key consistency

**Read first:** `app/enrichment/cache.py`, `app/enrichment/pipeline.py`.

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Fix mismatch: `get_cached` and `store_cached` must use the **same** `source_api` for a given cached payload. Recommended: cache per **winning source** (e.g. `"pdl"`) + `input_key = f"{normalized_name}\|{state}"` (define normalization helper or reuse debtor key pattern). | Remove use of literal `"enrichment"` as `source_api` unless intentionally one bucket (if one bucket, document and use for both get and store). | `grep enrichment_cache pipeline.py cache.py` — consistent keys |
| **0.2** Add unit test: after `store_cached("apollo", key, {...})`, `get_cached("apollo", key)` returns dict without HTTP. | Test in `tests/unit/test_enrichment_cache.py`. | `pytest tests/unit/test_enrichment_cache.py -q` |

---

## Wave 1 — Error-rate window + HALT

**Read first:** `.kiln/docs/arch-constraints.md` (C-03), `app/enrichment/circuit_breaker.py`, `app/models/operations.py` (`PipelineEvent`).

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add settings (names illustrative, pick consistent snake_case): `ENRICH_BREAKER_ERROR_WINDOW_SECONDS` default `300`, `ENRICH_BREAKER_ERROR_RATE_THRESHOLD` default `0.2`. | Keys appear in `app/config.py` with defaults. | `grep ENRICH_BREAKER app/config.py` |
| **1.2** Implement **rolling** failure tracking per source: e.g. in-memory ring buffer of timestamps (failures only) per source name, **or** query recent `pipeline_events` / dedicated table — **must** be testable without 5-minute wall clock (inject clock or shorten window in tests). When `failures_in_window / attempts_in_window >= threshold`, mark breaker open **or** set a `halt_enrichment` flag checked by `check_pipeline_halt`. | Unit test forces threshold with fake clock or tiny window override via `Settings`. | `pytest tests/unit/test_enrichment_halt.py -q` |
| **1.3** On HALT: insert `PipelineEvent` with `event_type="HALT"`, `component="enrichment"`, detail string without secrets. | Grep `PipelineEvent` + `HALT` in pipeline or breaker module. | `pytest -m "not slow" -q` |

---

## Wave 2 — Pipeline integration

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **2.1** `run_enrichment_pipeline` returns `0` processed when `check_pipeline_halt()` is true **before** batch loop. | Log field `status=halted` or equivalent. | `pytest tests/unit/test_enrichment_pipeline.py -k halt -q` |

---

## must_haves

1. No TTL or delete paths added to `EnrichmentCache` usage (C-08).
2. HALT observable via `check_pipeline_halt` + `PipelineEvent`.
3. Cache get/store keys are provably consistent in tests.
