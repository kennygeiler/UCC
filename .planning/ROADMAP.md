# Roadmap: UCC Lead Generation Platform

## Overview

v1 delivery follows the Kiln master-plan dependency chain: platform and data foundation, then ingestion (scraper → MCA → enrichment → compliance → export), manager visibility (dashboard), operational resilience (self-healing agent, independent watchdog), and capstone integration plus production readiness. Each phase maps one requirement cluster (PLAT → E2E) so every REQ-ID traces to a single phase.

## Phases

**Phase Numbering:** Integer phases 1–10 match requirement clusters M1–M10. Decimal phases (e.g. 3.1) are reserved for `/gsd-insert-phase` urgent work.

- [x] **Phase 1: Platform, data & CI** - Installable package, settings, async Postgres, migrations, job queue, health, logging, Sentry across services (completed 2026-04-06)
- [ ] **Phase 2: Scraper engine** - Tiered httpx/Playwright scrapers, tiers 1–3 coverage, scheduler, parsing, per-state smokes
- [ ] **Phase 3: MCA detection & scoring** - Alias matching, hot/warm/cold scoring, canonical debtor fields, nightly alias job, tests
- [ ] **Phase 4: Enrichment** - Waterfall executor, persistent cache, circuit breaker HALT, retry queue, contracts, partial-fail correctness
- [ ] **Phase 5: Compliance gate** - Four-layer gate, internal DNC, DataMerch fallback, external layers, no bypass, negative tests, audit-safe logs
- [ ] **Phase 6: Dedup, export & GHL** - Cross-state dedup, adapter-only campaign IO, GHL upsert + fields, CSV fallback, webhook, recycler, tests, no stray GHL imports
- [ ] **Phase 7: Manager dashboard** - Plain-language ops view, HTMX refresh, charts, CSV upload tier path, gated access, route tests
- [ ] **Phase 8: Self-healing agent** - LangGraph cycle with checkpointing, anomaly detection, GitHub repair path, email alerts, heartbeat, guardrails, node tests
- [ ] **Phase 9: Heartbeat watchdog** - Stale agent heartbeat detection, SendGrid alerts without app/agent imports, stall detection, deduped alerts, health endpoint, tests
- [ ] **Phase 10: Integration & production readiness** - E2E and integration tests, constraint audit, Railway checklist, C-01 module audit, smoke schedule automation

## Phase Details

### Phase 1: Platform, data & CI
**Goal**: Operators and developers share a single reliable baseline—install, configuration, database, job claiming, health checks, and cross-service observability.
**Depends on**: Nothing (first phase)
**Requirements**: PLAT-01, PLAT-02, PLAT-03, PLAT-04, PLAT-05, PLAT-06, PLAT-07, PLAT-08
**Success Criteria** (what must be TRUE):
  1. A developer can follow documented editable install and run the full pytest suite locally; CI runs the same suite successfully.
  2. Starting pipeline, agent, or watchdog with missing required settings fails immediately with clear validation errors (no silent defaults for secrets).
  3. Against one Postgres instance, `alembic upgrade head` creates or migrates every table the three services use; async sessions support all ORM modules; concurrent workers claim/complete jobs without duplicate processing (tests or equivalent documented pattern).
  4. Each service exposes a health endpoint suitable for Railway; unhealthy states are distinguishable from healthy in responses or documented status fields.
  5. Meaningful state transitions emit structured JSON logs with `component`, `status`, `error_type`, and `context`; Sentry is initialized on all three entrypoints so exceptions are attributable per service and environment.
**Plans:** 0/3 plans complete
Plans:
- [ ] `01-PLAN.md` — README + AGENTS pointer; CI Postgres; **[BLOCKING]** `alembic upgrade head` before pytest (PLAT-01, PLAT-03, PLAT-04)
- [ ] `02-PLAN.md` — Integration tests: DB session smoke, job queue concurrency; app/agent structured log field tests (PLAT-03, PLAT-05, PLAT-07)
- [ ] `03-PLAN.md` — Watchdog structlog (C-07); health JSON enrichment; Settings-backed Sentry for app/agent + tests for all three entrypoints (PLAT-02, PLAT-06, PLAT-07, PLAT-08)

