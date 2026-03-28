# Master Plan — UCC Business Debt Lead Generation Platform

## Overview

This plan organizes the build into 10 milestones representing coherent feature areas. Each milestone produces a working, testable increment. The ordering respects data-flow dependencies (scraping before enrichment, enrichment before compliance, compliance before export) and infrastructure dependencies (database before services, services before agent). CI/CD is established in Milestone 1 so every subsequent milestone inherits it.

All 17 hard constraints (C-01 through C-17) are enforced throughout. All 7 pipeline stages, the manager dashboard, self-healing agent, heartbeat watchdog, and CI/CD are addressed.

---

## Synthesis Summary

This plan synthesizes two competing architecture plans. Key resolution decisions:

| Topic | Resolution | Rationale |
|-------|-----------|-----------|
| CI/CD timing | Milestone 1 (not final) | Every milestone inherits automated testing; C-16 satisfied from day one |
| Compliance vs Dedup grouping | Separate milestones | Compliance (C-02) is legally critical; deserves focused milestone |
| Tier 2/3 scraper timing | Built in Milestone 2 | SC-01 requires 45+ states; same framework applies to all tiers |
| Sentry integration | Milestone 1 | Agent (M8) reads Sentry events; error tracking must exist early |
| Agent dependencies | M1 + M2 + M4 | Enables parallel work; agent monitors scrapers and enrichment primarily |
| Final milestone scope | Pure integration and hardening | No new infrastructure; focused on end-to-end validation |
| Job queue pattern | Explicit M1 deliverable | ADR-010 pattern is non-trivial infrastructure others depend on |

---

### Milestone 1: Foundation, Database, and CI/CD

**Goal**: Establish the project skeleton, database schema, CI/CD pipeline, Railway deployment stubs, and shared infrastructure so all subsequent milestones have a working foundation.

**Deliverables**:
- [ ] Python project structure matching architecture module layout with pyproject.toml and all declared dependencies
- [ ] Configuration module using pydantic-settings covering all environment variables; validation fails fast on missing required vars
- [ ] SQLAlchemy 2.0 async engine and session factory
- [ ] ORM models for all tables: ucc_filings, leads, mca_aliases, enrichment_cache, internal_dnc, compliance_checks, state_priority, scraper_runs, job_queue, enrichment_retry_queue, agent_heartbeat, pipeline_events, langgraph_checkpoints
- [ ] Alembic migration infrastructure with initial migration creating all tables
- [ ] Postgres job queue implementation using SELECT FOR UPDATE SKIP LOCKED pattern
- [ ] structlog JSON logging configuration with required fields (component, status, error_type, context)
- [ ] Health check endpoints for all three services (pipeline, agent, watchdog)
- [ ] FastAPI application entry point for pipeline service; stub entry points for agent and watchdog
- [ ] Procfile with three service entries and railway.toml with restart policies (on-failure/on-failure/always) and health check paths
- [ ] GitHub Actions workflow running pytest on every push and PR to main
- [ ] Sentry SDK initialized in all three service entry points
- [ ] pytest configuration with conftest, test database fixtures, and foundational unit tests
- [ ] Environment variable reference file listing all required variables

**Dependencies**: None (root milestone)

**Acceptance Criteria**:
- Railway reports all three services healthy on /health
- alembic upgrade head creates all tables in a fresh Postgres instance
- Job queue insert/claim/complete cycle works in integration test
- GitHub Actions pipeline passes on push
- structlog produces valid JSON with all required fields
- Configuration module raises validation error when a required env var is absent
- Sentry captures a test exception from each service

**Scope Boundaries**: No business logic. No scraper code, no enrichment, no compliance, no dashboard UI. This is infrastructure only.

---

### Milestone 2: Scraper Engine

**Goal**: Build the scraping subsystem that extracts raw UCC filings from state SOS websites across all tiers, respecting per-state rate limits and the tiered strategy.

