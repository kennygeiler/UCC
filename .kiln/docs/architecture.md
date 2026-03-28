<!-- status: complete -->
# Architecture -- UCC Business Debt Lead Generation Platform

## System Overview

The UCC Lead Generation Platform is an automated pipeline that scrapes public UCC (Uniform Commercial Code) filings from ~45 US state Secretary of State websites, identifies businesses burdened by Merchant Cash Advance (MCA) debt, enriches them into actionable leads, enforces strict legal compliance, and exports qualified leads to GoHighLevel for campaign execution.

The system is 100% AI-managed with zero human developers. It is operated by a single non-technical manager via a monitoring dashboard.

---

## Component Map

The system consists of **seven pipeline stages**, a **dashboard**, a **self-healing agent**, and a **heartbeat watchdog**, deployed as **three independent Railway services** sharing a single Postgres database.

### Service 1: Pipeline Service

Contains the core data pipeline and dashboard API.

```
[Scheduler (APScheduler)]
    |
    v
[1. Scraper Engine] --> per-state scraper modules
    |                    (httpx for HTTP, Playwright for JS-rendered)
    v
[2. MCA Detector] --> alias matching engine
    |                  (known MCA lenders + shell companies)
    v
[3. Lead Scorer] --> position count, filing recency, collateral analysis
    |
    v
[4. Enrichment Pipeline] --> waterfall executor
    |                         (PDL -> Apollo -> OpenCorporates -> Whitepages -> Twilio)
    |                         circuit breaker (pybreaker) per source
    v
[5. Compliance Gate] --> sequential 4-layer check
    |                     (Internal DNC -> DataMerch -> DNC.com/CCC -> Blacklist Alliance)
    v
[6. Deduplicator] --> business name + filing number + cross-state fuzzy match
    |
    v
[7. Campaign Exporter] --> CampaignPlatformAdapter interface
    |                       (GHLAdapter: upsert + workflow enrollment)
    v
[GHL Webhook Receiver] --> disposition feedback -> lead recycling
    |
    v
[Dashboard API (FastAPI)] --> Jinja2 + HTMX templates
```

### Service 2: Self-Healing Agent

A LangGraph-based autonomous agent that monitors pipeline health and performs repairs.

```
[LangGraph Agent Loop]
    |
    +--> Read structured logs (structlog JSON from Service 1)
    +--> Read smoke test results (pytest-json-report)
    +--> Read Sentry error events
    |
    v
[Diagnosis Node] --> LLM analysis (Claude) of failure context
    |
    v
[Repair Node] --> generate fix, apply to staging branch, run tests
    |
    v
[Verification Node] --> pytest passes? merge to main : create GitHub issue
    |
    v
[Alert Node] --> SendGrid email to manager (plain English)
    |
    v
[Priority Queue] --> state_priority table (top 10 states = tier 1, repaired first)
    |
    v
[Heartbeat Writer] --> writes timestamp to Postgres every 60s
```

### Service 3: Heartbeat Watchdog

An independent deadman switch monitor with NO dependency on Service 1 or 2.

```
[Watchdog Loop (every 5 min)]
    |
    +--> Query heartbeat table: is agent heartbeat < 5 min old?
    +--> Query lead table: have new records been inserted in expected window?
    |
    v
[Alert Decision] --> if stale: SendGrid email directly to manager
```

---

## Data Flow

### Happy Path (Lead Lifecycle)

```
State SOS Portal
    --> [Scraper] raw UCC filing record
    --> [MCA Detector] confirmed MCA filing (matched to known lender/alias)
    --> [Scorer] scored lead (position count, recency, collateral type)
    --> [Enrichment] phone, email, revenue, owner name added
    --> [Compliance] passes all 4 gates
    --> [Deduplicator] unique lead confirmed
    --> [Exporter] pushed to GHL via API (upsert + workflow enrollment)
    --> [GHL] rep works the lead, updates disposition
    --> [Webhook] disposition synced back to pipeline DB
    --> [Recycler] eligible leads re-queued after cooldown
```

### Failure Paths

