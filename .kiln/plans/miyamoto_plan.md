# miyamoto_plan.md
# Architecture-Level Build Plan: UCC Lead Generation Platform
# Author: miyamoto (independent planner, Architecture stage)
# Date: 2026-03-24

---

## Overview

This plan organizes the build of the UCC Lead Generation Platform into seven milestones. Each milestone represents a coherent, independently verifiable architecture slice. Milestones are ordered to respect data-flow dependencies: the pipeline must exist before autonomous healing can monitor it, and the watchdog must be independent of both. CI/CD infrastructure is established first so every subsequent milestone inherits it.

The plan fully addresses:
- All 7 pipeline stages (Scrape, Detect, Score, Enrich, Comply, Dedup, Export)
- Manager Dashboard
- Self-Healing Agent (Service 2)
- Heartbeat Watchdog (Service 3)
- CI/CD and Railway deployment
- All 17 hard constraints (C-01 through C-17)

---

## Milestone 1: Foundation — Repository, Database, and CI/CD

**Goal:** Establish the shared infrastructure skeleton all other milestones depend on. Nothing is business-logic; everything is load-bearing scaffolding. No milestone can ship without this foundation in place.

### Scope Summary

Stand up the GitHub repository, Railway project with three service slots, and Postgres instance. Define the full database schema via Alembic migrations. Configure GitHub Actions for continuous integration. Establish the pydantic-settings configuration contract and structlog JSON logging baseline. Define the Procfile and railway.toml so all three services can be deployed (even as empty health-check stubs).

### Deliverables

- [ ] GitHub repository initialized with `pyproject.toml` (Python 3.12+, all declared dependencies)
- [ ] `app/config.py` — pydantic-settings model covering all environment variables listed in architecture doc; validation fails fast on missing required vars
- [ ] `app/db.py` — SQLAlchemy 2.0 async engine + session factory wired to `DATABASE_URL`
- [ ] Alembic migration set: all core tables created (`ucc_filings`, `leads`, `mca_aliases`, `dnc`, `job_queue`, `enrichment_retry_queue`, `enrichment_cache`, `compliance_checks`, `state_priority`, `scraper_runs`, `agent_heartbeat`, `pipeline_events`, `langgraph_checkpoints`)
- [ ] `Procfile` with three service entries: `pipeline`, `agent`, `watchdog`
- [ ] `railway.toml` with restart policies (`on-failure`/`on-failure`/`always`) and `RAILWAY_HEALTHCHECK_PATH=/health` for each service
- [ ] Stub `GET /health` endpoints in `app/main.py`, `agent/main.py`, `watchdog/main.py` (returns `{"status": "ok"}`)
- [ ] GitHub Actions workflow: runs `pytest` (unit + integration) on every push and PR to main
- [ ] structlog configured for JSON output with required fields (`component`, `status`, `error_type`, `context`) — shared across all three services
- [ ] Sentry SDK initialized in all three service entry points via `SENTRY_DSN`
- [ ] `.env.example` listing all required environment variables (no secrets)

### Dependencies

None. This is the root milestone.

### Acceptance Criteria

- Railway reports all three services healthy (green) on `/health`
- `alembic upgrade head` runs clean against a fresh Postgres instance
- GitHub Actions pipeline passes on an empty test suite (green, not skipped)
- A log entry written by any service appears in Railway log viewer as valid JSON with all required fields
- `python -c "from app.config import settings"` raises `ValidationError` when a required env var is absent

### Constraint Adherence

- C-04 (Railway-only): Procfile + railway.toml confirm Railway deployment
- C-05 (Single Postgres): All tables in one migration set, one `DATABASE_URL`
- C-14 (Python only): No Node.js, no npm, no build toolchain
- C-16 (GitHub source of truth): GitHub Actions CI established from day one
- C-01 (AI maintainability): Short modules, docstrings, structlog on all state changes

### Status: PENDING

---

## Milestone 2: Scraper Engine — Per-State UCC Filing Ingestion

**Goal:** Deliver a working, tiered scraping system that ingests UCC filing records from Secretary of State websites across all states, enforces per-state rate limits, and writes raw filings to `ucc_filings`.

### Scope Summary