**Deliverables**:
- [ ] Abstract base scraper class with standard interface
- [ ] State scraper registry mapping state codes to scraper classes and tier assignments
- [ ] Per-state rate limiter with configurable delays (default 1 req/3s, Tier 3 at 1 req/10s) with jitter and exponential backoff on errors
- [ ] Session manager for cookie/ViewState persistence per state
- [ ] httpx-based scraper implementations for Tier 1 states (NY, CA, TX, FL, NJ, GA, IL, PA, OH, MD)
- [ ] Tier 2 state scrapers (~24 states) with session management
- [ ] Tier 3 state scrapers (~6 states) with proxy rotation
- [ ] Tier 4 (DC, NYC) stubbed but skipped at MVP
- [ ] Playwright-based scraper support for JS-rendered portals
- [ ] HTML parsing layer for SOS portal responses
- [ ] User-Agent rotation
- [ ] Scraper run logging to scraper_runs table (state, started_at, finished_at, records_found, status, error_detail)
- [ ] APScheduler job definitions for cadenced scraping (daily Tier 1, daily-to-48h Tier 2, 48h+ Tier 3)
- [ ] Smoke test per state scraper, scheduled daily (not on push)
- [ ] Unit tests for parsing logic; integration tests for scraper-to-database flow

**Dependencies**: Milestone 1 (database, job queue, logging, CI/CD)

**Acceptance Criteria**:
- All Tier 1 state scrapers successfully fetch and parse UCC filings in integration tests
- Tier 2 and Tier 3 scrapers have passing unit tests and smoke tests
- Per-state rate limiting enforced (measurable delay between requests)
- Scraped records written to ucc_filings table with all required columns
- Scraper run metadata logged to scraper_runs table for every execution
- APScheduler triggers scrape jobs on configured tier cadence
- No scraper function exceeds 50 lines (C-01)
- Playwright-dependent scrapers run without error in the Railway Python environment

**Scope Boundaries**: No MCA detection, no scoring, no enrichment. Raw filing ingestion only.

---

### Milestone 3: MCA Detection and Lead Scoring

**Goal**: Identify MCA-related filings from raw UCC data and score leads by financial distress level, producing scored lead records ready for enrichment.

**Deliverables**:
- [ ] MCA detector module with alias matching engine against mca_aliases table
- [ ] Seed data for known MCA lenders and common shell company names
- [ ] Alias updater module for self-improving detection via nightly pattern analysis job
- [ ] Lead scoring engine using position count (primary signal), filing recency, and collateral type analysis
- [ ] Score tier assignment logic (hot/warm/cold)
- [ ] Pipeline wiring: scraper output feeds detector, detector output feeds scorer, scored leads written to leads table with enrichment_status pending
- [ ] Canonical debtor name written to support downstream fuzzy matching (C-10)
- [ ] Unit tests for alias matching (exact match, fuzzy match, shell company patterns)
- [ ] Unit tests for scoring algorithm with known test cases

**Dependencies**: Milestone 1 (database), Milestone 2 (scraper output in ucc_filings)

**Acceptance Criteria**:
- Known MCA lender names matched with high confidence in test data
- Shell company aliases correctly resolved to canonical lender names
- Lead score calculated and persisted for all detected MCA filings
- Position count across multiple filings correctly aggregated per debtor
- Scoring produces distinct tier assignments for test data with varying distress signals
- Alias updater job runs nightly without error
- Higher scores assigned to filings with more secured-party positions

**Scope Boundaries**: No enrichment, no compliance checks. Detection and scoring only.

---

### Milestone 4: Enrichment Pipeline

**Goal**: Add phone, email, revenue, and owner name to scored leads via a waterfall of enrichment sources with circuit breaker protection and permanent caching.

