---
title: "UCC Lead Generation Platform — Brownfield Architecture"
status: draft
created: 2026-05-19
updated: 2026-05-19
generated_by: bmad-document-project (Architect, applied manually)
audience: AI maintainers (Claude/agents), human reviewers
scan_level: full
---

# UCC Lead Generation Platform — Brownfield Architecture

## 1. Document Purpose

This document captures the **actual, as-built** architecture of the repository at `https://github.com/kennygeiler/UCC` (cloned commit `fa61a83`, `main` branch). It is written from a brownfield perspective: code in the tree is the source of truth, planning docs are corroborating evidence, and any gap between the two is called out as technical debt or a known incomplete deliverable.

It is intentionally written for an AI maintainer (Claude, future agents, the self-healing agent already inside this repo). Functions, modules, and tables are named explicitly so the agent does not need to re-derive structure from the tree.

## 2. Project Snapshot

| Field | Value |
|-------|-------|
| Repository | https://github.com/kennygeiler/UCC |
| Default branch | `main` |
| Cloned commit | `fa61a83 feat(dashboard): explainer modal and state coverage; dev UX fixes` |
| Project type | Multi-service backend pipeline (3 Railway services, 1 Postgres) |
| Primary language | Python 3.12+ |
| Total Python files (app+agent+watchdog) | 104 (~8,122 LoC) |
| Total Python test files | 51 (~3,197 LoC) |
| Public surface | FastAPI dashboard + GHL webhook receiver + 3 `/health` endpoints |
| Maintenance posture | Designed for **AI-only maintenance** (per C-01) |
| Production deploy target | Railway (NIXPACKS builder, `railway.toml`) |
| Database | Single Railway-managed PostgreSQL 16+ |
| Most recent planning artifacts | `.kiln/` (Kiln pipeline v0.98.3, run kiln-384252), `.planning/` |

## 3. Actual Tech Stack (with Versions Found in Code)

Sources: `pyproject.toml`, `Procfile`, `railway.toml`, `.github/workflows/ci.yml`, `docker-compose.yml`.

### Runtime

| Component | Version (floor) | Where pinned | Notes |
|-----------|-----------------|--------------|-------|
| Python | `>=3.12` | `pyproject.toml` `[project] requires-python` | CI matches via `actions/setup-python@v5` |
| FastAPI | `>=0.110.0` | `pyproject.toml` | Used by `app/main.py`, `agent/main.py`, `watchdog/main.py` |
| Uvicorn (standard) | `>=0.27.0` | `pyproject.toml` | Entry for all three services (Procfile) |
| SQLAlchemy (asyncio) | `>=2.0.0` | `pyproject.toml` | Async ORM; mapped via `Mapped[...]` 2.0 typed style |
| asyncpg | `>=0.29.0` | `pyproject.toml` | Driver behind `postgresql+asyncpg://` |
| Alembic | `>=1.13.0` | `pyproject.toml` | Migrations in `migrations/versions/` |
| pydantic-settings | `>=2.0.0` | `pyproject.toml` | `app/config.py` — single config surface |
| structlog | `>=23.0.0` | `pyproject.toml` | JSON logs via `app/logging.py`, `watchdog/logging_config.py` |
| sentry-sdk | `>=2.0.0` | `pyproject.toml` | Initialized in all three service entrypoints |
| APScheduler | `>=3.10.0` | `pyproject.toml` | `app/scrapers/scheduler.py` (AsyncIOScheduler) |
| httpx | `>=0.27.0` | `pyproject.toml` | Scrapers, compliance APIs, GHL adapter, watchdog SendGrid |
| pybreaker | `>=1.0.0` | `pyproject.toml` | `app/enrichment/circuit_breaker.py` |
| Jinja2 | `>=3.1.0` | `pyproject.toml` | Dashboard templates |
| python-multipart | `>=0.0.6` | `pyproject.toml` | CSV upload on `/dashboard/upload-tiers` |
| langgraph | `>=0.2.0` | `pyproject.toml` | `agent/graph.py` |
| anthropic | `>=0.30.0` | `pyproject.toml` | Claude calls in `diagnose` node |
| sendgrid | `>=6.10.0` | `pyproject.toml` | Agent + watchdog (REST via httpx — package present for typing/future use) |
| PyGithub | `>=2.0.0` | `pyproject.toml` | Agent repair/PR loop |
| playwright | `>=1.40.0` | `pyproject.toml` | `app/scrapers/playwright_base.py` (base only; no Tier 1 implementations yet) |
| beautifulsoup4 | `>=4.12.0` | `pyproject.toml` | `app/scrapers/parsers.py` |
| twilio | `>=9.0.0` | `pyproject.toml` | Phone validation (config keys wired; pipeline usage minimal) |
| rapidfuzz | `>=3.6.0` | `pyproject.toml` | MCA fuzzy alias matching |

### Dev

| Component | Version (floor) | Notes |
|-----------|-----------------|-------|
| pytest | `>=8.0.0` | `tool.pytest.ini_options` with `asyncio_mode = "auto"` |
| pytest-asyncio | `>=0.23.0` | Auto async mode |
| pytest-cov | `>=4.0.0` | Coverage |

### Infra

| Component | Version | Source |
|-----------|---------|--------|
| PostgreSQL | 16 | `.github/workflows/ci.yml` (`postgres:16`), `docker-compose.yml` (`postgres:16-alpine`), Railway plugin |
| Railway builder | NIXPACKS | `railway.toml` `[build] builder = "NIXPACKS"` |
| GitHub Actions Python | 3.12 | `.github/workflows/ci.yml` |

### Reproducibility note

There is **no lockfile** (no `requirements.txt`, no `poetry.lock`, no `uv.lock`). Reproducibility relies on `pyproject.toml` lower bounds. README explicitly calls this out. See §11 Technical Debt.

## 4. Repository Layout (Actual)

