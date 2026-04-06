# Phase 4: Enrichment — Research

**Date:** 2026-04-06  
**Question:** What do we need to know to implement ENRICH-01–06 against the current tree?

## RESEARCH COMPLETE

## Current implementation snapshot

| Area | File(s) | Notes |
|------|---------|--------|
| Waterfall | `app/enrichment/waterfall.py` | `WaterfallExecutor` tries strategies sequentially; docstring mentions circuit breakers but **executor does not skip or wrap strategies with breakers**. |
| Sources | `app/enrichment/sources.py` | PDL, Apollo, OpenCorporates, Whitepages, Twilio — httpx calls; **raw API JSON** returned. |
| Pipeline | `app/enrichment/pipeline.py` | `build_enrichment_waterfall()` order: PDL → Apollo → OpenCorporates; **cache read uses** `source_api="enrichment"` **but store uses** winning `source` name — **key mismatch risk**. `_apply_enrichment` sets `enrichment_status="complete"` **without validating required fields** (ENRICH-06 gap). |
| Cache | `app/enrichment/cache.py` | `get_cached` / `store_cached` — Postgres `EnrichmentCache` (`app/models/dnc.py`), JSONB, no TTL ✓. |
| Breakers | `app/enrichment/circuit_breaker.py` | pybreaker per source; `is_any_breaker_open()` uses `b.current_state == "open"` — **verify pybreaker API** (`state` vs `current_state`). |
| Retry | `app/models/job.py` | `EnrichmentRetryQueue` has `lead_id`, `source`, `attempt_count`, `next_retry_at` — **no processor** in scheduler from this snapshot. |

## Policy alignment (C-03)

`.kiln/docs/arch-constraints.md`: **>20% errors in 5 minutes** → breaker / HALT. Current code uses **fixed fail_max** breakers and **does not** compute error rates. Plans must either implement rolling-window metrics (Postgres `pipeline_events` + counters) or a justified mapping with tests.

## Testing strategy

- **Unit:** waterfall ordering, breaker gating, mapper normalization, completeness gate.  
- **Integration:** Postgres cache + retry queue + HALT event (with DB).  
- **Contract:** golden JSON fixtures per vendor response shape used in production paths.

## Validation Architecture

### Dimension 1 — Correctness

Automated tests prove: waterfall order, cache hit avoids HTTP, breaker open skips source, HALT recorded when policy requires, retry `next_retry_at` advances, **incomplete leads never `enrichment_status=complete`**.

### Dimension 2 — Security

No secrets in logs; API keys only from Settings; parameterized DB access.

### Dimension 3 — Performance

Batch processing respects `batch_size`; no unbounded alias/API loops in executor.

### Dimension 4 — Reliability

Waterfall exhaustion → retry queue; HALT stops mass export (enrichment run returns 0 when halted).

### Dimension 5 — Observability

Structured logs on cache hit/miss, waterfall hit/miss, HALT, retry schedule.

### Dimension 6 — Maintainability

Single mapper module; C-01 function sizes; tests per module.

### Dimension 7 — Compatibility

httpx + async SQLAlchemy patterns consistent with existing tests.

### Dimension 8 — Automated verification

Every plan task maps to `pytest` commands; contract tests in CI (`pytest -m "not slow"`).

---

*Phase: 04-enrichment*