1. **Scraper failure**: Smoke test fails -> self-healing agent detects -> diagnoses via structured logs -> attempts repair -> creates GitHub issue with priority label -> emails manager.

2. **Enrichment failure**: Circuit breaker trips (>20% errors in 5 min) -> pipeline HALTS -> failed records queued in `enrichment_retry_queue` -> self-healing agent investigates -> pipeline resumes after source confirmed healthy.

3. **Compliance API failure**: Lead is BLOCKED (never exported) -> queued for retry -> alert sent.

4. **Self-healing agent failure**: Heartbeat goes stale -> watchdog detects (>5 min) -> emails manager directly.

5. **GHL API failure**: Exporter retries with exponential backoff -> falls back to CSV export queue for manual upload -> alert sent.

---

## Database Schema (Logical)

All tables in a single Railway Postgres 16+ instance.

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `ucc_filings` | Raw scraped filing records | filing_number, state, debtor_name, secured_party, filing_date, collateral_description, scraped_at |
| `leads` | Enriched, scored lead records | id, debtor_name, state, lead_score, mca_position_count, phone, email, owner_name, estimated_revenue, enrichment_status, compliance_status, export_status, ghl_contact_id, disposition, disposition_updated_at |
| `mca_aliases` | Known MCA lender names and shell companies | alias_name, canonical_lender_name, confidence, source, added_at |
| `enrichment_cache` | Permanent cache of all enrichment API results | source_api, input_key, result_json, fetched_at |
| `internal_dnc` | Permanent opt-out list (phone and email) | phone, email, source_channel, added_at, added_by |

### Compliance Tables

| Table | Purpose |
|-------|---------|
| `compliance_checks` | Audit log of every compliance check per lead (gate, result, checked_at) |

### Operations Tables

| Table | Purpose |
|-------|---------|
| `state_priority` | Per-state priority tier, leads_last_30_days, last_scrape_success, current_status |
| `scraper_runs` | Log of each scraper execution (state, started_at, finished_at, records_found, status, error_detail) |
| `job_queue` | Postgres-based job queue (job_type, payload, status, priority, scheduled_at, started_at, completed_at, retry_count, last_error) |
| `enrichment_retry_queue` | Failed enrichment records awaiting retry (lead_id, source, attempt_count, last_error, next_retry_at) |
| `agent_heartbeat` | Self-healing agent heartbeat (agent_id, last_seen, status) |
| `pipeline_events` | Event log for pipeline state changes (event_type, component, detail, created_at) |

### LangGraph Tables

| Table | Purpose |
|-------|---------|
| `langgraph_checkpoints` | LangGraph state persistence (managed by LangGraph Postgres checkpointer) |

---

## Module Structure