**Deliverables**:
- [ ] Generic waterfall executor accepting ordered strategy callables, shared by enrichment, compliance, and scraper fallback subsystems
- [ ] Enrichment source connectors: People Data Labs, Apollo, OpenCorporates, Whitepages, Twilio Lookup, SOS officer scraping
- [ ] Enrichment cache backed by Postgres (permanent, no TTL per C-08)
- [ ] Circuit breaker wrapper (pybreaker) per source with configurable thresholds (>20% errors in 5 min)
- [ ] Pipeline HALT mechanism: open circuit writes HALT event to pipeline_events and suspends export queue processing
- [ ] Enrichment retry queue with exponential backoff schedule (1h, 4h, 24h, 72h)
- [ ] Pipeline integration: scored leads fed into enrichment waterfall
- [ ] Contract tests validating each enrichment source response schema
- [ ] Unit tests for waterfall executor, cache hit/miss, circuit breaker state transitions
- [ ] Integration tests for waterfall executor with mock sources

**Dependencies**: Milestone 1 (database, job queue), Milestone 3 (scored leads)

**Acceptance Criteria**:
- Waterfall executor tries sources in configured order, returns first success
- Cache prevents duplicate API calls for previously enriched entities; cached result includes fetch timestamp
- Circuit breaker opens after threshold exceeded; HALT event appears in pipeline_events
- Failed enrichments written to enrichment_retry_queue with correct backoff schedule
- Partially enriched leads never marked as enrichment_status complete (C-03)
- Contract tests validate each source's response schema
- APScheduler retries failed enrichments at backoff intervals

**Scope Boundaries**: No compliance checks, no dedup, no export. Enrichment only.

---

### Milestone 5: Compliance Gate

**Goal**: Enforce the absolute 4-layer compliance check that blocks non-compliant leads from export. Zero tolerance (C-02).

**Deliverables**:
- [ ] Compliance gate orchestrator enforcing sequential 4-layer check order
- [ ] Layer 1: Internal DNC table check (phone + email checked independently, checked first before any paid API calls per C-12)
- [ ] Layer 2: DataMerch API client with fallback to UCC filing pattern analysis when API key is unconfigured (C-15)
- [ ] Layer 3: DNC.com or CCC API client for federal + state DNC scrub
- [ ] Layer 4: Blacklist Alliance API client for TCPA litigator screening
- [ ] Compliance check audit log: every check recorded to compliance_checks table (gate name, result, timestamp)
- [ ] Permanent block on any layer failure — no override, no soft flag, no export-with-warning
- [ ] Warning log emitted on every lead when DataMerch is unconfigured
- [ ] Internal DNC CRUD operations: append-only writes; manager-only reversal requires explicit audit trail (C-12)
- [ ] Unit tests for gate orchestration, each layer independently, and the DataMerch fallback path
- [ ] Integration tests for full gate pass/fail scenarios
- [ ] Negative testing: verify no code path exists to bypass the compliance gate

**Dependencies**: Milestone 1 (database), Milestone 4 (enriched leads)

**Acceptance Criteria**:
- A lead failing any layer is permanently blocked from export
- Internal DNC is checked before any paid API calls
- All compliance checks logged with gate name, result, and timestamp regardless of pass/fail
- DataMerch fallback activates when API key is unconfigured and logs a warning
- No code path exists to bypass the compliance gate
- Internal DNC entries are append-only; reversal requires explicit audit trail
- Internal DNC entries cannot be removed by any automated code path

**Scope Boundaries**: No dedup, no export, no dashboard. Compliance enforcement only.

---

### Milestone 6: Deduplication and Campaign Export

**Goal**: Eliminate duplicate leads across states and scrape cycles, export qualified leads to GoHighLevel via the platform-agnostic adapter, handle disposition feedback, and recycle eligible leads.

**Deliverables**:
- [ ] Deduplicator module: exact match (business name + state + filing number) and fuzzy cross-state match (C-10)
- [ ] Position count tracking across all filings per business
- [ ] Abstract CampaignPlatformAdapter interface with four methods per C-06
- [ ] Concrete GHL adapter: upsert + tiered workflow enrollment using GHL API v2, exponential backoff on failure
- [ ] GHL custom field validation at service startup: verifies all 8 required custom fields exist before pipeline runs (C-13)
- [ ] Three workflow environment variables for tier routing (tier-1/2/3)
- [ ] CSV fallback export for manual upload when GHL API is unavailable
- [ ] GHL webhook receiver for disposition feedback (OpportunityUpdate, ContactUpdate) with payload verification via webhook secret
- [ ] Lead recycling module: re-queue eligible leads after configurable cooldown (default 30 days) based on disposition
- [ ] Unit tests for dedup logic (exact + fuzzy), adapter interface compliance, webhook parsing, recycler cooldown
- [ ] Integration tests for full export flow