```
UCC/
├── app/                          # Pipeline service (FastAPI) — main.py + 9 subpackages
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, Sentry init, scheduler lifespan, /health, / (redirect)
│   ├── config.py                 # pydantic-settings Settings class — single env surface
│   ├── db.py                     # async engine, async_sessionmaker, get_session ctx mgr
│   ├── logging.py                # configure_logging() + get_logger() (structlog JSON)
│   ├── models/                   # SQLAlchemy 2.0 typed ORM models (13 tables)
│   │   ├── base.py               # Base, TimestampMixin
│   │   ├── filing.py             # ucc_filings
│   │   ├── lead.py               # leads (with mca_position_count, mca_tier, source_filing_id)
│   │   ├── mca_alias.py          # mca_aliases
│   │   ├── dnc.py                # internal_dnc, dnc_reversal_audit, enrichment_cache, compliance_checks
│   │   ├── job.py                # job_queue, enrichment_retry_queue
│   │   └── operations.py         # state_priority, scraper_runs, agent_heartbeat, pipeline_events, langgraph_checkpoints
│   ├── scrapers/                 # Scraping subsystem (M2)
│   │   ├── base.py               # BaseScraper ABC with ScraperRun lifecycle, httpx fetch, dedup persist
│   │   ├── playwright_base.py    # Playwright base (Chromium) — present, not used by tier-1 yet
│   │   ├── registry.py           # SCRAPER_REGISTRY: {state_code -> {class, tier}}; schedulable_state_codes(), get_states_by_tier()
│   │   ├── scheduler.py          # APScheduler AsyncIOScheduler; tier 1=24h, tier 2=36h, tier 3=48h; alias updater + enrichment retry jobs
│   │   ├── rate_limiter.py       # Per-state delay + jitter + backoff; tier-3 floor=10s; proxy rotation cycle from PROXY_URL csv
│   │   ├── parsers.py            # BS4 HTML table → filing dicts helpers
│   │   ├── user_agents.py        # get_random_user_agent()
│   │   └── states/               # 40 state scrapers + tier4_stubs.py
│   │       ├── california.py     # 7.5K (custom JSON search, lookback window)
│   │       ├── texas.py          # 12.7K (largest; bespoke search)
│   │       ├── new_jersey.py     # 9.5K
│   │       ├── new_york.py       # 8.4K
│   │       ├── florida.py        # 4.2K
│   │       ├── … 35 other states (~1.3K each, table-driven)
│   │       └── tier4_stubs.py    # DistrictColumbiaStubScraper, NewYorkCityStubScraper (skip-at-MVP)
│   ├── mca/                      # MCA detection + scoring (M3)
│   │   ├── detector.py           # detect_mca: exact → fuzzy (rapidfuzz WRatio) → shell → collateral keywords
│   │   ├── scorer.py             # count_positions, recency_boost, assign_tier (hot/warm/cold), compute_score
│   │   ├── pipeline.py           # Wires filings → detector → scorer → leads write
│   │   ├── alias_updater.py      # Nightly alias updater (run_alias_update_job)
│   │   └── seed_data.py          # SHELL_COMPANY_PATTERNS, MCA_COLLATERAL_KEYWORDS, seed lender list
│   ├── enrichment/               # Enrichment pipeline (M4)
│   │   ├── waterfall.py          # WaterfallExecutor (generic ordered-strategy), WaterfallExhaustedError
│   │   ├── sources.py            # enrich_pdl, enrich_apollo, enrich_opencorporates (+ stubs for whitepages/twilio/sos_officer)
│   │   ├── cache.py              # ENRICHMENT_CACHE_SOURCE, enrichment_cache_key, get_cached, store_cached (Postgres, no TTL)
│   │   ├── circuit_breaker.py    # BREAKERS dict, is_any_breaker_open (pybreaker, C-03)
│   │   ├── rate_tracker.py       # Rolling failure-rate tracker (window seconds + threshold from Settings)
│   │   ├── backoff.py            # next_backoff_seconds (1h, 4h, 24h, 72h)
│   │   ├── normalize.py          # normalize_vendor_response, enrichment_meets_bar (completeness check, ENRICH-06)
│   │   ├── retry_worker.py       # run_enrichment_retry_job (APScheduler-driven)
│   │   └── pipeline.py           # Orchestration: get_pending_leads → enrich_lead → check_pipeline_halt → HALT pipeline_events row
│   ├── compliance/               # 4-layer compliance gate (M5, C-02)
│   │   ├── gate.py               # run_compliance_gate; layers in order: internal_dnc → datamerch → dnc_scrub → blacklist_alliance
│   │   ├── internal_dnc.py       # Append-only ops + reverse_dnc_block (audit row)
│   │   ├── export_guard.py       # require_compliance_cleared(lead_data) raised at adapter boundary
│   │   └── exceptions.py         # ComplianceNotClearedError, etc.
│   ├── dedup/                    # Cross-state dedup — currently inlined into pipeline.py and export/dedup.py
│   ├── export/                   # Campaign export (M6)
│   │   ├── adapter.py            # CampaignPlatformAdapter ABC (C-06)
│   │   ├── ghl_adapter.py        # Concrete GHL API v2 adapter; require_compliance_cleared in upsert_lead
│   │   ├── csv_fallback.py       # CSVFallbackAdapter
│   │   ├── dedup.py              # Export-time dedup helpers
│   │   ├── recycler.py           # Disposition-based recycler with cooldown
│   │   └── webhook.py            # FastAPI router for GHL webhooks (mounted in app/main.py)
│   ├── dashboard/                # Manager dashboard (M7, C-11)
│   │   ├── routes.py             # /dashboard/, /scrapers, /state-coverage, /leads, /alerts, POST /upload-tiers
│   │   ├── queries.py            # get_dashboard_stats, get_recent_alerts, get_scraper_status, get_state_filing_lead_stats
│   │   └── templates/            # Jinja2: dashboard.html + partials/
│   └── services/
│       └── job_queue.py          # SELECT FOR UPDATE SKIP LOCKED claim/complete (ADR-010)
│
├── agent/                        # Self-healing agent service (M8)
│   ├── main.py                   # FastAPI shell; _agent_loop() every 5 min; heartbeat_loop()
│   ├── graph.py                  # LangGraph StateGraph: detect → diagnose → repair → verify → alert
│   └── heartbeat.py              # Writes agent_heartbeat row every 60 s
│
├── watchdog/                     # Heartbeat watchdog service (M9, C-07: zero app/agent imports)
│   ├── main.py                   # FastAPI shell + /health
│   ├── monitor.py                # check_heartbeat, check_lead_flow (business-hours gated), send_alert (SendGrid via httpx)
│   └── logging_config.py         # Separate structlog config — no app.logging import
│
├── migrations/                   # Alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py        # 13-table initial schema
│       ├── 002_lead_mca_identity.py     # adds debtor_name_normalized, mca_tier, source_filing_id to leads
│       └── 003_dnc_reversal_audit.py    # dnc_reversal_audit table for C-12
│
├── tests/
│   ├── conftest.py                      # Forces SCRAPER_SCHEDULER_ENABLED=false, MCA_ALIAS_UPDATE_ENABLED=false, ENRICH_RETRY_JOB_ENABLED=false
│   ├── unit/                            # 30 unit test files (config, models, scorer, detector, waterfall, gate, dashboard, scrapers, scheduler, watchdog…)
│   ├── integration/                     # E2E pipeline, scraper persist, job-queue concurrency, MCA pipeline, alias updater integration, db_postgres
│   ├── smoke/                           # tests/smoke/test_scraper_smoke.py (slow-marked)
│   ├── contract/                        # Enrichment vendor response shape contracts
│   └── fixtures/
│
├── scripts/
│   ├── dashboard_local.py               # 48 K — local dashboard runner with seeded data
│   ├── e2e_local.py                     # 15 K — local end-to-end runner
│   ├── setup_local.sh                   # venv + alembic upgrade head
│   └── deploy_railway.sh                # Railway init + plugin + env var + deploy
│
├── .github/workflows/
│   ├── ci.yml                           # pytest -m "not slow" with postgres:16 service on push/PR
│   └── scraper-smokes-scheduled.yml     # Daily 06:00 UTC + manual; slow scraper smokes
│
├── .kiln/                               # Kiln pipeline planning artifacts (v0.98.3, complete)
│   ├── master-plan.md, REPORT.md, STATE.md, resume.md
│   └── docs/ (architecture, tech-stack, arch-constraints, decisions, patterns, pitfalls, research, VISION, codebase-state, deployment)
│
├── .planning/                           # GSD-style planning artifacts (PROJECT, REQUIREMENTS, ROADMAP, STATE, codebase, phases)
│
├── .cursor/                             # IDE config (settings, plans)
├── _bmad/, .agents/, {output_folder}/   # ← Created by `bmad install` during this analysis run
│
├── docs/                                # ← NEW: this brief + this architecture doc
│   ├── brief.md
│   └── brownfield-architecture.md       # (this file)
│
├── AGENTS.md                            # Onboarding for agent maintainers (architecture TL;DR, conventions, constraints)
├── README.md                            # Operator-facing setup + CI parity + health endpoints
├── DEPLOY.md                            # Railway deployment guide (script and manual)
├── MEMORY.md
├── alembic.ini
├── docker-compose.yml                   # Local Postgres 16-alpine
├── pyproject.toml                       # Single source of dep + pytest config
├── railway.toml                         # Multi-service Railway config
├── Procfile                             # web, agent, watchdog
├── package-lock.json                    # 82 B — empty/placeholder, unused (no JS toolchain, C-14)
├── settings.local.json                  # Local IDE/agent settings
└── .env.example                         # Full env-var reference with notes
```