Implement the abstract base scraper, state registry, and per-tier rate-limiting strategy. Build scraper implementations for Tier 1 states first (top 10 MCA states: NY, CA, TX, FL, NJ, GA, IL, PA, OH, MD), then Tier 2, then Tier 3. Playwright headless browser support is included for JS-rendered portals (~10% of states). APScheduler is configured with per-state cron jobs. Every scraper has a corresponding smoke test. Session/cookie management handles stateful portals.

### Deliverables

- [ ] `app/scrapers/base.py` — abstract base scraper class defining the scraper contract
- [ ] `app/scrapers/registry.py` — maps state codes to scraper classes and tier assignments
- [ ] `app/scrapers/rate_limiter.py` — per-state rate limiter enforcing C-09 defaults (1 req/3s standard, 1 req/10s Tier 3) with jitter and exponential backoff
- [ ] `app/scrapers/session_manager.py` — cookie/ViewState session persistence per state
- [ ] Per-state scraper modules: Tier 1 (10 states), Tier 2 (~24 states), Tier 3 (~6 states); Tier 4 (DC, NYC) stubbed but skipped
- [ ] `app/scheduler/jobs.py` — APScheduler job definitions: daily Tier 1, daily-to-48h Tier 2, 48h+ Tier 3
- [ ] `app/models/filing.py` — `ucc_filings` ORM model
- [ ] `app/models/operations.py` — `scraper_runs` ORM model; every scraper run writes a row (state, started_at, finished_at, records_found, status, error_detail)
- [ ] Smoke tests in `tests/smoke/` — one per state scraper, scheduled daily (not on push)
- [ ] User-Agent rotation list used by all HTTP scrapers

### Dependencies

- Milestone 1 (database schema, Railway services, APScheduler wiring)

### Acceptance Criteria

- Tier 1 scrapers run end-to-end against live SOS portals and write rows to `ucc_filings`
- Per-state rate limiter is enforced; no scraper fires faster than its configured limit
- `scraper_runs` records a row for every execution with accurate status
- Playwright-dependent scrapers run without error in the Railway Python environment
- Smoke tests for all Tier 1 states pass on schedule
- No scraper module exceeds 50 lines per function (C-01)

### Constraint Adherence

- C-09 (Per-state rate limiting): Rate limiter enforces all tiers
- C-17 (Tiered scraping strategy): Registry enforces Tier 1/2/3/4 distinction
- C-01 (AI maintainability): One file per state, smoke test per state, short functions
- C-04 (Railway-only): Playwright runs in the Railway Python service via Nixpacks

### Status: PENDING

---

## Milestone 3: MCA Detection and Lead Scoring

**Goal:** Identify which raw UCC filings represent MCA (Merchant Cash Advance) debt, apply the lead scoring model, and write qualified, scored leads to the `leads` table ready for enrichment.

### Scope Summary

Implement the MCA alias matching engine against the `mca_aliases` table. Build the self-improving alias updater that analyzes filing patterns to detect emerging shell companies. Implement the lead scorer using position count, filing recency, and collateral type as signals. The output of this milestone is a scored `leads` row for every filing that passes detection.

### Deliverables

- [ ] `app/detection/mca_detector.py` — alias matching against `mca_aliases`; returns match confidence and canonical lender name
- [ ] `app/detection/alias_updater.py` — nightly job that analyzes filing patterns and proposes new aliases; runs as an APScheduler job
- [ ] `app/models/mca_alias.py` — `mca_aliases` ORM model
- [ ] `mca_aliases` seed data: initial list of known MCA lenders and shell companies
- [ ] `app/scoring/scorer.py` — scoring logic: position count (primary signal), recency decay, collateral type weighting; outputs integer `lead_score`
- [ ] `app/models/lead.py` — `leads` ORM model with all fields from architecture doc
- [ ] Pipeline wiring: Scraper output -> Detector -> Scorer -> `leads` row written (status: `scored`)
- [ ] Unit tests covering alias matching, alias updater, and scoring logic in `tests/unit/`

### Dependencies

- Milestone 1 (database schema, ORM models)
- Milestone 2 (scraper output in `ucc_filings`)

### Acceptance Criteria

