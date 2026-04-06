# Codebase Structure

**Analysis Date:** 2026-04-06

## Directory Layout

```
UCC/
├── app/                    # Pipeline service (FastAPI, domain logic)
├── agent/                  # Self-healing agent service
├── watchdog/               # Heartbeat watchdog (no app/agent imports)
├── migrations/             # Alembic revisions (script_location from alembic.ini)
├── tests/                  # pytest: unit, integration, smoke
├── .kiln/                  # Planning artifacts: master-plan, architecture, ADRs
├── .cursor/                # Editor/GSD tooling (not runtime)
├── alembic.ini             # Alembic config at repo root
├── pyproject.toml          # Package metadata, dependencies, pytest config
├── Procfile                # Railway: web, agent, watchdog uvicorn commands
├── AGENTS.md               # Maintainer conventions and constraint summary
└── MEMORY.md               # Project notes (non-runtime)
```

## Directory Purposes

**`app/`:**

- Purpose: Pipeline service — scraping, MCA processing, enrichment, compliance, export, dashboard, shared logging/config/db.
- Contains: Python packages for each subdomain; Jinja templates under `app/dashboard/templates/`.
- Key files: `app/main.py`, `app/config.py`, `app/db.py`, `app/logging.py`, `app/scrapers/registry.py`, `app/mca/pipeline.py`, `app/enrichment/pipeline.py`, `app/compliance/gate.py`, `app/export/adapter.py`, `app/services/job_queue.py`, `app/dashboard/routes.py`.

**`agent/`:**

- Purpose: LangGraph-based agent loop and heartbeat writer, hosted as its own FastAPI app.
- Contains: `agent/graph.py` (graph + node functions), `agent/main.py`, `agent/heartbeat.py`.
- Key files: `agent/main.py`, `agent/graph.py`, `agent/heartbeat.py`.
- Note: There is no `agent/nodes/` package in this repository; node logic lives in `agent/graph.py` (differs from the illustrative tree in `.kiln/docs/architecture.md`).

**`watchdog/`:**

- Purpose: Isolated watchdog per C-07.
- Contains: `watchdog/main.py`, `watchdog/monitor.py`.
- Key files: `watchdog/main.py`, `watchdog/monitor.py`.

**`migrations/`:**

- Purpose: Alembic migration scripts.
- Contains: `migrations/env.py`, `migrations/versions/*.py`.
- Key files: `migrations/versions/001_initial_schema.py`.

**`tests/`:**

- Purpose: Automated tests mirroring major modules.
- Contains: `tests/unit/`, `tests/integration/`, `tests/smoke/`, `tests/conftest.py`.
- Note: `tests/contract/` from `.kiln/docs/architecture.md` is not present; contract-style checks may live under `tests/unit/` or remain to be added.

**`.kiln/docs/`:**

- Purpose: Canonical architecture, constraints, ADRs, research.
- Key files: `.kiln/docs/architecture.md`, `.kiln/docs/arch-constraints.md`, `.kiln/docs/decisions.md`, `.kiln/master-plan.md`.

---

## Key File Locations

**Entry Points:**

- `app/main.py`: Pipeline FastAPI app, routers, `/health`.
- `agent/main.py`: Agent FastAPI app, scheduled agent + heartbeat tasks, `/health`.
- `watchdog/main.py`: Watchdog FastAPI app, monitor loop, `/health`.

**Configuration:**

- `app/config.py`: `pydantic-settings` `Settings` for pipeline and code that imports it.
- `alembic.ini`: Alembic `script_location = migrations`.
- `pyproject.toml`: Dependencies and `tool.pytest.ini_options`.
- `Procfile`: Railway process types and commands.

**Core Logic:**

- Scraping: `app/scrapers/base.py`, `app/scrapers/states/<state>.py`, `app/scrapers/scheduler.py`, `app/scrapers/rate_limiter.py`, `app/scrapers/parsers.py`.
- MCA: `app/mca/detector.py`, `app/mca/scorer.py`, `app/mca/pipeline.py`, `app/models/mca_alias.py`.
- Enrichment: `app/enrichment/waterfall.py`, `app/enrichment/sources.py`, `app/enrichment/cache.py`, `app/enrichment/circuit_breaker.py`.
- Compliance: `app/compliance/gate.py`, `app/compliance/internal_dnc.py`.
- Export / dedup / webhooks: `app/export/dedup.py`, `app/export/webhook.py`, `app/export/recycler.py`, `app/export/ghl_adapter.py`.
- Jobs: `app/services/job_queue.py`, `app/models/job.py`.

**Persistence:**

- `app/db.py`: Async engine and `get_session` context manager.
- `app/models/`: ORM modules including `base.py`, `filing.py`, `lead.py`, `dnc.py`, `job.py`, `operations.py`.

**Testing:**

- `tests/conftest.py`: Shared fixtures.
- `tests/unit/test_*.py`: Module-focused tests (e.g. `tests/unit/test_waterfall.py`, `tests/unit/test_models.py`).
- `tests/integration/test_e2e_pipeline.py`: Integration coverage.
- `tests/smoke/test_scraper_smoke.py`: Smoke tests for scrapers.

---

## Naming Conventions

**Files:**

- Python modules and packages: `snake_case` (e.g. `app/scrapers/states/new_york.py`, `app/models/mca_alias.py`).
- Tests: `test_<module>.py` under `tests/unit/` per `AGENTS.md`.

**Directories:**

- Domain subpackages under `app/` mirror lifecycle stages: `scrapers/`, `mca/`, `enrichment/`, `compliance/`, `export/`, `dashboard/`, `services/`.
- One module per state scraper under `app/scrapers/states/`.

---

## Where to Add New Code

**New state scraper:**

- Implementation: `app/scrapers/states/<state>.py` (register in `app/scrapers/registry.py`).
- Tests: `tests/unit/test_state_scrapers.py` or a dedicated test module following existing scraper tests.

**New pipeline stage (business logic):**

- Primary code: appropriate `app/<domain>/` package (prefer existing `mca/`, `enrichment/`, `compliance/`, `export/`).
- If a new subdomain is needed, add `app/<new_package>/__init__.py` and keep dependencies one-way toward `app/models/` and `app/db.py`.

**New ORM model / table:**

- Model module: `app/models/<table_topic>.py`, export from `app/models/__init__.py` if required by convention.
- Migration: new revision under `migrations/versions/` via `alembic revision` (see `AGENTS.md` commands).

**New HTTP surface (pipeline):**

- Routes: extend `app/dashboard/routes.py` or add a new router module under `app/` and include it from `app/main.py`.

**Agent behavior change:**

- Graph nodes / edges: `agent/graph.py`; lifecycle: `agent/main.py` or `agent/heartbeat.py`.

**Watchdog rule change:**

- `watchdog/monitor.py` only — preserve C-07 (no imports from `app` or `agent`).

**Tests:**

- Unit: `tests/unit/test_<feature>.py`.
- Integration: `tests/integration/`.
- Smoke: `tests/smoke/` for external/live checks.

---

## Special Directories

**`.kiln/`:**

- Purpose: Product and engineering planning source of truth (vision, architecture, constraints, research).
- Generated: No.
- Committed: Yes (typical for this repo).

**`.cursor/`:**

- Purpose: GSD workflows, skills, agent definitions for Cursor.
- Generated: Mixed (tooling).
- Committed: Per team policy; not imported at runtime by pipeline services.

---

*Structure analysis: 2026-04-06*