## 5. Services and Deployment Topology

Three independent Railway services share one Postgres instance.

| Service | Entrypoint | Start command (Procfile / railway.toml) | Restart policy | Healthcheck | Default port |
|---------|------------|-----------------------------------------|----------------|-------------|--------------|
| `pipeline` (web) | `app.main:app` (FastAPI) | `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` | `ON_FAILURE` (10 retries) | `GET /health` (300s timeout) | 8000 |
| `agent` | `agent.main:app` (FastAPI shell) | `uvicorn agent.main:app --host 0.0.0.0 --port ${PORT:-8001}` | `ON_FAILURE` (10 retries) | `GET /health` | 8001 |
| `watchdog` | `watchdog.main:app` (FastAPI shell) | `uvicorn watchdog.main:app --host 0.0.0.0 --port ${PORT:-8002}` | `ALWAYS` (0 max retries → never give up) | `GET /health` | 8002 |

Notes:

- **Healthcheck semantics**: pipeline and agent return HTTP 200 always, using `status: "ok"` vs `"degraded"` in the JSON body to signal DB connectivity. This is deliberate (`app/main.py` comment: "Non-200 is not used for database outages so Railway liveness does not thrash on transient DB issues"). Watchdog `/health` includes a `monitor` field signaling the monitoring loop is scheduled.
- **Service isolation (C-07)**: `watchdog/monitor.py` reads env vars directly (`os.environ.get(...)`) and uses a hand-rolled `_make_url()` to coerce `postgres://` → `postgresql+asyncpg://`. It never imports `app.config` or anything from `app/` or `agent/`. Verified by inspection of `watchdog/` directory.
- **Lifespan** (`app/main.py`): on startup, when `SCRAPER_SCHEDULER_ENABLED` is true, creates `AsyncIOScheduler` from `app.scrapers.scheduler.create_scheduler()`. On shutdown, calls `scheduler.shutdown(wait=True)` then `dispose_engine()`. Tests override the env to keep schedulers quiet.
- **Agent lifespan** (`agent/main.py`): spawns two background asyncio tasks — `_agent_loop()` (5-min `run_agent_cycle()`) and `heartbeat.heartbeat_loop()` (60-s `agent_heartbeat` row update).