- Known MCA lender names in test fixtures are detected with match confidence
- Lead scorer assigns higher scores to filings with more secured-party positions
- `leads` table receives a row for each MCA-detected filing with `enrichment_status: pending`
- Alias updater job runs nightly without error
- Unit test coverage for scorer and detector

### Constraint Adherence

- C-10 (Cross-state deduplication): Dedup milestone builds on this data; scoring milestone must write canonical debtor name to support fuzzy matching
- C-01 (AI maintainability): Scorer and detector are single-purpose functions with docstrings

### Status: PENDING

---

## Milestone 4: Enrichment Pipeline

**Goal:** Enrich scored leads with phone, email, revenue, and owner name using a waterfall of external API sources. All enrichment results are permanently cached. Circuit breakers protect against cascading API failures. Partially enriched leads never enter the export queue.

### Scope Summary

Implement the generic waterfall executor (ADR-008). Implement all six enrichment source connectors (PDL, Apollo, OpenCorporates, Whitepages, Twilio Lookup, SOS officer scraping). Wrap each source in a pybreaker circuit breaker. Implement the permanent enrichment cache backed by `enrichment_cache`. Implement the `enrichment_retry_queue` with exponential backoff. Pipeline HALT logic fires when any circuit breaker opens.

### Deliverables

- [ ] `app/enrichment/waterfall.py` — generic waterfall executor: accepts ordered strategy list, returns first success, logs each attempt; shared by enrichment, compliance, and scraping subsystems
- [ ] `app/enrichment/sources/pdl.py` — People Data Labs connector (primary phone, owner name)
- [ ] `app/enrichment/sources/apollo.py` — Apollo.io connector (primary email, revenue)
- [ ] `app/enrichment/sources/opencorporates.py` — OpenCorporates connector (secondary owner name)
- [ ] `app/enrichment/sources/whitepages.py` — Whitepages Pro connector (secondary phone)
- [ ] `app/enrichment/sources/twilio_lookup.py` — Twilio Lookup connector (phone validation, line-type)
- [ ] `app/enrichment/sources/sos_officer.py` — SOS officer name scraping (first-try owner name, free)
- [ ] `app/enrichment/circuit_breaker.py` — pybreaker wrapper: >20% errors in 5-min window trips breaker; open circuit writes HALT event to `pipeline_events`
- [ ] `app/enrichment/cache.py` — Postgres-backed enrichment cache: read before API call, write after success (permanent, C-08)
- [ ] `app/models/job.py` — `enrichment_retry_queue` ORM model; backoff schedule: 1h, 4h, 24h, 72h
- [ ] Pipeline HALT logic: when any circuit breaker opens, pipeline suspends export queue processing and writes to `pipeline_events`
- [ ] Contract tests in `tests/contract/` validating enrichment API response schemas
- [ ] Integration tests for waterfall executor with mock sources

### Dependencies

- Milestone 1 (database, circuit breaker state in Postgres)
- Milestone 3 (scored leads available as enrichment input)

### Acceptance Criteria

- Waterfall executor tries sources in configured order and returns first non-null result
- Cache hit prevents duplicate API calls; cached result includes `fetched_at`
- Circuit breaker opens after 20%+ error rate; HALT event appears in `pipeline_events`
- `enrichment_retry_queue` receives failed records; APScheduler retries at backoff intervals
- Contract tests confirm API response shapes match connector parsing logic
- No partially enriched lead progresses past `enrichment_status: complete` (C-03)

### Constraint Adherence

- C-03 (Enrichment failure halts pipeline): Circuit breaker + HALT event + retry queue
- C-05 (Single Postgres): Enrichment cache and retry queue in Postgres
- C-08 (Indefinite retention): Enrichment cache is permanent, no TTL
- ADR-008 (Waterfall pattern): Generic executor used here and shared with compliance

### Status: PENDING

---

## Milestone 5: Compliance Gate and Deduplication

**Goal:** Enforce the 4-layer compliance gate with zero tolerance (C-02). Deduplicate leads across states and scrape cycles (C-10). Only leads that pass all four compliance layers and are confirmed unique proceed to the export queue.

### Scope Summary