**Dependencies**: Milestone 1 (database), Milestone 5 (compliant leads)

**Acceptance Criteria**:
- No duplicate lead records in export queue across states or scrape cycles
- Fuzzy matching catches same business filed in different states
- GHL upsert creates/updates contacts with all custom fields populated
- Workflow enrollment routes leads to correct tier workflow
- GHL custom field validation fails fast at startup if any required field is absent
- CSV fallback produces a valid file when GHL API is unavailable
- Webhook receiver verifies signature (401 on invalid) and writes disposition to leads table
- Recycler re-queues leads after cooldown with correct disposition filtering
- Pipeline code imports only the abstract adapter, never GHL-specific modules (C-06)

**Scope Boundaries**: No dashboard UI, no agent monitoring. Export pipeline only.

---

### Milestone 7: Manager Dashboard

**Goal**: Deliver a server-rendered monitoring dashboard for the non-technical manager showing pipeline health, lead metrics, compliance stats, and alerts.

**Deliverables**:
- [ ] Dashboard HTTP routes served from the pipeline service
- [ ] Jinja2 templates: base layout, main dashboard, scraper status, lead metrics, compliance stats, alerts
- [ ] HTMX integration for periodic partial-page refresh (polling every 30 seconds, no full page reload)
- [ ] Tailwind CSS via CDN for styling
- [ ] Chart.js via CDN for pipeline metric charts
- [ ] Dashboard views: pipeline health overview, lead counts by stage, compliance pass rates, scraper status by state, recent alerts, state priority table
- [ ] CSV upload endpoint for manual tier assignment (C-11)
- [ ] Access control via Railway private networking or basic auth at MVP
- [ ] All labels describe business outcomes — no technical jargon, no error codes, no stack traces
- [ ] Tests for dashboard routes and data aggregation queries

**Dependencies**: Milestone 1 (database, FastAPI), Milestone 2 (scraper data), Milestone 3 (scoring data), Milestone 4 (enrichment data), Milestone 5 (compliance data), Milestone 6 (export and disposition data)

**Acceptance Criteria**:
- Dashboard renders all specified views with real data from database
- No technical jargon visible in the UI (C-11)
- HTMX polling updates data without full page reload
- CSV upload for tier assignment works end-to-end
- Page load under 3 seconds with representative data volume (SC-07)
- Dashboard accessible only via configured auth mechanism

**Scope Boundaries**: No new pipeline logic. Visualization and monitoring only. No complex auth system.

---

### Milestone 8: Self-Healing Agent

**Goal**: Build the LangGraph-based autonomous agent that monitors pipeline health, diagnoses failures, attempts repairs, and alerts the manager.

**Deliverables**:
- [ ] LangGraph agent graph with cyclical nodes: detect, diagnose, repair, verify, alert
- [ ] Postgres checkpointer for LangGraph state persistence across service restarts
- [ ] Detector node: reads pipeline_events, scraper_runs, structured logs, and Sentry error events; surfaces anomalies by severity
- [ ] Diagnostician node: LLM-based failure analysis via Claude API producing human-readable diagnosis
- [ ] Repairer node: generates fix, applies to staging branch via GitHub API, triggers CI run
- [ ] Verifier node: checks CI result via GitHub API; merge to main on pass, create GitHub issue on fail
- [ ] Alerter node: SendGrid plain-English email to manager; no more than one email per unique failure type per 24-hour window
- [ ] GitHub issue automation: create issues with priority labels (priority-high for Tier 1 states), check for duplicate open issues before filing (C-16)
- [ ] Priority-based repair ordering using state_priority table (Tier 1 states first)
- [ ] State priority nightly recalculation job ranking states by recent lead volume
- [ ] Heartbeat writer: timestamp to agent_heartbeat table every 60 seconds
- [ ] Agent health check endpoint
- [ ] Agent entry point as separate Railway service
- [ ] Tests for each node independently and for graph state transitions

