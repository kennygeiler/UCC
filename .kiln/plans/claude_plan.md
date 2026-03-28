# Build Plan -- UCC Business Debt Lead Generation Platform

## Plan Overview

This plan organizes the build into milestones representing coherent feature areas. Each milestone produces a working, testable increment. The ordering respects data flow dependencies (scraping before enrichment, enrichment before compliance, compliance before export) and infrastructure dependencies (database before services, services before agent).

Constraints C-01 through C-17 from arch-constraints.md are enforced throughout. Key cross-cutting constraints:
- C-01 (Zero human developers): Every module has tests, docstrings, structured logging, no metaprogramming.
- C-04/C-05 (Railway-only, single Postgres): No Redis, no external queues, no non-Railway infrastructure.
- C-14 (Python only, no JS build toolchain): Server-rendered templates only.

---

## Milestone 1: Project Foundation and Database Layer

**Goal:** Establish the project skeleton, configuration, database schema, and migration infrastructure so all subsequent milestones have a working data layer to build on.

**Deliverables:**
- [ ] Python project structure matching architecture.md module layout (pyproject.toml, app/, agent/, watchdog/, tests/, migrations/)
- [ ] pydantic-settings configuration module loading all environment variables from arch doc
- [ ] SQLAlchemy 2.0 ORM models for all tables: ucc_filings, leads, mca_aliases, enrichment_cache, internal_dnc, compliance_checks, state_priority, scraper_runs, job_queue, enrichment_retry_queue, agent_heartbeat, pipeline_events
- [ ] Alembic migration infrastructure with initial migration creating all tables
- [ ] Database session factory (async SQLAlchemy engine)
- [ ] Postgres job queue implementation (SELECT FOR UPDATE SKIP LOCKED pattern per ADR-010)
- [ ] structlog JSON logging configuration (per ADR-009)
- [ ] Health check endpoint (GET /health) for Railway
- [ ] FastAPI application entry point (app/main.py)
- [ ] pytest configuration with conftest.py, test database fixtures
- [ ] Unit tests for configuration, models, and job queue

**Dependencies:** None (first milestone)

**Acceptance Criteria:**
- `alembic upgrade head` creates all tables in a Postgres instance
- Job queue insert/claim/complete cycle works in integration test
- `GET /health` returns 200
- `pytest` passes with all foundation tests green
- structlog produces JSON output on all log calls

**Traces to:** SC-06 (data layer for dedup), SC-11 (AI-maintainable codebase), all goals (foundation)

---

## Milestone 2: Scraper Engine

**Goal:** Build the scraping subsystem that extracts raw UCC filings from state SOS websites, respecting per-state rate limits and tiering strategy.

**Deliverables:**
- [ ] Abstract base scraper class with standard interface (per architecture.md)
- [ ] State scraper registry mapping state codes to scraper classes
- [ ] Per-state rate limiter with configurable delays (C-09: default 1 req/3s, Tier 3 at 1 req/10s)
- [ ] Session manager for cookie/ViewState persistence
- [ ] httpx-based scraper implementations for Tier 1 states (top 10: NY, CA, TX, FL, NJ, GA, IL, PA, OH, MD)
- [ ] Playwright-based scraper support for JS-rendered portals
- [ ] BeautifulSoup4 HTML parsing layer
- [ ] User-Agent rotation
- [ ] Exponential backoff with jitter on HTTP errors
- [ ] Scraper run logging to scraper_runs table
- [ ] APScheduler job definitions for cadenced scraping (C-17 tiered cadence)
- [ ] Smoke test framework for live SOS portal validation
- [ ] Unit tests for parsing logic; integration tests for scraper-to-database flow

**Dependencies:** Milestone 1 (database layer, job queue, logging)