Implement all four compliance layers using the shared waterfall executor, with the internal DNC check first (free, Postgres) before any paid external API call. Implement the DataMerch fallback per C-15. Implement the cross-state fuzzy deduplication engine. Every compliance check is written to `compliance_checks` as an immutable audit log. Internal DNC is write-once and irrevocable (C-12).

### Deliverables

- [ ] `app/compliance/gate.py` — 4-layer compliance gate orchestrator using waterfall executor; returns `PASS` or `BLOCK` with blocking reason
- [ ] `app/compliance/internal_dnc.py` — Internal DNC table operations: check by phone and email independently; write-once append (C-12)
- [ ] `app/compliance/datamerch.py` — DataMerch API client (Gate 2); fallback path when `DATAMERCH_API_KEY` absent: UCC pattern analysis (C-15); logs warning on every lead if DataMerch not configured
- [ ] `app/compliance/dnc_scrub.py` — DNC.com or CCC API client (Gate 3: federal + state DNC scrub)
- [ ] `app/compliance/blacklist_alliance.py` — Blacklist Alliance API client (Gate 4: TCPA litigator screen)
- [ ] `compliance_checks` table: every gate result written as an immutable audit row (gate name, result, checked_at)
- [ ] `app/models/dnc.py` — Internal DNC ORM model with audit trail
- [ ] `app/dedup/deduplicator.py` — exact match on (business_name + state + filing_number); fuzzy cross-state match; position count aggregation; GHL upsert provides additional dedup layer (C-10)
- [ ] Pipeline wiring: enriched lead -> Compliance Gate -> Deduplicator -> `export_status: queued` or `BLOCKED`
- [ ] Unit tests for each compliance layer with mock API responses
- [ ] Unit tests for deduplicator covering exact match, fuzzy match, and cross-state scenarios

### Dependencies

- Milestone 1 (database schema: `internal_dnc`, `compliance_checks`)
- Milestone 4 (enriched leads as compliance input)
- Milestone 4 waterfall executor (shared by compliance gate)

### Acceptance Criteria

- Internal DNC check runs first; no paid API call fires if a lead is on internal DNC
- DataMerch gate logs a warning and applies fallback pattern analysis when `DATAMERCH_API_KEY` is absent
- All four gate results are written to `compliance_checks` regardless of pass/fail
- A lead blocked at any gate is never written to `export_status: queued`
- Duplicate detection prevents duplicate rows in `leads` for the same business across states and cycles
- Internal DNC entries cannot be removed via any automated code path (C-12)

### Constraint Adherence

- C-02 (Compliance gate absolute): All four layers enforced, no override path
- C-10 (Cross-state dedup): Fuzzy match + position count aggregation
- C-12 (Internal DNC irrevocable): Write-once, no delete/update on DNC records
- C-15 (DataMerch fallback): Fallback path implemented and activated by missing env var

### Status: PENDING

---

## Milestone 6: Campaign Export, Webhook Receiver, and Lead Recycling

**Goal:** Export qualified leads to GoHighLevel via the CampaignPlatformAdapter interface, handle disposition feedback from GHL webhooks, and recycle eligible leads after cooldown.

### Scope Summary

Implement the abstract `CampaignPlatformAdapter` interface (C-06) and the concrete `GHLAdapter` using GHL API v2 (ADR-004). Implement the GHL webhook receiver for real-time disposition feedback. Implement the lead recycler that re-queues eligible leads after the 30-day cooldown. Implement CSV fallback export for when the GHL API is unavailable. All GHL custom fields are pre-validated against the requirement list (C-13).

### Deliverables