## 6. Data Model

Database is a single Railway Postgres 16+ instance. All 13 tables ship in `migrations/versions/001_initial_schema.py`, with two later migrations:

- `002_lead_mca_identity.py` — adds `debtor_name_normalized`, `mca_tier`, `source_filing_id` (unique FK) to `leads`
- `003_dnc_reversal_audit.py` — adds `dnc_reversal_audit` table for C-12

### 6.1 Table summary

| Table | Defined in (model) | Purpose | Key columns / indexes |
|-------|--------------------|---------|-----------------------|
| `ucc_filings` | `app/models/filing.py` (`UCCFiling`) | Raw scraped UCC filings | `filing_number`, `state`, `debtor_name`, `secured_party`, `filing_date`, `collateral_description`, `scraped_at`; ixs on `filing_number`, `state` |
| `leads` | `app/models/lead.py` (`Lead`) | Scored + enriched leads | `debtor_name`, `debtor_name_normalized`, `state`, `lead_score`, `mca_position_count`, `mca_tier`, `source_filing_id` (FK→ucc_filings.id, unique), `phone`, `email`, `owner_name`, `estimated_revenue`, `enrichment_status`, `compliance_status`, `export_status`, `ghl_contact_id`, `disposition`, `disposition_updated_at`; ixs on `state`, `enrichment_status`, `compliance_status`, `export_status` |
| `mca_aliases` | `app/models/mca_alias.py` (`MCAlias`) | Known MCA lender names + shell aliases | `alias_name`, `canonical_lender_name`, `confidence`, `source`, `added_at` |
| `internal_dnc` | `app/models/dnc.py` (`InternalDNC`) | Permanent opt-out list (phone + email) | `phone`, `email`, `source_channel`, `added_at`, `added_by`, `is_active` (default true) — **append-only, C-12** |
| `dnc_reversal_audit` | `app/models/dnc.py` (`DncReversalAudit`) | Audit trail for manager-only DNC reversals | `internal_dnc_id` (FK), `reversed_by`, `reason`, `reversed_at`; ix on `internal_dnc_id` |
| `enrichment_cache` | `app/models/dnc.py` (`EnrichmentCache`) | Permanent cache of vendor responses (C-08) | `source_api`, `input_key`, `result_json` (JSONB), `fetched_at`; ix on (`source_api`, `input_key`) |
| `compliance_checks` | `app/models/dnc.py` (`ComplianceCheck`) | Audit log per lead per gate | `lead_id` (FK→leads.id), `gate_name`, `result`, `checked_at`; ix on `lead_id` |
| `job_queue` | `app/models/job.py` (`JobQueue`) | Postgres job queue (ADR-010) | `job_type`, `payload` (JSONB), `status`, `priority`, `scheduled_at`, `started_at`, `completed_at`, `retry_count`, `last_error`; ixs on `status`, `scheduled_at`, `priority` |
| `enrichment_retry_queue` | `app/models/job.py` (`EnrichmentRetryQueue`) | Failed enrichments awaiting retry | `lead_id` (FK→leads.id), `source`, `attempt_count`, `last_error`, `next_retry_at`; ix on `lead_id` |
| `state_priority` | `app/models/operations.py` (`StatePriority`) | Per-state tier + recent lead volume | `state` (unique), `tier`, `leads_last_30_days`, `last_scrape_success`, `current_status` |
| `scraper_runs` | `app/models/operations.py` (`ScraperRun`) | Log per scraper execution | `state`, `started_at`, `finished_at`, `records_found`, `status`, `error_detail`; ix on `state` |
| `agent_heartbeat` | `app/models/operations.py` (`AgentHeartbeat`) | Self-healing agent heartbeat | `agent_id` (unique), `last_seen`, `status` |
| `pipeline_events` | `app/models/operations.py` (`PipelineEvent`) | Pipeline state changes (e.g. HALT) | `event_type`, `component`, `detail`, `created_at`; ix on `event_type` |
| `langgraph_checkpoints` | `app/models/operations.py` (`LanggraphCheckpoint`) | Minimal LangGraph checkpoint table | `thread_id`, `checkpoint` (JSONB), `metadata` (JSONB), `created_at`; ix on `thread_id` |

### 6.2 Notable model-level patterns

- **Typed 2.0 ORM**: All models use `Mapped[T] = mapped_column(...)` with `nullable=True/False` explicit and `default=...` for app-level defaults and `server_default=...` for DB-side defaults.
- **`TimestampMixin`** in `app/models/base.py` provides `created_at` / `updated_at` (`server_default = now()`).
- **JSONB**: used for `payload`, `result_json`, `checkpoint`, `metadata`.
- **No ORM relationships** between `Lead` ↔ `UCCFiling` are declared beyond a `ForeignKey` on `source_filing_id`. Joins are done explicitly via `select(...)` to keep functions short and the SQL legible to AI maintainers.
- **`Lead.source_filing_id`** is `unique=True` (one lead per source filing). Cross-state dedup happens above this layer.

## 7. Pipeline Data Flow (Actual Code Paths)

