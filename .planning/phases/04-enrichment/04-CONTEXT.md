# Phase 4: Enrichment — Context

**Gathered:** 2026-04-06  
**Status:** Ready for planning  
**Source:** Roadmap + `.planning/REQUIREMENTS.md` + `.kiln/docs/arch-constraints.md` + existing `app/enrichment/` (no separate discuss-phase; decisions locked from authoritative constraints).

## Phase boundary

Deliver a **production-credible enrichment path**: ordered waterfall (ADR-008), **permanent** Postgres cache (C-08), **circuit breaker + HALT** when sources fail beyond threshold (C-03), **retry queue** with documented backoff, **contract tests** on external response shapes, and **no false “complete”** enrichment when required fields are missing (ENRICH-06).

Out of scope for this phase: compliance gate layers (M5), export/GHL (M6), dashboard UI (M7).

## Implementation decisions

### Locked (from architecture / constraints)

- **Waterfall executor** is the shared primitive (`app/enrichment/waterfall.py`); enrichment, compliance, and scraper fallback must stay aligned with ADR-008 semantics (try ordered strategies, first success wins, explicit failure when exhausted).
- **Cache** is Postgres-backed `enrichment_cache`, **no TTL**, no deletes (C-08; see `.kiln/docs/pitfalls.md`).
- **HALT** on enrichment failure pattern: per arch-constraints, **>20% errors in a 5-minute window** per source trips protection; pipeline must not keep exporting; `pipeline_events` records HALT (align implementation with existing `check_pipeline_halt` / `PipelineEvent`).
- **Retry backoff** schedule from constraints: **1h, 4h, 24h, 72h** (exponential-style progression), rows in `enrichment_retry_queue`.
- **Settings** for API keys and behavior live in `app.config.Settings` (pydantic-settings), not raw `os.environ` in business logic.
- **Structured logging** with required fields on state changes (`component`, `status`, `error_type`, `context`).

### Claude’s discretion (planning resolves)

- Exact **rolling error-rate** implementation vs pybreaker defaults: either implement a **5-minute sliding window** + 20% threshold per source, or document why pybreaker’s fail_max/reset_timeout approximates policy and add tests that prove HALT fires at the documented threshold.
- **Normalized enrichment record**: internal dict shape (`phone`, `email`, `owner_name`, `estimated_revenue`, etc.) mapping from heterogeneous API JSON — plans should fix one canonical mapper module to avoid duplicate parsing.
- **Contract tests**: prefer **recorded fixtures** (JSON files in `tests/contract/` or `tests/fixtures/enrichment/`) + schema assertions, not live API calls in CI.

## Canonical references

Downstream agents MUST read these before implementing:

- `.kiln/docs/arch-constraints.md` — C-03, C-08 enrichment language  
- `.kiln/docs/decisions.md` — ADR-008 waterfall  
- `.kiln/docs/pitfalls.md` — enrichment cache and partial enrichment hazards  
- `AGENTS.md` — import and logging conventions  
- `.planning/codebase/INTEGRATIONS.md` — enrichment cache pointer  

## Deferred

- SOS officer scraping as a first-class waterfall step (may remain stubbed if not yet registered in `build_enrichment_waterfall`).

---

*Phase: 04-enrichment*