- [ ] `app/export/adapter.py` — abstract `CampaignPlatformAdapter` with four interface methods: `upsert_lead`, `enroll_in_campaign`, `get_disposition_updates`, `parse_webhook_payload` (C-06)
- [ ] `app/export/ghl_adapter.py` — concrete GHL API v2 implementation: two-call pattern (upsert + workflow enrollment), tiered workflow routing by `lead_score`, exponential backoff on failure
- [ ] `app/export/csv_fallback.py` — CSV export to filesystem queue; manual upload path for GHL API outages
- [ ] `app/export/webhook_handler.py` — FastAPI endpoint receiving GHL OpportunityUpdate and ContactUpdate webhooks; verifies payload via `GHL_WEBHOOK_SECRET`; writes disposition to `leads.disposition`
- [ ] `app/recycling/recycler.py` — APScheduler job: queries leads with disposition `have_debt_not_interested` past 30-day cooldown; resets `export_status: queued`
- [ ] GHL custom field validation check at service startup: verifies all 8 required custom fields exist in the GHL sub-account before pipeline runs (C-13)
- [ ] Three GHL workflow environment variables wired to tier routing: `GHL_WORKFLOW_TIER1`, `GHL_WORKFLOW_TIER2`, `GHL_WORKFLOW_TIER3`
- [ ] Integration tests for GHLAdapter with mocked GHL API responses
- [ ] Unit tests for webhook payload parsing and recycler cooldown logic

### Dependencies

- Milestone 1 (database, FastAPI app, env vars)
- Milestone 5 (export-queued leads as export input)

### Acceptance Criteria

- A lead with `export_status: queued` is upserted to GHL and enrolled in the correct tier workflow in a single pipeline pass
- GHL custom field validation fails fast at startup if any of the 8 required fields are absent
- Webhook receiver verifies signature and writes disposition; invalid signature returns 401
- CSV fallback writes a file to the queue directory when `GHL_API_KEY` is absent or API returns 5xx
- Recycler re-queues eligible leads exactly once per 30-day cooldown cycle
- Pipeline code never imports from `ghl_adapter.py` directly; all calls go through the adapter interface (C-06)

### Constraint Adherence

- C-06 (Platform-agnostic): Abstract adapter interface; no GHL-specific imports in pipeline code
- C-13 (GHL custom fields pre-created): Startup validation check
- ADR-004 (GHL API v2): Two-call upsert + enroll pattern

### Status: PENDING

---

## Milestone 7: Manager Dashboard

**Goal:** Deliver the non-technical manager dashboard that surfaces pipeline health, lead metrics, compliance stats, and scraper status — server-rendered, loading under 3 seconds, with no technical jargon.

### Scope Summary

Implement the FastAPI dashboard routes and Jinja2 + HTMX templates. Dashboard is served from the pipeline service (Service 1). All data comes from Postgres queries. HTMX is used for periodic partial-page refresh (no full-page reload). Chart.js via CDN for metrics visualization. Tailwind CSS via CDN for styling. No auth system at MVP (Railway private networking or basic auth). CSV upload for manual tier assignment.

### Deliverables

- [ ] `app/dashboard/routes.py` — dashboard HTTP routes: `/`, `/scraper-status`, `/lead-metrics`, `/compliance-stats`, `/alerts`
- [ ] `app/dashboard/templates/base.html` — Jinja2 base template with Tailwind CDN, Chart.js CDN, HTMX CDN
- [ ] `app/dashboard/templates/index.html` — main dashboard: pipeline health summary, lead counts by stage, recent alert list
- [ ] `app/dashboard/templates/scraper_status.html` — per-state scraper last-run status, records found, failure indicators
- [ ] `app/dashboard/templates/lead_metrics.html` — leads processed today/week/month, compliance pass rate, enrichment success rate
- [ ] `app/dashboard/templates/compliance_stats.html` — gate pass/fail breakdown, DNC block count, compliance audit trail excerpt
- [ ] `app/dashboard/templates/alerts.html` — recent pipeline events and email alert history
- [ ] HTMX polling on dashboard index: refreshes lead count and alert panel every 30 seconds without full page reload
- [ ] CSV upload endpoint: accepts tier assignment CSV; manager maps leads to tiers manually (no algorithmic assignment)
- [ ] Page load < 3 seconds measured from Railway environment (SC-07)
- [ ] No technical jargon in any UI label or message (C-11)

### Dependencies

- Milestone 1 (FastAPI app, database)
- Milestone 2 (scraper run data)
- Milestone 3 (lead scoring data)
- Milestone 4 (enrichment data)
- Milestone 5 (compliance data)
- Milestone 6 (export and disposition data)

### Acceptance Criteria

- All five dashboard pages render without error against a populated test database
- HTMX partial refresh updates lead count panel without page reload
- CSV upload writes tier assignments to `leads.campaign_tier` for matching records
- Dashboard page load measured under 3 seconds in Railway environment
- No page contains technical jargon; all labels describe business outcomes