```
[SOS portal] --> BaseScraper.scrape() --> ucc_filings
                                            |
                                            v
                                  MCA pipeline (app/mca/pipeline.py)
                                            |
                                            v
                       detect_mca() [exact/fuzzy/shell/collateral] -> score_lead() -> leads (enrichment_status='pending')
                                                                                      |
                                                                                      v
                                                       run_enrichment_pipeline(batch_size=50)
                                                       check_pipeline_halt() [breakers + rate_tracker.halted]
                                                       cache hit -> apply / cache miss -> WaterfallExecutor (pdl -> apollo -> opencorporates)
                                                                                      |
                                                                                      v
                                                          normalize_vendor_response + enrichment_meets_bar
                                                          enrichment_status: 'complete' | 'incomplete' | 'retry_queued'
                                                                                      |
                                                                                      v
                                                          run_compliance_gate(lead) [4 layers sequential]
                                                          internal_dnc -> datamerch -> dnc_scrub -> blacklist_alliance
                                                          ANY blocked -> Lead.compliance_status = 'blocked:<gate>' (permanent)
                                                          all pass -> Lead.compliance_status = 'cleared'
                                                                                      |
                                                                                      v
                                                          export/dedup -> GHLAdapter.upsert_lead() (require_compliance_cleared) -> enroll_in_campaign
                                                                                      |
                                                                                      v
                                                          GHL webhook --> app/export/webhook.py --> disposition --> Lead row
                                                                                      |
                                                                                      v
                                                          app/export/recycler.py -> requeue eligible leads after cooldown
```

Background to this flow:

- **APScheduler** (`app/scrapers/scheduler.py`) runs scraping jobs (`run_scraper` per state, on `IntervalTrigger` per tier). It also schedules `run_alias_update_job` and `run_enrichment_retry_job` when those settings are enabled.
- **HALT logic** (`app/enrichment/pipeline.py::check_pipeline_halt`) writes a `pipeline_events` row with `event_type='HALT'` exactly once per HALT (module-level `_halt_event_logged` flag; reset for tests by `reset_halt_logging_for_tests()`).
- **Adapter boundary** (`app/export/ghl_adapter.py`) calls `require_compliance_cleared(lead_data)` at the top of `upsert_lead`. Pipeline code imports only `app.export.adapter` (verified by AGENTS.md convention and inspection).

## 8. Self-Healing Agent (`agent/`)

### Graph

`agent/graph.py` defines an `AgentState` TypedDict and a LangGraph `StateGraph` with the cyclical structure:

```
START -> detect -> diagnose -> repair -> verify -> alert -> END
                                  ^____________________| (retry on transient verify failure)
```

| Node | Reads | Writes / Side effects |
|------|-------|-----------------------|
| `detect` | `scraper_runs` (failed), `pipeline_events` (HALT) | Builds `anomalies` list sorted by priority |
| `diagnose` | `anomalies[:10]`, Claude (Anthropic API) | Sets `diagnosis` string (plain English, C-11) |
| `repair` | `diagnosis`, GitHub (PyGithub) | Opens branch + PR via GitHub API |
| `verify` | GitHub CI status | Sets `ci_passed`; on pass → merge; on fail → file issue with `priority-*` label |
| `alert` | `diagnosis`, `MANAGER_EMAIL` | SendGrid email (rate-limited per failure fingerprint) |

Constants: `MAX_DETECT_RETRIES = 3`, agent loop interval `AGENT_INTERVAL_SECONDS = 300` (5 min) in `agent/main.py`.

### Checkpointing

A `langgraph_checkpoints` table exists (`app/models/operations.py::LanggraphCheckpoint`) and is shaped to accept a Postgres checkpointer. The compiled graph in `agent/graph.py` references `BaseCheckpointSaver`. The exact wiring of the saver instance is in `agent/graph.py` (~530 lines total — most logic is in the four node bodies).

### Heartbeat

`agent/heartbeat.py` writes a row to `agent_heartbeat` every 60 seconds (`agent_id = 'self-healing'`). This is what `watchdog/monitor.py::check_heartbeat()` queries.

## 9. Heartbeat Watchdog (`watchdog/`)

### Isolation (C-07)

- Reads `DATABASE_URL`, `SENDGRID_API_KEY`, `MANAGER_EMAIL`, `SENTRY_DSN` directly from `os.environ.get(...)`.
- Has its own `_make_url` URL coercer (does not import `app.db._make_url`).
- Uses its own `watchdog/logging_config.py`.

### Loop

`watchdog/monitor.py::run_watchdog_loop` runs every `CHECK_INTERVAL_SECONDS = 300` (5 min):

1. `check_heartbeat()` — selects `last_seen` from `agent_heartbeat WHERE agent_id='self-healing'`; stale = older than `HEARTBEAT_STALE_MINUTES = 5`.
2. If stale → `send_alert("Self-Healing Agent Down", ...)`. Alert deduplicated by `ALERT_COOLDOWN_MINUTES = 60`.
3. If stale **and** within business hours (M–F, 8 AM–6 PM ET — `_is_business_hours()`) → `check_lead_flow()` (counts `leads.created_at` within `LEAD_FLOW_WINDOW_MINUTES = 30`). If zero, send second alert.

### Alerting

Direct HTTPS POST to `https://api.sendgrid.com/v3/mail/send` via `httpx`. The `sendgrid` package is declared in `pyproject.toml` but watchdog hits the REST endpoint directly (acceptable; less dep surface to wedge during alerts).

## 10. External Integrations and Adapters

