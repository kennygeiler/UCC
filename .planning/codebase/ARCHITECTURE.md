# Architecture

**Analysis Date:** 2026-04-06

## Pattern Overview

**Overall:** Three independent Python services (FastAPI + background asyncio loops) sharing one PostgreSQL database, deployed as separate Railway processes per `Procfile`. The pipeline service owns scraping through export and the manager dashboard; the agent service runs a LangGraph-style repair cycle and writes heartbeats; the watchdog service is a deadman switch with no imports from `app/` or `agent/` (C-07).

**Key Characteristics:**

- Async I/O end-to-end for DB access (`asyncpg` via SQLAlchemy 2.0) in `app/db.py`.
- Ordered-strategy **waterfall** execution for enrichment and similar flows (`app/enrichment/waterfall.py`).
- Campaign platform isolation via **`CampaignPlatformAdapter`** (`app/export/adapter.py`); concrete GHL logic lives in `app/export/ghl_adapter.py` (C-06: pipeline logic should depend on the abstract adapter, not GHL modules directly).
- Structured logging via `app/logging.py` and optional Sentry in each service entrypoint.

**Authoritative design reference:** `.kiln/docs/architecture.md` (component map, logical schema, deployment model). **`AGENTS.md`** states the same product intent; its "Key Files — NOT YET CREATED" list is stale relative to the repository.

---

## Layers

**Pipeline service (`app/`):**

- Purpose: UCC scrape → MCA detection/scoring → enrichment → compliance → dedup/export → dashboard and webhooks.
- Location: `app/`
- Contains: FastAPI app (`app/main.py`), settings (`app/config.py`), DB session factory (`app/db.py`), ORM models (`app/models/`), scrapers (`app/scrapers/`), MCA pipeline (`app/mca/`), enrichment (`app/enrichment/`), compliance (`app/compliance/`), export (`app/export/`), job queue service (`app/services/job_queue.py`), dashboard (`app/dashboard/`).
- Depends on: PostgreSQL, external HTTP APIs (scrapers, enrichment, compliance, GHL), environment configuration via `app.config.Settings`.
- Used by: Railway `web` process (`uvicorn app.main:app` per `Procfile`).

**Self-healing agent service (`agent/`):**

- Purpose: Periodic autonomous cycle (detect anomalies, diagnose/repair path in graph) and heartbeat persistence.
- Location: `agent/`
- Contains: FastAPI shell with scheduled loop (`agent/main.py`), LangGraph state machine and node functions (`agent/graph.py`), heartbeat task (`agent/heartbeat.py`).
- Depends on: Shared DB and models via `app.db`, `app.models.*`, shared logging `app.logging` (agent is not isolated from `app/` like the watchdog).
- Used by: Railway `agent` process (`uvicorn agent.main:app` per `Procfile`).

**Heartbeat watchdog (`watchdog/`):**

- Purpose: Independent monitoring loop; checks agent heartbeat (and related signals) using raw SQLAlchemy engine creation and `os.environ` only—no `app.config`, no `agent` imports (C-07).
- Location: `watchdog/`
- Contains: FastAPI entry (`watchdog/main.py`), monitor loop (`watchdog/monitor.py`).
- Depends on: `DATABASE_URL`, SendGrid and manager email env vars as implemented in `watchdog/monitor.py`.
- Used by: Railway `watchdog` process (`uvicorn watchdog.main:app` per `Procfile`).

**Persistence & migrations:**

- Purpose: Single Postgres schema; Alembic revisions under `migrations/`.
- Location: `migrations/`, configured from repo-root `alembic.ini` (`script_location = migrations`).
- Contains: `migrations/env.py`, `migrations/versions/001_initial_schema.py`.

---

## Data Flow

**Happy-path lead lifecycle (intended — see `.kiln/docs/architecture.md`):**

1. Scheduler/scraper jobs pull public UCC data from state SOS endpoints (`app/scrapers/`, `app/scrapers/scheduler.py`).
2. MCA identification and scoring run in `app/mca/` (`detector.py`, `scorer.py`, `pipeline.py`).
3. Enrichment uses `WaterfallExecutor` and source callables (`app/enrichment/pipeline.py`, `app/enrichment/sources.py`, `app/enrichment/cache.py`, `app/enrichment/circuit_breaker.py`).
4. Four-layer compliance runs through `app/compliance/gate.py` with internal DNC in `app/compliance/internal_dnc.py`.
5. Deduplication and export go through `app/export/dedup.py` and adapter implementations (`app/export/ghl_adapter.py`, `app/export/csv_fallback.py`).
6. GHL disposition feedback and recycling: `app/export/webhook.py`, `app/export/recycler.py`.
7. Operational visibility: `app/dashboard/routes.py` + Jinja templates under `app/dashboard/templates/`.

**Self-healing / operations (runtime):**