### Constraint Adherence

- C-11 (Non-technical dashboard): Language review on all labels; no error codes or stack traces exposed
- C-14 (Python only, no JS build toolchain): All templates use CDN delivery; no npm
- ADR-003 (FastAPI + HTMX): No SPA; server-rendered with HTMX for dynamic updates

### Status: PENDING

---

## Milestone 8: Self-Healing Agent (Service 2)

**Goal:** Deploy the LangGraph-based self-healing agent as an independent Railway service that monitors pipeline health, diagnoses failures using structured logs, attempts autonomous repair, and sends plain-English alerts to the manager.

### Scope Summary

Implement the LangGraph agent graph with five nodes: Detector, Diagnostician, Repairer, Verifier, Alerter. Add GitHub issue automation for failures that cannot be auto-resolved. Configure priority-based repair ordering using `state_priority` table. Implement the heartbeat writer that updates `agent_heartbeat` every 60 seconds. Agent reads structured logs (JSON via structlog), smoke test results (pytest-json-report), and Sentry error events.

### Deliverables

- [ ] `agent/graph.py` — LangGraph agent graph definition: Detector -> Diagnostician -> Repairer -> Verifier -> Alerter cycle; Postgres checkpointer for state persistence across restarts (ADR-007)
- [ ] `agent/nodes/detector.py` — anomaly detection: reads `pipeline_events`, `scraper_runs`, Sentry events; surfaces anomalies by severity
- [ ] `agent/nodes/diagnostician.py` — LLM-based (Claude) analysis of structured log context around each anomaly; produces diagnosis and proposed fix
- [ ] `agent/nodes/repairer.py` — applies proposed fix to staging branch via GitHub API; triggers GitHub Actions CI run
- [ ] `agent/nodes/verifier.py` — checks GitHub Actions CI result (pytest pass/fail via PyGithub); on pass: merges to main, on fail: creates GitHub issue
- [ ] `agent/nodes/alerter.py` — SendGrid email to `MANAGER_EMAIL` in plain English; one email per unique failure type per 24h window (no alert storms)
- [ ] `agent/nodes/issue_creator.py` — PyGithub: creates issue with priority label (priority-high for Tier 1 states); checks for duplicate open issues before filing
- [ ] `agent/heartbeat.py` — writes `agent_heartbeat.last_seen = now()` every 60 seconds to Postgres
- [ ] `state_priority` table nightly recalculation: APScheduler job ranks states by `leads_last_30_days`; top 10 always Tier 1
- [ ] Self-healing agent health endpoint: `GET /health` returns `{"status": "ok", "last_heartbeat": "<timestamp>"}`
- [ ] Integration tests covering the Detector node with mock `pipeline_events` data

### Dependencies

- Milestone 1 (database, structlog, Sentry, GitHub Actions)
- Milestone 2 (scraper run data for anomaly detection)
- Milestone 4 (enrichment failure events)
- Milestone 5 (compliance events)

### Acceptance Criteria

- Agent starts, completes one full detection cycle, and writes a heartbeat within 60 seconds of startup
- Detector surfaces a simulated scraper failure from `pipeline_events` within one cycle
- LangGraph checkpointer persists agent state to `langgraph_checkpoints`; agent resumes from checkpoint after simulated restart
- GitHub issue is created with correct priority label for a Tier 1 state scraper failure
- SendGrid alert email is sent in plain English with no stack traces or technical identifiers
- No more than one email per unique failure type per 24-hour window

### Constraint Adherence

- C-01 (AI maintainability): Agent graph nodes are short functions with docstrings; LangGraph provides inspectable state
- C-07 (Three independent services): Agent deploys as separate Railway service with independent restart
- C-16 (GitHub source of truth): All repairs go through GitHub Actions CI before merging
- ADR-007 (LangGraph): Postgres checkpointer; cyclical graph

### Status: PENDING

---

## Milestone 9: Heartbeat Watchdog (Service 3)

**Goal:** Deploy the independent deadman-switch watchdog as a third Railway service with `always` restart policy. The watchdog has no dependency on Service 1 or Service 2 code or runtime state. It monitors only Postgres and sends direct email alerts.