| Integration | Where | Notes |
|-------------|-------|-------|
| GoHighLevel API v2 | `app/export/ghl_adapter.py` | Base URL `https://services.leadconnectorhq.com`. Adds `Version: 2021-07-28` header. Workflow IDs from `GHL_WORKFLOW_TIER1/2/3`. Eight custom fields expected pre-created (C-13). |
| GoHighLevel webhooks | `app/export/webhook.py` | FastAPI router mounted on pipeline service. Verifies via `GHL_WEBHOOK_SECRET`. |
| People Data Labs | `app/enrichment/sources.py::enrich_pdl` | Primary enrichment layer 1 |
| Apollo.io | `app/enrichment/sources.py::enrich_apollo` | Enrichment layer 2 |
| OpenCorporates | `app/enrichment/sources.py::enrich_opencorporates` | Enrichment layer 3 |
| Whitepages / Twilio Lookup | Configured in env; not in the active waterfall today | Future enrichment layers |
| DataMerch | `app/compliance/gate.py::check_datamerch` | `GET https://api.datamerch.com/v1/check?name=...`. **Fail-open by default**; `COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH=true` flips to fail-closed (C-15). |
| DNC.com / CCC | `app/compliance/gate.py::check_dnc_scrub` | `GET https://api.dnc.com/v1/check?phone=...`. Skips with warning when key unset. |
| Blacklist Alliance | `app/compliance/gate.py::check_blacklist_alliance` | `GET https://api.blacklistalliance.com/v1/lookup?phone=...`. |
| Anthropic Claude | `agent/graph.py::diagnose` | Plain-English diagnosis input for alerts |
| GitHub | `agent/graph.py::repair`, `verify` | PyGithub; branch + PR + CI status read |
| SendGrid | `agent` alerts + `watchdog/monitor.py` | Direct HTTPS via httpx |
| Sentry | All three services | Initialized only when `SENTRY_DSN` is set (so local dev runs without it) |

## 11. Build, Test, and CI

### Build

- No build step. NIXPACKS on Railway autodetects Python from `pyproject.toml`, installs editable mode + deps. Local: `python3.12 -m venv .venv && pip install -e ".[dev]"`.
- Playwright browsers are **not** installed by default in CI (per README: "scheduled smokes may add it when needed"). Playwright-based scrapers therefore require an extra step in any production image: `playwright install chromium`.

### Test

- `pyproject.toml` `[tool.pytest.ini_options]` sets `asyncio_mode = "auto"` and registers markers: `integration`, `slow`, `smoke`.
- `tests/conftest.py` forces `SCRAPER_SCHEDULER_ENABLED=false`, `MCA_ALIAS_UPDATE_ENABLED=false`, `ENRICH_RETRY_JOB_ENABLED=false` so background jobs do not fire under pytest.
- Default invocation: `pytest -m "not slow"` (per CI). Slow scraper smokes run on a separate scheduled workflow.

### CI workflows

| Workflow | File | Trigger | What it does |
|----------|------|---------|--------------|
| `CI` | `.github/workflows/ci.yml` | push & PR to `main`/`master` | Spins up `postgres:16` service container; `DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test_ucc`; `SENTRY_DSN` placeholder; `pip install -e ".[dev]"`; `alembic upgrade head`; `pytest -x -v -m "not slow"` |
| `Scraper smokes (scheduled)` | `.github/workflows/scraper-smokes-scheduled.yml` | cron `0 6 * * *` + `workflow_dispatch` | Long-running slow smokes (`pytest -m slow`); optional `PROXY_URL` secret for Tier-3 portals |

### Local dev assists

- `docker-compose.yml` provides a `postgres:16-alpine` instance for local dev/tests (`ucc:ucc_local@localhost:5432/ucc_dev`, `pg_isready` healthcheck, named volume).
- `scripts/setup_local.sh` — venv + editable install + alembic upgrade head bootstrap.
- `scripts/dashboard_local.py` (48 K) — boots the dashboard with seeded data.
- `scripts/e2e_local.py` (15 K) — local end-to-end pipeline run.
- `scripts/deploy_railway.sh` — non-interactive(ish) Railway deploy helper.

## 12. Configuration Surface

Single source: `app/config.py::Settings` (pydantic-settings). Loaded from environment and `.env`. **Required**: `DATABASE_URL`. Everything else is optional with sensible defaults — the system fails open in dev (e.g. compliance APIs log a warning and skip).

| Variable | Default | Used by |
|----------|---------|---------|
| `DATABASE_URL` | — (required) | All services (asyncpg coerced) |
| `SENTRY_DSN` | `None` | All three services (skips init when unset) |
| `GHL_API_KEY`, `GHL_LOCATION_ID`, `GHL_WEBHOOK_SECRET`, `GHL_WORKFLOW_TIER1/2/3` | `None` | `app/export/ghl_adapter.py`, `app/export/webhook.py` |
| `APOLLO_API_KEY`, `PDL_API_KEY`, `OPENCORPORATES_API_KEY`, `WHITEPAGES_API_KEY` | `None` | `app/enrichment/sources.py` |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | `None` | Phone validation (wired, light usage) |
| `DATAMERCH_API_KEY` | `None` | `check_datamerch` |
| `COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH` | `False` | `check_datamerch` toggles fail-closed (C-15) |
| `DNC_SCRUB_API_KEY` | `None` | `check_dnc_scrub` |
| `BLACKLIST_API_KEY` | `None` | `check_blacklist_alliance` |
| `PROXY_URL` | `None` | `RateLimiter` (CSV list → `itertools.cycle`) — Tier 3 only |
| `SCRAPER_SCHEDULER_ENABLED` | `True` | `app/main.py` lifespan; tests force false |
| `SCRAPER_FILING_LOOKBACK_DAYS` | `3` | CA JSON search window |
| `MCA_FUZZY_MIN_ALIAS_LEN` | `5` | `detector._fuzzy_match_alias` |
| `MCA_FUZZY_SCORE_CUTOFF` | `85` | `detector._fuzzy_match_alias` (rapidfuzz WRatio) |
| `MCA_ALIAS_UPDATE_ENABLED` | `True` | Scheduler; tests force false |
| `MCA_ALIAS_UPDATE_INTERVAL_HOURS` | `24` | Scheduler |
| `ENRICH_BREAKER_ERROR_WINDOW_SECONDS` | `300` | `rate_tracker.RollingRateTracker` |
| `ENRICH_BREAKER_ERROR_RATE_THRESHOLD` | `0.2` | rate tracker (C-03) |
| `ENRICH_RATE_MIN_ATTEMPTS_BEFORE_HALT` | `5` | rate tracker |
| `ENRICH_RETRY_JOB_ENABLED` | `True` | Scheduler; tests force false |
| `ENRICH_RETRY_INTERVAL_MINUTES` | `60` | Scheduler |
| `ANTHROPIC_API_KEY` | `None` | `agent/graph.py::diagnose` |
| `GITHUB_TOKEN`, `GITHUB_REPO` | `None` | `agent/graph.py::repair`/`verify` |
| `SENDGRID_API_KEY`, `MANAGER_EMAIL` | `None` | Agent alerter + watchdog alerter |