**Dependencies**: Milestone 1 (database, logging, Sentry, GitHub Actions), Milestone 2 (scrapers to monitor), Milestone 4 (enrichment to monitor)

**Acceptance Criteria**:
- Agent detects simulated scraper failure via structured logs within one detection cycle
- Diagnosis node produces human-readable failure analysis
- Repair node creates a branch with a fix and triggers CI
- Successful repair merges to main; failed repair creates GitHub issue with priority label
- Manager receives plain-English email alert with no stack traces
- No more than one email per unique failure type per 24 hours
- Heartbeat written to Postgres every 60 seconds
- Priority queue processes Tier 1 states before lower tiers
- Agent state survives service restart (Postgres checkpointer)
- LangGraph checkpoint persists to langgraph_checkpoints table

**Scope Boundaries**: No pipeline business logic changes. Monitoring and repair only. Agent does not modify compliance gate behavior.

---

### Milestone 9: Heartbeat Watchdog

**Goal**: Deploy an independent deadman switch that monitors the self-healing agent and alerts the manager if the agent itself fails.

**Deliverables**:
- [ ] Watchdog loop checking agent_heartbeat table every 5 minutes
- [ ] Staleness detection: alert if heartbeat is older than 5 minutes
- [ ] Lead flow check: alert if no new records inserted in expected pipeline window
- [ ] Direct SendGrid email alert to manager (bypasses agent entirely); plain English
- [ ] Alert deduplication: no more than one alert per failure type per 60-minute window
- [ ] Watchdog health check endpoint
- [ ] Watchdog entry point as separate Railway service with always restart policy
- [ ] Zero code dependency on pipeline or agent service code (C-07): no imports from app/ or agent/ namespaces
- [ ] Tests for staleness detection logic, lead flow check, and alert triggering

**Dependencies**: Milestone 1 (database), Milestone 8 (heartbeat writer)

**Acceptance Criteria**:
- Watchdog detects stale heartbeat (>5 min) within one check cycle
- Email alert sent directly to manager without involving the agent
- Watchdog sends no email when heartbeat is fresh
- Watchdog has zero imports from app/ or agent/ packages
- Service restarts automatically on crash (Railway always policy)
- Watchdog continues operating when pipeline and agent services are down
- Alert deduplication prevents duplicate emails for same failure within 60 minutes

**Scope Boundaries**: No pipeline logic, no agent logic. Pure monitoring and alerting.

---

### Milestone 10: End-to-End Integration and Production Readiness

**Goal**: Validate the complete lead lifecycle from raw UCC filing to GHL campaign enrollment. Harden all failure paths. Confirm all 17 constraints are satisfied. Achieve production deployment.

**Deliverables**:
- [ ] End-to-end test suite tracing a synthetic lead through all 7 pipeline stages
- [ ] Compliance gate stress test: known DNC phone/email blocked at Gate 1; known TCPA litigator blocked at Gate 4
- [ ] Enrichment circuit breaker integration test: >20% error rate triggers HALT; pipeline resumes after source recovery
- [ ] Self-healing agent integration test: injected failure detected, diagnosed, and results in GitHub issue and manager alert
- [ ] Watchdog integration test: agent heartbeat stopped, watchdog detects within 5 minutes, email sent
- [ ] Dashboard load time confirmed under 3 seconds against production-representative data
- [ ] Module audit: all functions under 50 lines, all modules have docstrings and test files (C-01)
- [ ] All 17 architectural constraints verified with evidence per constraint
- [ ] Environment variable checklist: all required vars documented, validated, and set in Railway
- [ ] Railway production deployment: all three services green on /health with real data flowing
- [ ] Sentry error thresholds configured for production alerting
- [ ] DataMerch fallback path verified: pipeline runs correctly with DataMerch API key unset (C-15)
- [ ] Smoke test schedule confirmed (daily, not on push)
- [ ] Auto-deploy to Railway on main branch merge confirmed