### Scope Summary

The watchdog runs a simple loop every 5 minutes. It checks two conditions in Postgres: (1) is `agent_heartbeat.last_seen` less than 5 minutes ago, and (2) have new `leads` rows been inserted within the expected pipeline window. If either condition fails, it sends a direct SendGrid email to the manager. No dependency on pipeline service or agent service code.

### Deliverables

- [ ] `watchdog/main.py` — service entry point: starts watchdog loop, exposes `GET /health`
- [ ] `watchdog/checker.py` — two-condition check: heartbeat staleness (>5 min) and lead insertion gap (based on expected cadence); reads only Postgres, no inter-service HTTP calls
- [ ] `watchdog/alerter.py` — SendGrid direct email: bypasses self-healing agent entirely; plain English message to `MANAGER_EMAIL`
- [ ] Railway restart policy: `always` (restarts unconditionally on any exit)
- [ ] Watchdog has its own `requirements` declaration or is isolated within the monorepo; no imports from `app/` or `agent/` namespaces
- [ ] Alert deduplication: no more than one alert per failure type per 60-minute window (prevents email storms during prolonged outages)

### Dependencies

- Milestone 1 (database: `agent_heartbeat` table, `leads` table, Postgres connection)
- Milestone 8 (agent heartbeat writer must be deployed for watchdog to have data to check)

### Acceptance Criteria

- Watchdog detects a stale heartbeat (simulated by stopping the agent) within one 5-minute check cycle
- Watchdog sends a SendGrid email when heartbeat is stale; email received at `MANAGER_EMAIL`
- Watchdog sends no email when heartbeat is fresh
- No import from `app/` or `agent/` namespaces exists in `watchdog/`
- Railway shows watchdog service with `always` restart policy and healthy status
- Alert deduplication prevents duplicate emails for the same failure within 60 minutes

### Constraint Adherence

- C-07 (Three independent services): Watchdog is completely isolated from other services' code
- C-04 (Railway-only): Railway `always` restart policy provides deadman-switch resilience
- ADR-006 (Independent failure domains): Watchdog communicates only via Postgres, never via HTTP to other services

### Status: PENDING

---

## Milestone 10: End-to-End Integration, Hardening, and Production Readiness

**Goal:** Validate the complete lead lifecycle from raw UCC filing to GHL campaign enrollment. Harden all failure paths. Confirm all 17 constraints are satisfied. Achieve Railway production deployment across all three services.

### Scope Summary

Run a full end-to-end pipeline pass using real state SOS data. Validate each pipeline stage produces correct output. Stress-test the compliance gate with known DNC and litigator entries. Simulate enrichment circuit breaker trips. Trigger self-healing agent repair cycle end-to-end. Verify watchdog alert fires on agent failure. Confirm dashboard reflects real data. Review all modules for C-01 compliance (function length, docstrings, test coverage). Set up Sentry alerts for production error thresholds.

### Deliverables

- [ ] End-to-end test suite: traces one synthetic lead through all 7 pipeline stages in a staging environment
- [ ] Compliance gate stress test: known DNC phone/email blocked at Gate 1; known TCPA litigator blocked at Gate 4
- [ ] Enrichment circuit breaker integration test: >20% error rate triggers HALT; `pipeline_events` records event; pipeline resumes after source recovery
- [ ] Self-healing agent integration test: injected scraper failure -> agent detects -> diagnoses -> creates GitHub issue -> alerts manager
- [ ] Watchdog integration test: agent heartbeat stopped -> watchdog detects within 5 minutes -> email sent
- [ ] Dashboard load time measured and confirmed < 3 seconds against production database
- [ ] Module audit: all functions < 50 lines, all modules have docstrings and test files (C-01)
- [ ] Environment variable checklist: all 24 env vars documented, validated, and set in Railway
- [ ] Railway production deploy: all three services green on `/health` with real data flowing
- [ ] Sentry error thresholds configured: alert fires if unhandled exceptions exceed 50/hour
- [ ] DataMerch fallback path verified: pipeline runs correctly with `DATAMERCH_API_KEY` unset (C-15)

### Dependencies

- All prior milestones (1 through 9)

### Acceptance Criteria