**Acceptance Criteria:**
- At least 5 Tier 1 state scrapers successfully fetch and parse UCC filings in integration tests
- Rate limiting enforced (measurable delay between requests)
- Scraped records written to ucc_filings table with all required columns
- Scraper run metadata logged to scraper_runs table
- Each scraper has a corresponding smoke test
- APScheduler triggers scrape jobs on configured cadence

**Traces to:** SC-01 (scrape 45+ states), SC-11 (AI-maintained), C-09 (rate limits), C-17 (tiered strategy)

---

## Milestone 3: MCA Detection and Lead Scoring

**Goal:** Identify MCA-related filings from raw UCC data and score leads by financial distress level.

**Deliverables:**
- [ ] MCA detector module with alias matching engine against mca_aliases table
- [ ] Seed data for known MCA lenders and common shell company names
- [ ] Alias updater module for self-improving detection (pattern analysis job)
- [ ] Lead scoring engine: position count, filing recency, collateral type analysis
- [ ] Score tier assignment logic (hot/warm/cold)
- [ ] Pipeline integration: scraper output feeds detector, detector output feeds scorer
- [ ] Unit tests for alias matching (exact match, fuzzy match, shell company patterns)
- [ ] Unit tests for scoring algorithm with known test cases

**Dependencies:** Milestone 1 (database), Milestone 2 (scraper output in ucc_filings)

**Acceptance Criteria:**
- Known MCA lender names matched with high confidence in test data
- Shell company aliases correctly resolved to canonical lender names
- Lead score calculated and persisted for all detected MCA filings
- Position count across multiple filings correctly aggregated per debtor
- Scoring produces distinct tier assignments for test data with varying distress signals

**Traces to:** SC-02 (MCA alias detection), SC-03 (lead scoring), Goal 2 (speed to lead)

---

## Milestone 4: Enrichment Pipeline

**Goal:** Add phone, email, revenue, and owner name to scored leads via a waterfall of enrichment sources with circuit breaker protection.

**Deliverables:**
- [ ] Generic waterfall executor (ADR-008) accepting ordered strategy callables
- [ ] Enrichment source implementations: PDL, Apollo, OpenCorporates, Whitepages, Twilio Lookup, SOS officer scraping
- [ ] Enrichment cache (Postgres-backed, permanent per C-08)
- [ ] Circuit breaker wrapper (pybreaker) per source with configurable thresholds (>20% errors in 5 min)
- [ ] Pipeline HALT mechanism on circuit breaker open (C-03)
- [ ] Enrichment retry queue with exponential backoff (1h, 4h, 24h, 72h)
- [ ] Pipeline integration: scored leads fed into enrichment waterfall
- [ ] Contract tests validating enrichment API response schemas
- [ ] Unit tests for waterfall executor, cache hit/miss, circuit breaker state transitions

**Dependencies:** Milestone 1 (database, job queue), Milestone 3 (scored leads)

**Acceptance Criteria:**
- Waterfall executor tries sources in configured order, returns first success
- Cache prevents duplicate API calls for previously enriched entities
- Circuit breaker opens after threshold exceeded; pipeline halts
- Failed enrichments written to enrichment_retry_queue with correct backoff schedule
- Partially enriched leads never marked as enrichment_status=complete
- Contract tests validate each source's response schema

**Traces to:** SC-04 (enrichment coverage), C-03 (halt on failure), C-08 (permanent cache), ADR-008 (waterfall pattern)

---

## Milestone 5: Compliance Gate

**Goal:** Enforce the absolute 4-layer compliance check that blocks non-compliant leads from export. Zero tolerance (C-02).

**Deliverables:**
- [ ] Compliance gate orchestrator enforcing sequential 4-layer check order
- [ ] Layer 1: Internal DNC table check (phone + email, checked first per C-12)
- [ ] Layer 2: DataMerch API client with fallback to UCC filing pattern analysis (C-15)
- [ ] Layer 3: DNC.com or CCC API client for federal + state DNC scrub
- [ ] Layer 4: Blacklist Alliance API client for TCPA litigator screening
- [ ] Compliance check audit log (every check recorded to compliance_checks table)
- [ ] Permanent block on any layer failure -- no override, no soft flag
- [ ] Warning log when DataMerch is unconfigured (C-15 fallback path)
- [ ] Internal DNC CRUD operations (append-only writes, manager-only reversal with audit trail per C-12)
- [ ] Unit tests for gate orchestration, each layer independently, and the fallback path
- [ ] Integration tests for full gate pass/fail scenarios