### Phase 2: Scraper engine
**Goal**: Public UCC data is ingested on a tiered, rate-respecting schedule with auditable runs and maintainable parsing.
**Depends on**: Phase 1
**Requirements**: SCRAPE-01, SCRAPE-02, SCRAPE-03, SCRAPE-04, SCRAPE-05, SCRAPE-06
**Success Criteria** (what must be TRUE):
  1. A tier-appropriate state scraper runs via the registered framework (httpx and/or Playwright) with per-state rate limits (delay, jitter, backoff).
  2. Tier 1 scrapers persist filings into `ucc_filings` and write scraper run audit rows traceable to each run.
  3. Tier 2 and Tier 3 coverage meets master-plan breadth targets, evidenced by tests and/or smokes as specified there.
  4. Scheduled scrape jobs execute on tier-appropriate cadence (observable via scheduler integration or operational logs).
  5. Parsing normalizes SOS HTML within C-01 maintainability limits; each state scraper has a documented smoke on the scheduled profile (not necessarily every PR).
**Plans**: TBD

### Phase 3: MCA detection & scoring
**Goal**: Filings are reliably classified and scored into MCA signal tiers with identities ready for deduplication.
**Depends on**: Phase 2
**Requirements**: MCA-01, MCA-02, MCA-03, MCA-04, MCA-05
**Success Criteria** (what must be TRUE):
  1. The MCA detector matches configured aliases (including fuzzy/shell patterns) against `mca_aliases` and filing text with deterministic, test-covered behavior.
  2. Lead scores reflect position count, recency, and collateral signals and assign hot/warm/cold tiers observable on stored lead records.
  3. Pipeline persists scored leads with canonical debtor identity fields suitable for cross-state dedup (C-10).
  4. A nightly alias updater job runs safely (no destructive surprises) and can be verified to broaden or refresh alias coverage over time.
  5. Unit tests cover matcher and scorer edge cases described in master-plan acceptance language.
**Plans**: TBD

### Phase 4: Enrichment
**Goal**: Leads gain external attributes through an ordered, resilient enrichment path with halt semantics that protect downstream export.
**Depends on**: Phase 3
**Requirements**: ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04, ENRICH-05, ENRICH-06
**Success Criteria** (what must be TRUE):
  1. Enrichment runs through a waterfall executor with explicit pass/fail semantics shared with other ADR-008-style patterns in the codebase.
  2. Enrichment results are cached in Postgres with no TTL; repeated lookups behave per C-08.
  3. When per-source failure rates exceed the threshold, the circuit breaker opens and HALT blocks export until recovery is observable (C-03).
  4. Failed enrichments enter a retry queue with documented backoff and verifiable scheduling behavior.
  5. Contract tests lock production-path response shapes; partial enrichment never marks a lead export-complete when requirements are unmet (tests prove it).
**Plans**: TBD

### Phase 5: Compliance gate
**Goal**: No compliant export occurs unless all four compliance layers pass; DNC and fallback behaviors match legal and architectural constraints.
**Depends on**: Phase 4
**Requirements**: COMPLY-01, COMPLY-02, COMPLY-03, COMPLY-04, COMPLY-05, COMPLY-06, COMPLY-07
**Success Criteria** (what must be TRUE):
  1. The gate executes four layers in order; any failure permanently blocks export for that lead (C-02), verifiable in integration or E2E flows.
  2. Internal DNC is checked before paid compliance APIs; entries are append-only with manager-audited reversal only (C-12).
  3. DataMerch runs with documented fallback when the API key is absent; operators see warnings, not silent pass (C-15).
  4. DNC.com/CCC and Blacklist Alliance layers persist pass/fail to `compliance_checks` with structured logs suitable for audit without exposing secrets.
  5. Static analysis and/or tests prove no export path skips the gate; negative tests cover known DNC and litigator scenarios per M10 language.
**Plans**: TBD

### Phase 6: Dedup, export & GHL
**Goal**: Compliant leads deduplicate across states and reach GoHighLevel (or CSV fallback) only through the adapter abstraction, with recycling and verified integrations.
**Depends on**: Phase 5
**Requirements**: EXPORT-01, EXPORT-02, EXPORT-03, EXPORT-04, EXPORT-05, EXPORT-06, EXPORT-07, EXPORT-08
**Success Criteria** (what must be TRUE):
  1. Deduplication performs exact and fuzzy cross-state matching with test evidence (C-10).
  2. Pipeline business logic uses only `CampaignPlatformAdapter` for campaign IO; no GHL SDK types leak outside the adapter family (C-06, C-13, EXPORT-08 verifiable).
  3. GHL adapter upserts contacts, maps tiers to workflows, validates eight custom fields at startup, and misconfiguration fails fast; CSV fallback produces a usable export when the GHL API is unavailable.
  4. Webhook receiver verifies signatures and records disposition; recycler re-queues eligible leads per documented cooldown rules (tests or integration).
  5. Integration tests cover happy-path export and dedup conflict resolution.