**Dependencies**: All prior milestones (1-9)

**Acceptance Criteria**:
- A UCC filing scraped from a live Tier 1 SOS portal results in a GHL contact and workflow enrollment within one pipeline cycle
- Zero non-compliant leads present in GHL after a full pipeline run with mixed test data
- Self-healing agent detects and files a GitHub issue for an injected scraper failure within 10 minutes
- Watchdog email arrives within 6 minutes of agent heartbeat going stale
- All Railway services report healthy; no unexpected restarts in 24-hour observation window
- All 17 architectural constraints confirmed satisfied with documented evidence

**Scope Boundaries**: No new features. Integration, validation, and hardening only.

---

## Milestone Dependency Graph

```
M1 (Foundation + CI/CD)
 |
 +---> M2 (Scraper Engine — all tiers)
 |      |
 |      +---> M3 (MCA Detection + Scoring)
 |             |
 |             +---> M4 (Enrichment Pipeline)
 |                    |
 |                    +---> M5 (Compliance Gate)
 |                    |      |
 |                    |      +---> M6 (Dedup + Export)
 |                    |             |
 |                    |             +---> M7 (Dashboard)
 |                    |
 |                    +---> M8 (Self-Healing Agent) [parallel with M5-M7]
 |                           |
 |                           +---> M9 (Watchdog)
 |
 +---> M10 (Integration + Hardening) [after all milestones 1-9]
```

Note: Milestones 5-7 and 8-9 can proceed in parallel once M4 is complete. Milestone 10 is the final integration milestone.

---

## Risk Areas

| Risk | Constraints | Mitigation |
|------|------------|------------|
| State SOS websites change structure frequently | C-09, C-17 | Smoke tests per scraper (M2); self-healing agent detects and repairs (M8); Tier 1 states prioritized |
| Compliance gate bypass through code defect | C-02, C-12 | Dedicated compliance milestone (M5) with negative testing; audit log enables verification |
| Enrichment source API changes or outages | C-03, C-08 | Circuit breakers, retry queues, and contract tests (M4) detect issues early |
| LangGraph version instability | ADR-007 | Pin LangGraph version; test graph state transitions explicitly (M8) |
| Railway resource limits at scale | C-04, C-05 | Single Postgres sufficient at 10K leads/month; monitor and plan scaling beyond 100K |
| DataMerch vendor access denied | C-15 | Fallback path in compliance gate (M5) functions without DataMerch |
| GHL API rate limits or changes | C-06 | CSV fallback (M6); adapter pattern isolates all GHL-specific code |
| Self-healing agent creates bad repair | C-16 | All repairs go through GitHub Actions CI before merge; Sentry catches regressions |
| Anti-bot measures on SOS sites | C-17 | Tier 3 proxy rotation; Tier 4 skipped at MVP; fallback to data brokers in V2 |

---

## Constraint Coverage

| Constraint | Primary Milestone(s) |
|------------|---------------------|
| C-01: Zero human developers (AI maintainability) | All milestones |
| C-02: Compliance gate absolute | M5 |
| C-03: Enrichment failure halts pipeline | M4 |
| C-04: Railway deployment only | M1, M9 |
| C-05: Single Postgres database | M1, M10 |
| C-06: Platform-agnostic campaign output | M6 |
| C-07: Three independent Railway services | M1, M8, M9 |
| C-08: Indefinite data retention | M1, M4, M10 |
| C-09: Per-state rate limiting | M2 |
| C-10: Cross-state deduplication | M3, M6 |
| C-11: Non-technical manager dashboard | M7 |
| C-12: Internal DNC irrevocable | M5 |
| C-13: GHL custom fields pre-created | M6 |
| C-14: Python only, no JS build toolchain | M1, M7 |
| C-15: DataMerch fallback | M5 |
| C-16: GitHub as source of truth | M1, M8 |
| C-17: Tiered scraping strategy | M2 |