1. `agent/main.py` starts `_agent_loop()` calling `run_agent_cycle()` from `agent/graph.py` and a separate `heartbeat_loop()` from `agent/heartbeat.py`.
2. `agent/graph.py` reads operational tables such as `ScraperRun` and `PipelineEvent` via `app.models.operations` to build anomaly lists, then runs graph nodes (detect → diagnose → repair → verify → alert-style flow as defined in that module).
3. `watchdog/monitor.py` polls `agent_heartbeat` (and related checks) on an interval and can alert independently if the agent appears stale.

**State management:**

- Business state: PostgreSQL tables defined in ORM models under `app/models/` (see `.kiln/docs/architecture.md` for logical table list).
- Agent graph state: `AgentState` TypedDict and LangGraph checkpointing patterns in `agent/graph.py` (checkpointer integration as implemented there).
- HTTP session state: Stateless FastAPI; dashboard uses server-rendered templates and HTMX-friendly partials where applicable.

---

## Key Abstractions

**`CampaignPlatformAdapter`:**

- Purpose: Isolate CRM/campaign operations behind a stable interface (C-06).
- Examples: `app/export/adapter.py` (abstract), `app/export/ghl_adapter.py`, `app/export/csv_fallback.py`.
- Pattern: Abstract base class with `upsert_lead`, `enroll_in_campaign`, `parse_webhook_payload`.

**`WaterfallExecutor`:**

- Purpose: Try ordered async strategies; first success wins; shared logging (ADR-008 in `.kiln/docs/decisions.md` / `.kiln/docs/architecture.md`).
- Examples: `app/enrichment/waterfall.py`.
- Pattern: Constructor takes `list[tuple[str, Callable]]`; `execute(**kwargs)` returns `(source_name, result)` or raises `WaterfallExhaustedError`.

**Scraper hierarchy:**

- Purpose: Per-state scraping with shared HTTP/Playwright behavior.
- Examples: `app/scrapers/base.py`, `app/scrapers/playwright_base.py`, `app/scrapers/registry.py`, `app/scrapers/states/*.py`.
- Pattern: Registry maps state codes to scraper classes; rate limiting in `app/scrapers/rate_limiter.py`.

**LangGraph agent graph:**

- Purpose: Encode detect → act → verify loop as a graph.
- Examples: `agent/graph.py` (nodes as functions wired with `StateGraph`, state type `AgentState`).
- Pattern: LangGraph `StateGraph` with checkpoint saver hookup as implemented in that file.

**Job queue:**

- Purpose: Postgres-backed work queue (SKIP LOCKED pattern described in `AGENTS.md` and `.kiln/docs/architecture.md`).
- Examples: `app/services/job_queue.py`, model `app/models/job.py`.

---

## Entry Points

**Pipeline HTTP API:**

- Location: `app/main.py`
- Triggers: `uvicorn app.main:app` (Railway `web` in `Procfile`).
- Responsibilities: Create `FastAPI` app, mount `app.dashboard.routes.router` and `app.export.webhook.router`, expose `GET /health`, configure logging and engine disposal on lifespan.

**Agent HTTP + background tasks:**

- Location: `agent/main.py`
- Triggers: `uvicorn agent.main:app` (Railway `agent` in `Procfile`).
- Responsibilities: Start agent cycle and heartbeat asyncio tasks on lifespan; `GET /health`.

**Watchdog HTTP + background loop:**

- Location: `watchdog/main.py`
- Triggers: `uvicorn watchdog.main:app` (Railway `watchdog` in `Procfile`).
- Responsibilities: Start `watchdog.monitor.run_watchdog_loop` on lifespan; `GET /health`; Sentry init without importing `app` or `agent`.

---

## Error Handling

**Strategy:** Fail fast on missing critical config in `app/config.py` for pipeline code; log structured errors with component context; optional Sentry capture via `sentry_sdk.init` in each service entry module.

**Patterns:**

- Enrichment: circuit breaker module `app/enrichment/circuit_breaker.py` coordinates with waterfall execution.
- Compliance: sequential gates in `app/compliance/gate.py` with explicit block vs pass semantics (C-02).
- Agent cycle: try/except in `agent/main.py` `_agent_loop` logs `agent_cycle_failed` without stopping the loop.

---

## Cross-Cutting Concerns

**Logging:** `app/logging.py` (`configure_logging`, `get_logger`); use in pipeline and agent. Watchdog avoids `app.logging` and uses Sentry/env only per C-07.

**Validation:** Pydantic settings in `app/config.py` for pipeline; watchdog validates presence of `DATABASE_URL` inside `watchdog/monitor.py` routines.

**Authentication / dashboard exposure:** Intended as manager-facing, restricted at edge (see `.kiln/docs/architecture.md` security boundaries); implement in `app/dashboard/routes.py` and deployment config.

---

*Architecture analysis: 2026-04-06*