**Plans**: TBD

### Phase 7: Manager dashboard
**Goal**: A non-technical manager can see pipeline health, funnel, compliance, and scraper status—and perform allowed manual actions—without a SPA build.
**Depends on**: Phase 6
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06
**Success Criteria** (what must be TRUE):
  1. A manager can open the dashboard and read pipeline health, funnel counts, compliance rates, and scraper status in plain language (C-11).
  2. Key sections refresh on an interval via HTMX (or documented equivalent) without full page reloads.
  3. Charts render from live aggregates within performance targets under representative data (tests or benchmarks).
  4. CSV upload supports manual tier assignment per master plan with clear success/failure feedback.
  5. Access is gated by configured basic auth or private networking (documented); route tests cover auth boundaries and primary read queries.
**Plans**: TBD
**UI hint**: yes

### Phase 8: Self-healing agent
**Goal**: An autonomous agent detects operational anomalies, attempts safe repairs, verifies outcomes, and alerts the manager—without weakening compliance or export rules.
**Depends on**: Phase 7
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, AGENT-07, AGENT-08
**Success Criteria** (what must be TRUE):
  1. A pinned graph library runs detect → diagnose → repair → verify → alert with Postgres checkpointing across restarts.
  2. The detector ranks anomalies from scraper runs, pipeline events, logs, and Sentry signals (observable in tests or fixtures).
  3. Repair integrates with GitHub (branch/PR/CI) respecting branch-protection expectations (C-16), proven in a controlled integration test.
  4. SendGrid alerts use per-fingerprint rate limits; issues dedupe and carry priority from `state_priority`; heartbeat rows write to `agent_heartbeat` at least every 60s while the loop runs.
  5. Tests cover graph nodes and transitions independently and prove the agent cannot mutate compliance logic or bypass export rules (AGENT-07).
**Plans**: TBD

### Phase 9: Heartbeat watchdog
**Goal**: An independent service proves the agent and pipeline are alive and alerts on stalls—without coupling to pipeline or agent packages.
**Depends on**: Phase 8
**Requirements**: WATCH-01, WATCH-02, WATCH-03, WATCH-04, WATCH-05, WATCH-06
**Success Criteria** (what must be TRUE):
  1. Watchdog detects stale `agent_heartbeat` within the documented SLA and alerts via SendGrid without importing `app` or `agent` (C-07), verifiable by import/packaging rules.
  2. Lead-flow stall detection fires when ingestion drops below expected volume; thresholds are documented and test-covered.
  3. Alert deduplication prevents email storms per failure class (tests with mocks).
  4. Health endpoint reports monitoring loop status suitable for Railway; tests cover staleness and alert gating without live email.
**Plans**: TBD

### Phase 10: Integration & production readiness
**Goal**: The full system is provably coherent under failure injection, constraint-complete, and deployable to Railway with operational smoke automation.
**Depends on**: Phase 9
**Requirements**: E2E-01, E2E-02, E2E-03, E2E-04, E2E-05, E2E-06, E2E-07, E2E-08
**Success Criteria** (what must be TRUE):
  1. E2E test runs synthetic filing → compliance → export → GHL (or mocked GHL) in one flow; separate integration tests prove circuit-breaker HALT/resume, agent detection → GitHub path, and watchdog stale heartbeat → alert (mocked mail).
  2. Constraint audit documents evidence for C-01–C-17 mapped to tests, config, or code.
  3. Railway checklist complete: three services green with documented production env vars.
  4. Module audit satisfies C-01 targets on representative modules; daily scraper smoke schedule is documented and wired in CI/automation as specified.
**Plans**: TBD

## Progress

**Execution Order:** Phases 1 → 10 in numeric order; decimal insert phases (if any) run between their surrounding integers.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Platform, data & CI | 0/3 | Complete    | 2026-04-06 |
| 2. Scraper engine | 0/TBD | Not started | - |
| 3. MCA detection & scoring | 0/TBD | Not started | - |
| 4. Enrichment | 0/TBD | Not started | - |
| 5. Compliance gate | 0/TBD | Not started | - |
| 6. Dedup, export & GHL | 0/TBD | Not started | - |
| 7. Manager dashboard | 0/TBD | Not started | - |
| 8. Self-healing agent | 0/TBD | Not started | - |
| 9. Heartbeat watchdog | 0/TBD | Not started | - |
| 10. Integration & production readiness | 0/TBD | Not started | - |

---
*Roadmap created: 2026-04-06 — phases aligned to PLAT…E2E clusters (10 phases, 68 requirements, 1:1 REQ mapping).*