**Dependencies:** Milestone 1 (database), Milestone 4 (enriched leads)

**Acceptance Criteria:**
- A lead failing any layer is permanently blocked from export
- Internal DNC is checked before any paid API calls
- All compliance checks logged with gate name, result, and timestamp
- DataMerch fallback activates when API key is unconfigured and logs a warning
- No code path exists to bypass the compliance gate
- Internal DNC entries are append-only; reversal requires explicit audit trail

**Traces to:** SC-05 (100% compliance), C-02 (absolute gate), C-12 (irrevocable DNC), C-15 (DataMerch fallback), Goal 3 (legal compliance)

---

## Milestone 6: Deduplication and Campaign Export

**Goal:** Eliminate duplicate leads across states and scrape cycles, then export qualified leads to GoHighLevel via API with tiered workflow enrollment.

**Deliverables:**
- [ ] Deduplicator module: exact match (business name + state + filing number) and fuzzy cross-state match (C-10)
- [ ] Position count tracking across all filings per business
- [ ] CampaignPlatformAdapter abstract interface with 4 methods (ADR-005, C-06)
- [ ] GHLAdapter concrete implementation: upsert + workflow enrollment (ADR-004)
- [ ] Tiered workflow enrollment (tier-1/2/3 mapped to GHL workflow IDs)
- [ ] GHL custom field mapping (C-13)
- [ ] CSV fallback export for manual upload when API is unavailable
- [ ] GHL webhook receiver for disposition feedback (OpportunityUpdate, ContactUpdate)
- [ ] Webhook payload verification via GHL_WEBHOOK_SECRET
- [ ] Lead recycling module: re-queue eligible leads after configurable cooldown (default 30 days)
- [ ] Unit tests for dedup logic (exact + fuzzy), adapter interface compliance, webhook parsing
- [ ] Integration tests for full export flow

**Dependencies:** Milestone 1 (database), Milestone 5 (compliant leads)

**Acceptance Criteria:**
- No duplicate lead records in export queue across states or scrape cycles
- Fuzzy matching catches same business filed in different states
- GHL upsert creates/updates contacts with all custom fields populated
- Workflow enrollment routes leads to correct tier workflow
- CSV fallback produces a valid file when API is unavailable
- Webhook receiver correctly parses disposition updates and syncs to leads table
- Recycler re-queues leads after cooldown with correct disposition filtering
- Pipeline code imports only the abstract adapter, never GHL-specific modules

**Traces to:** SC-06 (no duplicates), SC-10 (lead recycling), C-06 (platform agnosticism), C-10 (cross-state dedup), C-13 (GHL custom fields), ADR-004 (API integration), ADR-005 (adapter pattern)

---

## Milestone 7: Manager Dashboard

**Goal:** Deliver a server-rendered monitoring dashboard for the non-technical manager showing pipeline health, lead metrics, compliance stats, and alerts.

**Deliverables:**
- [ ] FastAPI dashboard routes (app/dashboard/routes.py)
- [ ] Jinja2 templates: base layout, main dashboard, scraper status, lead metrics, compliance stats, alerts
- [ ] HTMX integration for dynamic updates (polling, partial page refresh)
- [ ] Tailwind CSS via CDN for styling
- [ ] Chart.js via CDN for pipeline metric charts
- [ ] Dashboard views: pipeline health overview, lead counts by stage, compliance pass rates, scraper status by state, recent alerts, state priority table
- [ ] CSV upload endpoint for manual tier assignment (C-11)
- [ ] Basic auth or Railway private networking for access control at MVP
- [ ] Page load performance under 3 seconds (SC-07)
- [ ] Tests for dashboard routes and data aggregation queries