- A UCC filing scraped from a live Tier 1 SOS portal results in a GHL contact + workflow enrollment within one pipeline cycle
- Zero non-compliant leads present in GHL after a full pipeline run with mixed compliant/non-compliant test data
- Self-healing agent detects and files a GitHub issue for an injected scraper failure within 10 minutes
- Watchdog email arrives at `MANAGER_EMAIL` within 6 minutes of agent heartbeat going stale
- All Railway services report healthy; no restarts in 24-hour observation window
- All 17 architectural constraints confirmed satisfied with evidence per constraint

### Constraint Adherence

- All 17 constraints (C-01 through C-17) verified in this milestone's audit
- C-02 (Compliance absolute): Stress test confirms zero bypass paths
- C-08 (Indefinite retention): Confirm no TTL or delete logic present in codebase
- C-05 (Single Postgres): Confirm no second database or cache layer introduced

### Status: PENDING

---

## Milestone Dependency Graph

```
M1 (Foundation)
    |
    +-- M2 (Scraper Engine)
    |       |
    |       +-- M3 (MCA Detection + Scoring)
    |               |
    |               +-- M4 (Enrichment Pipeline)
    |                       |
    |                       +-- M5 (Compliance + Dedup)
    |                               |
    |                               +-- M6 (Export + Webhooks + Recycling)
    |                               |       |
    |                               |       +-- M7 (Dashboard) *
    |                               |
    |                               +-- M8 (Self-Healing Agent)
    |                                       |
    |                                       +-- M9 (Watchdog)
    |
    +-- M10 (End-to-End Integration) -- depends on M1 through M9
```

*M7 (Dashboard) can begin data layer work after M1 but requires M2-M6 for full data population.

---

## Risk Areas

| Risk | Milestones Affected | Mitigation |
|------|--------------------|----|
| State SOS website structure changes break scrapers | M2, M10 | Smoke tests per state; self-healing agent (M8) detects and repairs; Tier 1 states prioritized |
| Anti-bot measures (CAPTCHA, IP bans) on SOS sites | M2 | Tier 3 states use proxy rotation (C-17); Tier 4 skipped at MVP; fallback to data brokers in V2 |
| DataMerch API access denied | M5 | Fallback path built into compliance gate (C-15); pipeline runs without DataMerch configured |
| Enrichment API degradation cascades | M4 | Circuit breaker (C-03) halts pipeline before partial data reaches export queue |
| GHL API schema change breaks export | M6 | CampaignPlatformAdapter isolates GHL; contract tests catch schema drift |
| Self-healing agent creates a bad repair and deploys broken code | M8 | All repairs go through GitHub Actions CI; merge only on test pass; Sentry catches regressions |
| Self-healing agent crashes and produces no heartbeat | M9 | Watchdog (M9) is independent and detects stale heartbeat within 5 minutes |
| Compliance bypass through edge-case data | M5, M10 | Gate is sequential with no override path; compliance_checks audit log for every lead |
| Manager dashboard performance degrades as data grows | M7 | Postgres indexes on hot columns; HTMX partial refresh limits query scope |

---

## Constraints Reference

All 17 constraints are mapped to milestones above. Summary:

| Constraint | Primary Milestone |
|------------|------------------|
| C-01: Zero human developers (AI maintainability) | M1, all milestones |
| C-02: Compliance gate absolute | M5 |
| C-03: Enrichment failure halts pipeline | M4 |
| C-04: Railway deployment only | M1, M9 |
| C-05: Single Postgres database | M1, M10 |
| C-06: Platform-agnostic campaign output | M6 |
| C-07: Three independent Railway services | M1, M8, M9 |
| C-08: Indefinite data retention | M1, M10 |
| C-09: Per-state rate limiting | M2 |
| C-10: Cross-state deduplication | M5 |
| C-11: Non-technical manager dashboard | M7 |
| C-12: Internal DNC irrevocable | M5 |
| C-13: GHL custom fields pre-created | M6 |
| C-14: Python only, no JS build toolchain | M1, M7 |
| C-15: DataMerch fallback | M5 |
| C-16: GitHub as source of truth | M1, M8 |
| C-17: Tiered scraping strategy | M2 |