```
ucc-pipeline/
|-- app/
|   |-- __init__.py
|   |-- main.py                    # FastAPI app entry point
|   |-- config.py                  # pydantic-settings configuration
|   |-- db.py                      # SQLAlchemy engine + session factory
|   |-- models/                    # SQLAlchemy ORM models
|   |   |-- __init__.py
|   |   |-- filing.py              # UCC filing model
|   |   |-- lead.py                # Lead model
|   |   |-- mca_alias.py           # MCA alias model
|   |   |-- dnc.py                 # Internal DNC model
|   |   |-- job.py                 # Job queue model
|   |   |-- operations.py          # Scraper runs, heartbeat, events
|   |-- scrapers/
|   |   |-- __init__.py
|   |   |-- base.py                # Abstract base scraper
|   |   |-- registry.py            # State -> scraper class mapping
|   |   |-- states/                # Per-state scraper implementations
|   |   |   |-- california.py
|   |   |   |-- texas.py
|   |   |   |-- new_york.py
|   |   |   |-- florida.py
|   |   |   |-- ...                # One file per state
|   |   |-- rate_limiter.py        # Per-state rate limiting
|   |   |-- session_manager.py     # Cookie/ViewState session handling
|   |-- detection/
|   |   |-- __init__.py
|   |   |-- mca_detector.py        # MCA lender alias matching
|   |   |-- alias_updater.py       # Self-improving alias detection
|   |-- scoring/
|   |   |-- __init__.py
|   |   |-- scorer.py              # Lead scoring engine
|   |-- enrichment/
|   |   |-- __init__.py
|   |   |-- waterfall.py           # Generic waterfall executor
|   |   |-- sources/
|   |   |   |-- __init__.py
|   |   |   |-- pdl.py             # People Data Labs
|   |   |   |-- apollo.py          # Apollo.io
|   |   |   |-- opencorporates.py  # OpenCorporates
|   |   |   |-- whitepages.py      # Whitepages Pro
|   |   |   |-- twilio_lookup.py   # Twilio phone validation
|   |   |   |-- sos_officer.py     # SOS officer name scraping
|   |   |-- cache.py               # Enrichment result cache (Postgres)
|   |   |-- circuit_breaker.py     # pybreaker wrapper
|   |-- compliance/
|   |   |-- __init__.py
|   |   |-- gate.py                # 4-layer compliance gate orchestrator
|   |   |-- internal_dnc.py        # Internal DNC table operations
|   |   |-- datamerch.py           # DataMerch API client
|   |   |-- dnc_scrub.py           # DNC.com or CCC API client
|   |   |-- blacklist_alliance.py  # Blacklist Alliance API client
|   |-- dedup/
|   |   |-- __init__.py
|   |   |-- deduplicator.py        # Cross-state deduplication
|   |-- export/
|   |   |-- __init__.py
|   |   |-- adapter.py             # CampaignPlatformAdapter abstract interface
|   |   |-- ghl_adapter.py         # GHL API v2 concrete implementation
|   |   |-- csv_fallback.py        # CSV export fallback
|   |   |-- webhook_handler.py     # GHL webhook receiver (disposition feedback)
|   |-- recycling/
|   |   |-- __init__.py
|   |   |-- recycler.py            # Lead recycling based on disposition + cooldown
|   |-- dashboard/
|   |   |-- __init__.py
|   |   |-- routes.py              # Dashboard HTTP routes
|   |   |-- templates/             # Jinja2 HTML templates
|   |   |   |-- base.html
|   |   |   |-- index.html         # Main dashboard
|   |   |   |-- scraper_status.html
|   |   |   |-- lead_metrics.html
|   |   |   |-- compliance_stats.html
|   |   |   |-- alerts.html
|   |   |-- static/                # Tailwind CDN, Chart.js CDN references
|   |-- scheduler/
|   |   |-- __init__.py
|   |   |-- jobs.py                # APScheduler job definitions
|-- agent/
|   |-- __init__.py
|   |-- main.py                    # Self-healing agent entry point
|   |-- graph.py                   # LangGraph agent graph definition
|   |-- nodes/
|   |   |-- __init__.py
|   |   |-- detector.py            # Anomaly detection node
|   |   |-- diagnostician.py       # LLM-based diagnosis node
|   |   |-- repairer.py            # Code repair node
|   |   |-- verifier.py            # Test verification node
|   |   |-- alerter.py             # Email alert node
|   |   |-- issue_creator.py       # GitHub issue automation
|   |-- heartbeat.py               # Heartbeat writer (Postgres)
|-- watchdog/
|   |-- __init__.py
|   |-- main.py                    # Heartbeat watchdog entry point
|   |-- checker.py                 # Heartbeat staleness check
|   |-- alerter.py                 # Direct email alert (bypasses agent)
|-- migrations/                    # Alembic migration files
|   |-- alembic.ini
|   |-- env.py
|   |-- versions/
|-- tests/
|   |-- __init__.py
|   |-- unit/                      # Pure function tests
|   |-- integration/               # Database + API mock tests
|   |-- smoke/                     # Live SOS portal tests (scheduled)
|   |-- contract/                  # Enrichment API schema validation
|   |-- conftest.py                # Shared fixtures
|-- pyproject.toml                 # Project metadata + dependencies
|-- Procfile                       # Railway service definitions
|-- railway.toml                   # Railway configuration
```