**Dependencies:** Milestone 1 (database), Milestone 2 (scraper data), Milestone 5 (compliance data), Milestone 6 (export data)

**Acceptance Criteria:**
- Dashboard renders all specified views with real data from database
- No technical jargon visible in the UI (C-11)
- HTMX polling updates data without full page reload
- CSV upload for tier assignment works end-to-end
- Page load under 3 seconds with representative data volume
- Dashboard accessible only via auth mechanism (basic auth or private networking)

**Traces to:** SC-07 (dashboard performance), C-11 (non-technical UI), C-14 (no JS build toolchain), Goal 5 (manager intelligence)

---

## Milestone 8: Self-Healing Agent

**Goal:** Build the LangGraph-based autonomous agent that monitors pipeline health, diagnoses failures, attempts repairs, and alerts the manager.

**Deliverables:**
- [ ] LangGraph agent graph definition with cyclical nodes (detect -> diagnose -> repair -> verify -> alert)
- [ ] Postgres checkpointer for LangGraph state persistence
- [ ] Detector node: reads structlog JSON, pytest-json-report results, Sentry events
- [ ] Diagnostician node: LLM-based failure analysis via Claude API
- [ ] Repairer node: generates fix, applies to staging branch, runs tests
- [ ] Verifier node: pytest validation of repair; merge to main on pass, GitHub issue on fail
- [ ] Alerter node: SendGrid plain-English email to manager
- [ ] GitHub issue automation (PyGithub): create issues, label by priority, check for duplicates (C-16)
- [ ] Priority-based repair ordering using state_priority table (Tier 1 states first)
- [ ] Heartbeat writer: timestamp to agent_heartbeat table every 60 seconds
- [ ] Agent health check endpoint (GET /health)
- [ ] Agent entry point (agent/main.py) as separate Railway service
- [ ] Tests for each node independently, graph state transitions

**Dependencies:** Milestone 1 (database, logging), Milestone 2 (scrapers to monitor), Milestone 4 (enrichment to monitor)

**Acceptance Criteria:**
- Agent detects simulated scraper failure via structured logs
- Diagnosis node produces human-readable failure analysis
- Repair node creates a branch with a fix and runs tests
- Successful repair merges to main; failed repair creates GitHub issue with priority label
- Manager receives plain-English email alert for failures
- Heartbeat written to Postgres every 60 seconds
- Priority queue processes Tier 1 states before lower tiers
- Agent state survives Railway service restart (Postgres checkpointer)

**Traces to:** SC-08 (self-healing), SC-11 (zero human intervention), C-01 (AI-managed), C-16 (GitHub as source of truth), ADR-007 (LangGraph), Goal 4 (no human developers)

---

## Milestone 9: Heartbeat Watchdog

**Goal:** Deploy an independent deadman switch that monitors the self-healing agent and alerts the manager if the agent itself fails.

**Deliverables:**
- [ ] Watchdog loop checking agent_heartbeat table every 5 minutes
- [ ] Staleness detection: alert if heartbeat is older than 5 minutes
- [ ] Lead flow check: alert if no new records inserted in expected window
- [ ] Direct SendGrid email alert to manager (bypasses agent entirely)
- [ ] Watchdog health check endpoint (GET /health)
- [ ] Watchdog entry point (watchdog/main.py) as separate Railway service
- [ ] Railway restart policy: `always`
- [ ] Zero code dependency on pipeline or agent service code (C-07)
- [ ] Tests for staleness detection logic and alert triggering

**Dependencies:** Milestone 1 (database), Milestone 8 (heartbeat writer)