Conversion: `app/db.py::_make_url` and `watchdog/monitor.py::_make_url` both coerce `postgres://` and `postgresql://` URLs to `postgresql+asyncpg://`.

## 13. Source-Tree Hot Spots (Where Work Actually Happens)

For an AI maintainer landing in this repo, the highest-edit-frequency / highest-risk files are:

1. **`app/scrapers/states/*.py`** — 40 state scrapers. Most are small (~1.3 KB), driven by `column_map` + `build_search_url` + `parse_response`. The five large ones (`texas.py` 12.7 KB, `new_jersey.py` 9.5 KB, `new_york.py` 8.4 KB, `california.py` 7.5 KB, `florida.py` 4.2 KB) are bespoke. Expect parser drift here first.
2. **`app/compliance/gate.py`** — Legal-critical. Read-once before modifying. Negative tests guard against bypass paths.
3. **`agent/graph.py`** — 530 lines, the largest single file. Most of the agent's behavior lives in the four node bodies (detect/diagnose/repair/verify).
4. **`app/enrichment/pipeline.py`** — HALT semantics + cache + retry queue interplay. Subtle.
5. **`app/export/ghl_adapter.py`** — Vendor-specific shape. Behind the adapter boundary, so changes don't ripple — but `require_compliance_cleared` must remain at the top of `upsert_lead`.

## 14. Conventions and Invariants (Enforced by Code or by AGENTS.md)

- **Function size**: <50 lines, single-purpose, docstring (C-01). Verifiable mechanically.
- **Snake_case** for all Python files and functions; one file per state scraper.
- **No metaprogramming, no dynamic imports.** `app/scrapers/registry.py` uses explicit imports + a literal `SCRAPER_REGISTRY` dict.
- **All config via `app.config`** — never raw `os.environ` (single exception: watchdog, which must not import app).
- **Structured log fields required**: `component`, `status`, `error_type`, `context` on every meaningful state change.
- **Pipeline code imports only `app.export.adapter`** (the abstract). Never `app.export.ghl_adapter`. (C-06; AGENTS.md states this as a hard rule.)
- **Watchdog has zero `app/` or `agent/` imports.** (C-07; verifiable via grep.)
- **Internal DNC append-only**, reversal via `reverse_dnc_block` row. (C-12.)
- **Enrichment cache has no TTL.** (C-08.)
- **Job queue uses `SELECT FOR UPDATE SKIP LOCKED`.** (`app/services/job_queue.py`.)

## 15. Technical Debt and Known Gaps

Observed in the as-built code, beyond the planning docs:

