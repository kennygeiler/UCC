# Requirements: UCC Lead Generation Platform

**Defined:** 2026-04-06  
**Core Value:** Compliant, qualified MCA leads reach GHL without bypassing the compliance gate or breaking campaign-platform abstraction.

## v1 Requirements

### Platform, data, and CI (M1)

- [ ] **PLAT-01**: Developer can install the project with a documented editable install and run the full pytest suite locally and in CI.
- [ ] **PLAT-02**: Application settings load via pydantic-settings with fast failure when required variables are missing.
- [ ] **PLAT-03**: Async SQLAlchemy engine and session factory support all ORM modules and migrations against a single Postgres instance.
- [ ] **PLAT-04**: Alembic `upgrade head` creates and updates all persisted tables used by the pipeline, agent, and watchdog.
- [ ] **PLAT-05**: Job queue supports safe concurrent claim/complete via `SELECT FOR UPDATE SKIP LOCKED` (or equivalent documented pattern).
- [ ] **PLAT-06**: Each service exposes a health endpoint suitable for Railway checks; unhealthy state is observable.
- [ ] **PLAT-07**: Structured JSON logging includes required fields (`component`, `status`, `error_type`, `context`) on meaningful state changes.
- [ ] **PLAT-08**: Sentry is initialized in pipeline, agent, and watchdog entrypoints so test exceptions are capturable per environment.

### Scraper engine (M2)

- [x] **SCRAPE-01**: Tiered scraper framework supports httpx and Playwright paths with per-state registration and rate limits (delay, jitter, backoff).
- [x] **SCRAPE-02**: Tier 1 state scrapers ingest UCC filings into `ucc_filings` with scraper run audit rows.
- [x] **SCRAPE-03**: Tier 2 and Tier 3 coverage meets master-plan breadth targets with tests/smokes as specified.
- [x] **SCRAPE-04**: APScheduler (or equivalent) runs scrape jobs on tier-appropriate cadence.
- [x] **SCRAPE-05**: HTML parsing layer normalizes SOS responses without exceeding maintainability limits (C-01).
- [x] **SCRAPE-06**: Smoke tests exist per state scraper on the scheduled profile (not necessarily on every PR).

### MCA detection and scoring (M3)

- [x] **MCA-01**: MCA detector matches aliases (including fuzzy/shell patterns) against `mca_aliases` and filing text.
- [x] **MCA-02**: Scoring incorporates position count, recency, and collateral signals with hot/warm/cold tiers.
- [x] **MCA-03**: Pipeline writes scored leads with canonical debtor identity fields for downstream dedup (C-10).
- [x] **MCA-04**: Nightly alias updater job runs safely and improves detection coverage over time.
- [x] **MCA-05**: Unit tests cover matcher and scorer edge cases from master-plan acceptance language.

### Enrichment (M4)

- [x] **ENRICH-01**: Waterfall executor runs ordered enrichment strategies with clear pass/fail semantics shared pattern (ADR-008).
- [x] **ENRICH-02**: Enrichment cache is persistent in Postgres with no TTL (C-08).
- [x] **ENRICH-03**: Per-source circuit breaker opens on threshold failure; HALT blocks export processing until recovery (C-03).
- [x] **ENRICH-04**: Retry queue schedules failed enrichments with documented backoff.
- [x] **ENRICH-05**: Contract tests validate external source response shapes used in production paths.
- [x] **ENRICH-06**: Partial enrichment never marks a lead complete erroneously.

### Compliance gate (M5)

- [ ] **COMPLY-01**: Gate runs four layers in order; any failure permanently blocks export (C-02).
- [ ] **COMPLY-02**: Internal DNC is checked before paid compliance API usage; entries are append-only with audited reversal only (C-12).
- [ ] **COMPLY-03**: DataMerch client runs with documented fallback when API key absent (C-15) with warning visibility.
- [ ] **COMPLY-04**: DNC.com/CCC and Blacklist Alliance layers execute and log pass/fail to `compliance_checks`.
- [ ] **COMPLY-05**: Static analysis / tests demonstrate no bypass path from export to skipping the gate.
- [ ] **COMPLY-06**: Negative tests cover known DNC and litigator scenarios per M10 language.
- [ ] **COMPLY-07**: Compliance logging supports audit review without exposing secrets.