**Acceptance Criteria:**
- Watchdog detects stale heartbeat (>5 min) in test scenario
- Email alert sent directly to manager without involving the agent
- Watchdog has zero imports from app/ or agent/ packages
- Service restarts automatically on crash (Railway `always` policy)
- Watchdog continues operating when pipeline and agent services are down

**Traces to:** SC-09 (watchdog for the watchdog), C-07 (independent services), Goal 4 (autonomous operation)

---

## Milestone 10: CI/CD, Deployment, and Integration Testing

**Goal:** Establish the full CI/CD pipeline, Railway deployment configuration, and end-to-end integration testing.

**Deliverables:**
- [ ] GitHub Actions workflow: pytest (unit + integration + contract) on push/PR
- [ ] Railway configuration: railway.toml, Procfile defining all 3 services
- [ ] Railway health check paths configured for all services
- [ ] Railway restart policies: pipeline (on-failure, 3 retries), agent (on-failure), watchdog (always)
- [ ] Environment variable configuration documentation for Railway
- [ ] Sentry SDK integration for all 3 services
- [ ] End-to-end integration test: filing -> detect -> score -> enrich -> comply -> dedup -> export
- [ ] Smoke test schedule (daily, not on push)
- [ ] Auto-deploy to Railway on main branch merge
- [ ] Remaining Tier 2 and Tier 3 state scrapers (expanding beyond Tier 1 from Milestone 2)

**Dependencies:** All prior milestones (1-9)

**Acceptance Criteria:**
- GitHub Actions runs pytest on every push and PR; blocks merge on failure
- All 3 Railway services deploy and pass health checks
- End-to-end test exercises the full 7-stage pipeline with test data
- Smoke tests run on daily schedule and report results via pytest-json-report
- Sentry captures unhandled exceptions from all services
- State scraper coverage expanded to include Tier 2 states

**Traces to:** SC-01 (45+ states), SC-11 (zero human intervention), C-04 (Railway deployment), C-16 (GitHub CI/CD), Goal 4 (autonomous operation)

---

## Risk Areas

| Risk | Relevant Constraints | Mitigation in Plan |
|------|---------------------|-------------------|
| State SOS websites change structure frequently | C-09, C-17 | Milestone 2 builds smoke tests per scraper; Milestone 8 builds self-healing repair. Tier 1 states prioritized. |
| Compliance gate bypass through code defect | C-02, C-12 | Milestone 5 includes negative testing (no code path bypasses gate). Compliance check audit log enables verification. |
| Enrichment source API changes or outages | C-03 | Milestone 4 builds circuit breakers, retry queues, and contract tests to detect schema drift. |
| LangGraph version instability | ADR-007 | Milestone 8 pins LangGraph version and tests graph state transitions explicitly. |
| Railway resource limits at scale | C-04, C-05 | Single Postgres is sufficient at 10K leads/month per ADR-002. Monitor and plan Redis addition only beyond 100K. |
| DataMerch vendor access denied | C-15 | Milestone 5 includes fallback path (UCC filing pattern analysis) that functions without DataMerch. |
| GHL API rate limits or changes | ADR-004, C-06 | Milestone 6 includes CSV fallback. Adapter pattern isolates all GHL-specific code. |

---

## Milestone Dependency Graph

```
M1 (Foundation)
 |
 +---> M2 (Scraper Engine)
 |      |
 |      +---> M3 (MCA Detection + Scoring)
 |             |
 |             +---> M4 (Enrichment Pipeline)
 |                    |
 |                    +---> M5 (Compliance Gate)
 |                           |
 |                           +---> M6 (Dedup + Export)
 |                           |      |
 |                           +------+---> M7 (Dashboard)
 |
 +---> M8 (Self-Healing Agent) [can start after M1+M2+M4]
 |      |
 |      +---> M9 (Watchdog)
 |
 +---> M10 (CI/CD + Deployment) [after all milestones]
```

Note: Milestones 7, 8, and 9 can proceed in parallel once their dependencies are met. Milestone 10 is the final integration milestone.