---

## Deployment Model

### Railway Services

| Service | Entry Point | Health Check | Restart Policy |
|---------|-------------|-------------|----------------|
| `pipeline` | `app/main.py` | `GET /health` | `on-failure`, 3 retries |
| `agent` | `agent/main.py` | `GET /health` | `on-failure`, 3 retries |
| `watchdog` | `watchdog/main.py` | `GET /health` | `always` |

### Environment Variables (All Services)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Railway Postgres connection string |
| `GHL_API_KEY` | GoHighLevel API v2 bearer token |
| `GHL_LOCATION_ID` | GHL sub-account location ID |
| `GHL_WEBHOOK_SECRET` | Webhook payload verification |
| `GHL_WORKFLOW_TIER1` | GHL workflow ID for hot leads |
| `GHL_WORKFLOW_TIER2` | GHL workflow ID for warm leads |
| `GHL_WORKFLOW_TIER3` | GHL workflow ID for cold leads |
| `APOLLO_API_KEY` | Apollo.io API key |
| `PDL_API_KEY` | People Data Labs API key |
| `OPENCORPORATES_API_KEY` | OpenCorporates API key |
| `WHITEPAGES_API_KEY` | Whitepages Pro API key |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `DATAMERCH_API_KEY` | DataMerch API key (optional -- see C-15) |
| `DNC_SCRUB_API_KEY` | DNC.com or CCC API key |
| `BLACKLIST_API_KEY` | Blacklist Alliance API key |
| `ANTHROPIC_API_KEY` | Claude API for self-healing agent |
| `GITHUB_TOKEN` | GitHub PAT with repo scope |
| `GITHUB_REPO` | owner/repo-name |
| `SENDGRID_API_KEY` | SendGrid email API key |
| `MANAGER_EMAIL` | Manager's email for alerts |
| `SENTRY_DSN` | Sentry project DSN |

### CI/CD Pipeline

```
Push to GitHub
    --> GitHub Actions: pytest (unit + integration + contract)
    --> On main merge: Railway auto-deploy (all 3 services)
    --> Smoke tests run on schedule (daily, not on push)
```

---

## Key Architectural Patterns

### 1. Waterfall Executor
A generic function that accepts an ordered list of strategy callables. Tries each in order, returns the first success. Used by enrichment, compliance, and scraper fallback logic. Provides a single integration point for logging, metrics, and circuit breaker checks.

### 2. Circuit Breaker (pybreaker)
Wraps each enrichment API source. Opens after >20% failures in a 5-minute window. Open circuit triggers pipeline HALT event. Closed after self-healing agent confirms source recovery.

### 3. CampaignPlatformAdapter
Abstract interface isolating all campaign platform calls. GHLAdapter is the concrete implementation. Pipeline code imports only the abstract interface. Swapping platforms = one new adapter class.

### 4. Deadman Switch (Heartbeat Watchdog)
Self-healing agent writes heartbeat to Postgres every 60 seconds. Independent watchdog service checks for staleness every 5 minutes. Alert fires if heartbeat is >5 minutes old. Watchdog has `always` restart policy -- it never stops.

### 5. Postgres Job Queue
SELECT FOR UPDATE SKIP LOCKED pattern on a `job_queue` table. Jobs have priority, scheduled_at, and retry metadata. Workers poll the queue. Sufficient for daily-cadence pipeline at 10K leads/month.

### 6. Priority-Based Repair
`state_priority` table maps each state to a priority tier (recalculated nightly by lead volume). Self-healing agent processes repair queue sorted by tier. Top 10 MCA states (NY, CA, TX, FL, NJ, GA, IL, PA, OH, MD) are always tier 1.

---

## Security Boundaries

- All secrets stored as Railway environment variables, never in code or config files.
- GHL webhook payloads verified via webhook secret.
- GitHub token scoped to `repo` only.
- No public-facing endpoints except the webhook receiver and health checks.
- Dashboard access restricted via Railway private networking or basic auth at MVP.
- Internal DNC data is write-once (append-only), never exposed via API.