### Dedup, export, GHL (M6)

- [ ] **EXPORT-01**: Deduplication performs exact and fuzzy cross-state matching (C-10).
- [ ] **EXPORT-02**: `CampaignPlatformAdapter` is the only surface pipeline business logic uses for campaign IO (C-06).
- [ ] **EXPORT-03**: GHL adapter upserts contacts, maps tiers to workflows, and validates eight custom fields at startup (C-13).
- [ ] **EXPORT-04**: CSV fallback export works when GHL API is unavailable.
- [ ] **EXPORT-05**: Webhook receiver verifies signatures and records disposition for recycling.
- [ ] **EXPORT-06**: Recycler re-queues eligible leads per cooldown rules.
- [ ] **EXPORT-07**: Integration tests cover happy-path export and dedup conflicts.
- [ ] **EXPORT-08**: No module outside adapter family imports GHL-specific SDK types in pipeline packages.

### Manager dashboard (M7)

- [ ] **DASH-01**: Manager can view pipeline health, lead funnel counts, compliance rates, and scraper status without developer jargon (C-11).
- [ ] **DASH-02**: HTMX (or documented equivalent) refreshes key sections on an interval without full reloads.
- [ ] **DASH-03**: Charts render from live aggregates within performance targets under representative data.
- [ ] **DASH-04**: CSV upload path supports manual tier assignment per compliance with master plan.
- [ ] **DASH-05**: Access is gated by configured basic auth or private networking—documented and test-covered.
- [ ] **DASH-06**: Dashboard route tests cover auth and primary read queries.

### Self-healing agent (M8)

- [ ] **AGENT-01**: LangGraph (or pinned graph library) executes detect → diagnose → repair → verify → alert cycle with Postgres checkpointing.
- [ ] **AGENT-02**: Detector ingests scraper runs, pipeline events, logs, and Sentry signals to rank anomalies.
- [ ] **AGENT-03**: Repair path integrates with GitHub (branch, CI) without violating branch protection expectations (C-16).
- [ ] **AGENT-04**: Alerter emails manager via SendGrid with rate limits per failure fingerprint.
- [ ] **AGENT-05**: Issues are deduplicated and labeled with priority derived from `state_priority`.
- [ ] **AGENT-06**: Heartbeat persists every 60 seconds to `agent_heartbeat`.
- [ ] **AGENT-07**: Agent never mutates compliance gate logic or bypass exports.
- [ ] **AGENT-08**: Tests cover graph nodes and transitions independently.

### Heartbeat watchdog (M9)

- [ ] **WATCH-01**: Watchdog monitors `agent_heartbeat` stale state within documented SLA.
- [ ] **WATCH-02**: Alerts send via SendGrid without importing `app` or `agent` packages (C-07).
- [ ] **WATCH-03**: Lead flow stall detection alerts when pipeline stops ingesting expected volume.
- [ ] **WATCH-04**: Alert deduplication prevents email storms per failure class.
- [ ] **WATCH-05**: Watchdog health endpoint reports monitoring loop status.
- [ ] **WATCH-06**: Tests cover staleness and alert gating logic without live email.

### Integration and production readiness (M10)

- [ ] **E2E-01**: End-to-end test exercises synthetic filing → compliance → export → GHL enrollment (or mocked GHL) in one flow.
- [ ] **E2E-02**: Circuit breaker integration test proves HALT/resume semantics with fault injection.
- [ ] **E2E-03**: Agent integration test proves detection + GitHub issue path for controlled failure injection.
- [ ] **E2E-04**: Watchdog integration test proves stale heartbeat detection and alert trigger (mocked mail).
- [ ] **E2E-05**: Constraint audit documents evidence for C-01–C-17.
- [ ] **E2E-06**: Railway deployment checklist complete—all services green with production env vars.
- [ ] **E2E-07**: Module audit confirms function size/docstring/test pairing targets (C-01).
- [ ] **E2E-08**: Smoke schedule documented (daily scrapers) and wired in CI/automation as specified.

