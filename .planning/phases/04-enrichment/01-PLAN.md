---
phase: 4
plan: 01
version: 1
status: draft
wave_count: 2
created: 2026-04-06
title: Waterfall executor + circuit breaker integration (ADR-008)
requirements: [ENRICH-01, ENRICH-03]
depends_on_plans: []
files_touch_estimate:
  - app/enrichment/waterfall.py
  - app/enrichment/circuit_breaker.py
  - app/enrichment/pipeline.py
  - tests/unit/test_waterfall.py
---

# Plan 01 — Waterfall + circuit breakers

## Objective

**ENRICH-01:** Waterfall executor has explicit pass/fail semantics shared with ADR-008: strategies run in order; **open circuit breakers are skipped** (or calls are wrapped so failures increment breakers without silent success). **ENRICH-03 (foundation):** Per-source pybreaker instances are actually consulted on each attempt; logging distinguishes skip vs miss vs hit.

## Threat model

| ID | Threat | Mitigation |
|----|--------|------------|
| T-4-01 | Log leakage of API keys or PII from vendor errors | Log `error_type` + short `context` only; never log response bodies or headers with keys. |
| T-4-02 | Infinite retry loop on broken source | Breaker open → strategy skipped; waterfall may exhaust → handled in Plan 03 retry path. |

## UAT criteria (traceability)

| UAT ID | Criterion | REQ |
|--------|-----------|-----|
| UAT-4.01 | With breaker **open** for source A, waterfall does not invoke A’s callable (observable via mock call counts). | ENRICH-01 |
| UAT-4.02 | With all breakers **closed**, order is PDL → Apollo → OpenCorporates (matches `build_enrichment_waterfall`). | ENRICH-01 |

## Dependencies between plans

- **Plan 02** consumes this: cache + HALT logic assume waterfall/breaker behavior is correct.
- **Plan 04** tests contracts against normalized outputs after mapper (may stub waterfall).

---

## Wave 0 — Fix `WaterfallExecutor` + breaker API

**Read first:** `app/enrichment/waterfall.py`, `app/enrichment/circuit_breaker.py`, `pybreaker` docs (project: `pybreaker` in `pyproject.toml`).

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **0.1** Extend `WaterfallExecutor` to accept optional `breakers: dict[str, pybreaker.CircuitBreaker]` **or** accept strategies as `(name, fn, breaker)` tuples. Before `await strategy(...)`, if breaker exists and **open**, log `waterfall_skip` with `component=enrichment`, `status=skipped`, `context=source name`, and continue. | Grep: `waterfall_skip` appears in `waterfall.py`. | `pytest tests/unit/test_waterfall.py -q` |
| **0.2** Verify pybreaker open-state check: use the library’s public API (e.g. `breaker.opened` or `CircuitBreakerState` — **fix** `is_any_breaker_open()` if `current_state` is wrong). | `circuit_breaker.py` has no AttributeError in unit test that opens a breaker. | `pytest tests/unit/test_circuit_breaker.py -q` (add file if missing) |
| **0.3** Update `build_enrichment_waterfall()` in `app/enrichment/pipeline.py` to pass breakers for `pdl`, `apollo`, `opencorporates` from `BREAKERS`. | `grep -n build_enrichment_waterfall app/enrichment/pipeline.py` shows breaker wiring. | `pytest -m "not slow" -q` |

---

## Wave 1 — Unit tests for waterfall behavior

| Task | Acceptance criteria | Verification |
|------|---------------------|--------------|
| **1.1** Add `tests/unit/test_waterfall.py`: three fake async strategies; force breaker open on middle strategy; assert first and third run, middle not awaited. | Test name contains `breaker` or `skip`. | `pytest tests/unit/test_waterfall.py -q` |
| **1.2** Test `WaterfallExhaustedError` when all strategies fail or skipped (document expected behavior when all breakers open — should raise exhausted with clear errors). | At least one assertion on exception type. | `pytest tests/unit/test_waterfall.py -q` |

---

## must_haves (goal-backward)

1. `WaterfallExecutor` behavior matches docstring: **skip open breakers**, try remainder in order.
2. `is_any_breaker_open()` matches pybreaker’s real API.
3. `build_enrichment_waterfall()` wires per-source breakers.