1. **No lockfile.** Reproducibility is "lower bounds only" via `pyproject.toml`. A `requirements.lock`, `uv.lock`, or `poetry.lock` would close a meaningful supply-chain gap. README acknowledges this.
2. **`package-lock.json` (82 B) committed.** Vestigial; there is no JS toolchain (C-14). Safe to delete; left in place to avoid touching anything unprompted.
3. **`{output_folder}` directory created by BMAD install.** During this analysis, `bmad install` left a literal `{output_folder}/` directory in the repo root (template substitution that didn't resolve cleanly in this BMAD version). It's harmless but ugly; cleanup is recommended before committing.
4. **`_bmad/`, `.agents/`, `_bmad/_config/`** were also created by the BMAD install. They contain the BMAD skill catalog for Cursor and are useful going forward, but they were generated *during this analysis*, not by the project author — flag for the operator to decide whether to commit.
5. **Playwright base exists but no Tier-1 scrapers use it.** `app/scrapers/playwright_base.py` is present (3.5 K) and `tests/unit/test_playwright_base.py` exists, but `SCRAPER_REGISTRY` contains no Playwright-backed entries. JS-rendered portals (where they exist for Tier 1 states) currently rely on httpx. This is a latent risk if a state moves further behind a JS shell.
6. **Twilio and Whitepages are wired in env but not in the active enrichment waterfall.** `pyproject.toml` declares `twilio>=9.0.0`; `app/config.py` has `TWILIO_ACCOUNT_SID/TOKEN`; `WHITEPAGES_API_KEY` is declared. `build_enrichment_waterfall` only adds `pdl`, `apollo`, `opencorporates` today. Decision needed: drop the deps, or wire the layers.
7. **`app/dedup/` directory was referenced in `.kiln/docs/architecture.md` but in the actual tree dedup logic lives at `app/export/dedup.py`** (plus inlined into pipeline). Not a defect — the planning doc was prescriptive, the implementation collapsed it — but worth noting so future readers don't hunt for the missing folder.
8. **GHL custom-field startup validation (C-13) is not visible in `app/main.py`'s startup path.** The constraint says "fails fast at startup if any required field is absent" but no `assert_custom_fields()` call is present in lifespan. Either the planning intent was deferred, or this lives outside the entrypoint (e.g. first-call lazy check inside the adapter). Recommend adding an explicit startup check to satisfy C-13 verifiably.
9. **CI parity gap: Playwright browsers.** CI does not run `playwright install chromium`. Any future Playwright-backed scraper will pass tests only when its `@pytest.mark.slow` smoke is run on the scheduled workflow (and only if that workflow is updated to install Chromium). Document the install step explicitly when adding the first Playwright scraper.
10. **Agent → branch protection.** `AGENT-03` in `.planning/REQUIREMENTS.md` (Pending) flags that the agent's repair path must not violate GitHub branch-protection expectations. The current `repair` node opens a PR but the merge path on `verify`-pass needs to respect `main`'s protection rules; verify before enabling autonomous merge in production.
11. **Sentry "placeholder DSN" handling.** `app/config.py` warns that placeholder DSNs are rejected by the SDK; CI uses a syntactically valid-but-fake DSN. Be careful copying CI's env into a local `.env`.
12. **`MEMORY.md` (217 B) and `settings.local.json` (279 B)** are minimal but committed — review whether they should be `.gitignore`d.
13. **Two top-level state folders (`.kiln/`, `.planning/`) describe overlapping but not identical plans.** They are useful as input for an AI maintainer but require the reader to know that *the code* is canonical, not either plan.

## 16. Deployment Setup

### Railway (production target, C-04)

`railway.toml` declares three services (`[deploy]` = pipeline, `[service.agent]`, `[service.watchdog]`) under `NIXPACKS`. All three have `/health` checks with `healthcheckTimeout = 300`. The pipeline/agent use `restartPolicyType = "ON_FAILURE"` with `restartPolicyMaxRetries = 10`. The watchdog uses `restartPolicyType = "ALWAYS"` with `restartPolicyMaxRetries = 0` (i.e. "never give up").

### Deploy steps (from `DEPLOY.md`)

Two paths:

- **Automated:** `railway login` → `scripts/deploy_railway.sh` (script provisions Postgres plugin, prompts for env vars, deploys, runs migrations).
- **Manual:**
  1. `railway login`
  2. `railway init --name ucc-pipeline`
  3. `railway add --plugin postgresql`
  4. `railway variables set ...` (per `.env.example`)
  5. `railway up --detach`
  6. `railway run alembic upgrade head`

### Required env vars at minimum

`DATABASE_URL` (auto from Railway Postgres plugin), `SENTRY_DSN`, `GHL_API_KEY`, `GHL_LOCATION_ID`, `PDL_API_KEY`. Recommended: `ANTHROPIC_API_KEY`, `SENDGRID_API_KEY`, `MANAGER_EMAIL`, GHL workflow tier IDs.

### Local dev

`python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` then either `docker compose up -d` for Postgres or point `DATABASE_URL` elsewhere, then `python -m alembic upgrade head`, then `pytest -m "not slow"`.

## 17. Mapping to Constraints (Verification Pointers)

For each architectural constraint, where the code lives:

| Constraint | Lives in / verified by |
|------------|------------------------|
| C-01 AI maintainability | Whole codebase shape; `AGENTS.md` conventions; pytest gates |
| C-02 Compliance gate absolute | `app/compliance/gate.py`, `app/compliance/export_guard.py`, `tests/unit/test_compliance_negative.py` |
| C-03 Enrichment HALT | `app/enrichment/rate_tracker.py`, `app/enrichment/circuit_breaker.py`, `app/enrichment/pipeline.py::check_pipeline_halt` |
| C-04 Railway only | `railway.toml`, `Procfile`, `pyproject.toml` deps (no AWS SDKs etc.) |
| C-05 Single Postgres | `app/config.py::DATABASE_URL`, `app/db.py`, `migrations/` |
| C-06 Campaign adapter abstraction | `app/export/adapter.py`, `app/export/ghl_adapter.py` (only) |
| C-07 Watchdog isolation | `watchdog/monitor.py`, `watchdog/logging_config.py` (zero `app/`/`agent/` imports) |
| C-08 Indefinite retention | `app/enrichment/cache.py` (no TTL); model defaults |
| C-09 Rate limiting | `app/scrapers/rate_limiter.py` (jitter, backoff, tier-3 floor=10s, proxy cycle) |
| C-10 Cross-state dedup | `app/export/dedup.py`, normalized `debtor_name_normalized` column |
| C-11 Non-technical dashboard | `app/dashboard/routes.py`, `templates/`, HTMX/Jinja2/Tailwind/Chart.js via CDN |
| C-12 Internal DNC append-only | `app/compliance/internal_dnc.py`, `migrations/versions/003_dnc_reversal_audit.py` |
| C-13 GHL custom fields | `DEPLOY.md` checklist; **see Technical Debt #8** |
| C-14 Python only, no JS toolchain | `pyproject.toml` only; no `package.json`; `package-lock.json` is vestigial |
| C-15 DataMerch fallback | `app/compliance/gate.py::check_datamerch` (fail-open by default) + `COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH` |
| C-16 GitHub source of truth | `agent/graph.py` repair/verify nodes; `.github/workflows/ci.yml` |
| C-17 Tiered scraping | `app/scrapers/registry.py::SCRAPER_REGISTRY` + `schedulable_state_codes()` |

## 18. Recommended First Actions for AI Maintainers

If you are an AI agent picking this repo up cold, do these in order:

1. Read `AGENTS.md`, then `app/compliance/gate.py`, then `app/scrapers/base.py`, then `app/enrichment/pipeline.py`, then `agent/graph.py`. That is the load-bearing 80% of the system.
2. Run `pytest -m "not slow"` locally to baseline a green state.
3. Verify the technical-debt items in §15 — particularly the GHL custom-field startup check (#8), the lockfile situation (#1), and any leftover BMAD scaffolding (#3, #4).
4. Before touching any state scraper, run its dedicated smoke test (`tests/smoke/test_scraper_smoke.py -m slow`) to confirm whether failure is parser drift (your problem) or upstream portal change (file an issue first).
5. Never edit `app/compliance/gate.py`, `app/compliance/export_guard.py`, or `app/export/adapter.py` without explicit operator approval. These are the legal-survival surface (C-02, C-06).

---

*This document was produced by acting as the BMAD Architect (`bmad-document-project` skill, full-scan equivalent) against the cloned repository. Where planning docs and code diverge, code is the source of truth and the divergence is captured in §15.*