## v2 Requirements

Deferred enhancements (not in current v1 roadmap):

- **Full Tier 4 production support** — blocked at MVP per master plan.
- **Additional broker fallbacks beyond documented DataMerch path** — evaluate after compliance baseline is stable.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Non-Python primary implementation | C-14 |
| Export pathways that skip compliance | C-02 |
| Mutable internal DNC without audit | C-12 |
| Separate OLTP databases per service | C-05 |
| Client-side SPA build systems for dashboard | C-14 / C-11 simplicity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAT-01 | 1 | Pending |
| PLAT-02 | 1 | Pending |
| PLAT-03 | 1 | Pending |
| PLAT-04 | 1 | Pending |
| PLAT-05 | 1 | Pending |
| PLAT-06 | 1 | Pending |
| PLAT-07 | 1 | Pending |
| PLAT-08 | 1 | Pending |
| SCRAPE-01 | 2 | Pending |
| SCRAPE-02 | 2 | Pending |
| SCRAPE-03 | 2 | Pending |
| SCRAPE-04 | 2 | Pending |
| SCRAPE-05 | 2 | Pending |
| SCRAPE-06 | 2 | Pending |
| MCA-01 | 3 | Complete |
| MCA-02 | 3 | Complete |
| MCA-03 | 3 | Complete |
| MCA-04 | 3 | Complete |
| MCA-05 | 3 | Complete |
| ENRICH-01 | 4 | Complete |
| ENRICH-02 | 4 | Complete |
| ENRICH-03 | 4 | Complete |
| ENRICH-04 | 4 | Complete |
| ENRICH-05 | 4 | Complete |
| ENRICH-06 | 4 | Complete |
| COMPLY-01 | 5 | Pending |
| COMPLY-02 | 5 | Pending |
| COMPLY-03 | 5 | Pending |
| COMPLY-04 | 5 | Pending |
| COMPLY-05 | 5 | Pending |
| COMPLY-06 | 5 | Pending |
| COMPLY-07 | 5 | Pending |
| EXPORT-01 | 6 | Pending |
| EXPORT-02 | 6 | Pending |
| EXPORT-03 | 6 | Pending |
| EXPORT-04 | 6 | Pending |
| EXPORT-05 | 6 | Pending |
| EXPORT-06 | 6 | Pending |
| EXPORT-07 | 6 | Pending |
| EXPORT-08 | 6 | Pending |
| DASH-01 | 7 | Pending |
| DASH-02 | 7 | Pending |
| DASH-03 | 7 | Pending |
| DASH-04 | 7 | Pending |
| DASH-05 | 7 | Pending |
| DASH-06 | 7 | Pending |
| AGENT-01 | 8 | Pending |
| AGENT-02 | 8 | Pending |
| AGENT-03 | 8 | Pending |
| AGENT-04 | 8 | Pending |
| AGENT-05 | 8 | Pending |
| AGENT-06 | 8 | Pending |
| AGENT-07 | 8 | Pending |
| AGENT-08 | 8 | Pending |
| WATCH-01 | 9 | Pending |
| WATCH-02 | 9 | Pending |
| WATCH-03 | 9 | Pending |
| WATCH-04 | 9 | Pending |
| WATCH-05 | 9 | Pending |
| WATCH-06 | 9 | Pending |
| E2E-01 | 10 | Pending |
| E2E-02 | 10 | Pending |
| E2E-03 | 10 | Pending |
| E2E-04 | 10 | Pending |
| E2E-05 | 10 | Pending |
| E2E-06 | 10 | Pending |
| E2E-07 | 10 | Pending |
| E2E-08 | 10 | Pending |

**Coverage:**

- v1 requirements: 68 total  
- Mapped to phases: 68  
- Unmapped: 0  

---
*Requirements defined: 2026-04-06*  
*Last updated: 2026-04-06 — ENRICH-01..06 marked complete (Phase 4)*
