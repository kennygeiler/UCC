<!-- gsd-project-start source:PROJECT.md -->
## Project

**UCC Lead Generation Platform**

Automated US-wide UCC (Uniform Commercial Code) lead pipeline: scrape public Secretary of State filings, detect MCA-burdened businesses, enrich and score leads, enforce a four-layer legal compliance gate, deduplicate across states, and export compliant leads to GoHighLevel—with a manager-facing dashboard, a LangGraph self-healing agent, and an independent heartbeat watchdog. Built for AI-only maintenance (short modules, tests, structured logging) and Railway deployment.

**GSD note:** This `PROJECT.md` was initialized from existing repo sources—`AGENTS.md`, `.kiln/master-plan.md`, and `.planning/codebase/*`. Refine scope here as delivery progresses.

**Core Value:** **Compliant, qualified MCA leads reach GHL without bypassing the compliance gate or platform-abstraction rules**—everything else is secondary to legal safety and adapter-isolated export.

### Constraints

- **C-01–C-17** (see `AGENTS.md` / `.kiln/docs/arch-constraints.md`): AI-maintainable code, absolute compliance gate, enrichment halt rules, Railway + single Postgres, adapter abstraction, three independent services, no enrichment TTL, rate limits, dedup, manager-simple dashboard, irrevocable internal DNC, GHL field prerequisites, Python-only surface for product code, DataMerch fallback, GitHub as source of truth, tiered scraping.
- **Deployment:** Railway; production secrets via platform env (never commit `.env` contents).
<!-- gsd-project-end -->

<!-- gsd-stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12+ — entire application (`app/`, `agent/`, `watchdog/`, `tests/`, `migrations/`). Declared in `pyproject.toml` as `requires-python = ">=3.12"`.
- SQL — schema migrations under `migrations/versions/` (Alembic-generated).
## Runtime
- CPython 3.12 (CI pins 3.12 in `.github/workflows/ci.yml`).
- pip (editable install: `pip install -e ".[dev]"` per `pyproject.toml` and `AGENTS.md`).
- Lockfile: not detected (no `uv.lock`, `poetry.lock`, or `requirements.txt` in repo root).
## Frameworks
- FastAPI (`>=0.110.0`) — HTTP apps for pipeline (`app/main.py`), agent (`agent/main.py`), watchdog (`watchdog/main.py`).
- Uvicorn (`uvicorn[standard]>=0.27.0`) — ASGI server; `Procfile` and `railway.toml` use `uvicorn` entrypoints.
- SQLAlchemy 2.0 async (`sqlalchemy[asyncio]>=2.0.0`) — ORM and async sessions (`app/db.py`, models under `app/models/`).
- asyncpg (`>=0.29.0`) — Postgres driver (URLs normalized to `postgresql+asyncpg://` in `app/db.py`, `migrations/env.py`).
- Alembic (`>=1.13.0`) — migrations; config in `alembic.ini`, scripts in `migrations/`.
- pydantic-settings (`>=2.0.0`) — typed env config in `app/config.py`.
- Jinja2 (`>=3.1.0`) — server-rendered dashboard via `fastapi.templating.Jinja2Templates` in `app/dashboard/routes.py`.
- python-multipart (`>=0.0.6`) — multipart uploads (e.g. dashboard CSV in `app/dashboard/routes.py`).
- httpx (`>=0.27.0`) — async HTTP for enrichment, compliance, GHL, GitHub API calls, SendGrid from agent code.
- Playwright (`>=1.40.0`) — headless browser scraping (`app/scrapers/playwright_base.py`, state modules such as `app/scrapers/states/california.py`, `texas.py`, `new_york.py`, `new_jersey.py`).
- beautifulsoup4 (`>=4.12.0`) — HTML parsing (`app/scrapers/parsers.py` and related scrapers).
- APScheduler (`>=3.10.0`) — in-process scheduling (`app/scrapers/scheduler.py`).
- pybreaker (`>=1.0.0`) — circuit breaker for enrichment (`app/enrichment/circuit_breaker.py`).
- langgraph (`>=0.2.0`) — graph orchestration (`agent/graph.py`).
- anthropic (`>=0.30.0`) — Claude API for diagnosis (`agent/graph.py`).
- PyGithub (`>=2.0.0`) — GitHub automation (intended/agent paths; see `agent/graph.py`).
- sendgrid (`>=6.10.0`) — transactional email API (watchdog and agent).
- twilio (`>=9.0.0`) — Twilio Lookup HTTP API in `app/enrichment/sources.py`.
- structlog (`>=23.0.0`) — JSON logging (`app/logging.py`).
- sentry-sdk (`>=2.0.0`) — error tracking init in `app/main.py`, `agent/main.py`, `watchdog/main.py`.
- pytest (`>=8.0.0`), pytest-asyncio (`>=0.23.0`), pytest-cov (`>=4.0.0`) — optional dev extras in `pyproject.toml`; `testpaths = ["tests"]`, `asyncio_mode = "auto"`.
## Key Dependencies
- `fastapi` + `uvicorn` — all three deployable services.
- `sqlalchemy[asyncio]` + `asyncpg` — single Postgres database pattern per `AGENTS.md` / architecture docs.
- `pydantic-settings` — central configuration surface (`app/config.py`).
- `alembic` — schema evolution (`migrations/env.py` reads `DATABASE_URL`).
- `sentry-sdk` — production error visibility.
- `langgraph` + `anthropic` — self-healing agent loop in `agent/graph.py`.
## Configuration
- Primary definition: `app/config.py` (`Settings`); loads from process env and optional `.env` via `model_config` (do not commit real `.env`; template vars documented in `.env.example`).
- Watchdog intentionally avoids `app.config`: reads `DATABASE_URL`, `SENDGRID_API_KEY`, `MANAGER_EMAIL`, `SENTRY_DSN` from `os.environ` in `watchdog/monitor.py` (constraint C-07).
- Pipeline `app/main.py` and other entrypoints also call `sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))` in addition to `Settings` usage elsewhere.
- `pyproject.toml` — `[build-system]` setuptools; `[tool.setuptools.packages.find]` includes `app*`, `agent*`, `watchdog*`.
- `alembic.ini` — placeholder `sqlalchemy.url`; real URL overridden from env in `migrations/env.py`.
## Platform Requirements
- Python 3.12+, pip, network access for PyPI; Playwright requires browser install (`playwright install`) for scraper tests/runtime.
- Local DB: Postgres URL compatible with asyncpg (see `.env.example`).
- Railway: `railway.toml` (Nixpacks builder) defines `web`, `service.agent`, and `service.watchdog` start commands and `/health` checks; `Procfile` mirrors three-process layout.
- GitHub Actions: `.github/workflows/ci.yml` runs `pytest` with fake `DATABASE_URL` and `SENTRY_DSN`.
## Manager UI (current state)
- Server-rendered HTML with Jinja2 templates under `app/dashboard/templates/` (e.g. `dashboard.html`).
- HTMX and Tailwind loaded from public CDNs in `app/dashboard/templates/dashboard.html` (no npm/webpack toolchain).
- `.kiln/docs/tech-stack.md` mentions Chart.js via CDN; Chart.js is not referenced in `app/dashboard/templates/` at analysis time.
## Application code scope
- Application code is **not** minimal: substantial Python exists under `app/` (scrapers, enrichment, compliance, export, dashboard), `agent/`, `watchdog/`, plus `tests/` and `migrations/`.
<!-- gsd-stack-end -->

<!-- gsd-conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Python modules and packages use **snake_case** (e.g. `app/scrapers/states/california.py`, `app/config.py`).
- One scraper module per state under `app/scrapers/states/`.
- ORM-oriented names under `app/models/` (table-oriented filenames per `AGENTS.md`).
- **snake_case** for functions and methods across `app/`, `agent/`, `watchdog/`.
- **snake_case** for locals and parameters; type hints used in settings and public APIs (see `app/config.py`).
- **PascalCase** for Pydantic settings and ORM models (e.g. `Settings` in `app/config.py`).
- Follow C-01 in `.kiln/docs/arch-constraints.md` and `AGENTS.md`: short, single-purpose functions with docstrings; no metaprogramming, no dynamic imports, no clever abstractions.
## Code Style
- **Not detected:** No `ruff.toml`, `[tool.ruff]`, `black` config, or `.editorconfig` in the repository root. Rely on Python 3.12+ syntax and consistent style matching existing modules.
- **Not detected:** No ESLint/Biome (C-14: Python only). No configured mypy or ruff in `pyproject.toml`.
- Present on settings and many internal APIs (e.g. `app/config.py`, `app/logging.py` return types). Extend the same style for new code.
## Import Organization
- **Not detected:** No `src` layout or import path rewrites; packages are `app`, `agent`, `watchdog` per `pyproject.toml` `[tool.setuptools.packages.find]`.
- Pipeline code imports the abstract export surface only: `app.export.adapter` — never GHL-specific modules directly.
- `watchdog/` must not import from `app/` or `agent/`.
- Configuration: use `app.config` / pydantic-settings (`Settings`); do not read raw `os.environ` in application logic.
## Error Handling
- **Pydantic `ValidationError`:** Required settings missing → fail fast (see tests in `tests/unit/test_config.py`).
- **Domain errors:** Raised exceptions consumed by callers or tests (e.g. `WaterfallExhaustedError` in `app/enrichment/waterfall.py`, asserted in `tests/unit/test_waterfall.py` and `tests/integration/test_e2e_pipeline.py`).
- **HTTP / I/O:** Scrapers and async code use async patterns; tests mock `httpx` or session behavior with `AsyncMock` (e.g. `tests/unit/test_scraper_base.py`, `tests/unit/test_state_scrapers.py`).
- Prefer explicit exceptions over silent failures for pipeline stages that affect compliance or export (align with C-02).
## Logging
- Call `configure_logging()` where the process starts (application entrypoints).
- Obtain loggers with `get_logger("<component>")` from `app/logging.py`; bind **component**, and on meaningful events include **status**, **error_type**, and **context** as required by `AGENTS.md` / C-01.
## Comments
- Module-level docstrings describe purpose and constraints (`app/config.py`, `app/logging.py`).
- Test docstrings state the behavior under test (one line, imperative).
- Use for public modules and non-obvious behavior; C-01 expects docstrings on functions — match the style in `app/logging.py` (`configure_logging`, `get_logger`).
## Function Design
## Module Design
<!-- gsd-conventions-end -->

<!-- gsd-architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Async I/O end-to-end for DB access (`asyncpg` via SQLAlchemy 2.0) in `app/db.py`.
- Ordered-strategy **waterfall** execution for enrichment and similar flows (`app/enrichment/waterfall.py`).
- Campaign platform isolation via **`CampaignPlatformAdapter`** (`app/export/adapter.py`); concrete GHL logic lives in `app/export/ghl_adapter.py` (C-06: pipeline logic should depend on the abstract adapter, not GHL modules directly).
- Structured logging via `app/logging.py` and optional Sentry in each service entrypoint.
## Layers
- Purpose: UCC scrape → MCA detection/scoring → enrichment → compliance → dedup/export → dashboard and webhooks.
- Location: `app/`
- Contains: FastAPI app (`app/main.py`), settings (`app/config.py`), DB session factory (`app/db.py`), ORM models (`app/models/`), scrapers (`app/scrapers/`), MCA pipeline (`app/mca/`), enrichment (`app/enrichment/`), compliance (`app/compliance/`), export (`app/export/`), job queue service (`app/services/job_queue.py`), dashboard (`app/dashboard/`).
- Depends on: PostgreSQL, external HTTP APIs (scrapers, enrichment, compliance, GHL), environment configuration via `app.config.Settings`.
- Used by: Railway `web` process (`uvicorn app.main:app` per `Procfile`).
- Purpose: Periodic autonomous cycle (detect anomalies, diagnose/repair path in graph) and heartbeat persistence.
- Location: `agent/`
- Contains: FastAPI shell with scheduled loop (`agent/main.py`), LangGraph state machine and node functions (`agent/graph.py`), heartbeat task (`agent/heartbeat.py`).
- Depends on: Shared DB and models via `app.db`, `app.models.*`, shared logging `app.logging` (agent is not isolated from `app/` like the watchdog).
- Used by: Railway `agent` process (`uvicorn agent.main:app` per `Procfile`).
- Purpose: Independent monitoring loop; checks agent heartbeat (and related signals) using raw SQLAlchemy engine creation and `os.environ` only—no `app.config`, no `agent` imports (C-07).
- Location: `watchdog/`
- Contains: FastAPI entry (`watchdog/main.py`), monitor loop (`watchdog/monitor.py`).
- Depends on: `DATABASE_URL`, SendGrid and manager email env vars as implemented in `watchdog/monitor.py`.
- Used by: Railway `watchdog` process (`uvicorn watchdog.main:app` per `Procfile`).
- Purpose: Single Postgres schema; Alembic revisions under `migrations/`.
- Location: `migrations/`, configured from repo-root `alembic.ini` (`script_location = migrations`).
- Contains: `migrations/env.py`, `migrations/versions/001_initial_schema.py`.
## Data Flow
- Business state: PostgreSQL tables defined in ORM models under `app/models/` (see `.kiln/docs/architecture.md` for logical table list).
- Agent graph state: `AgentState` TypedDict and LangGraph checkpointing patterns in `agent/graph.py` (checkpointer integration as implemented there).
- HTTP session state: Stateless FastAPI; dashboard uses server-rendered templates and HTMX-friendly partials where applicable.
## Key Abstractions
- Purpose: Isolate CRM/campaign operations behind a stable interface (C-06).
- Examples: `app/export/adapter.py` (abstract), `app/export/ghl_adapter.py`, `app/export/csv_fallback.py`.
- Pattern: Abstract base class with `upsert_lead`, `enroll_in_campaign`, `parse_webhook_payload`.
- Purpose: Try ordered async strategies; first success wins; shared logging (ADR-008 in `.kiln/docs/decisions.md` / `.kiln/docs/architecture.md`).
- Examples: `app/enrichment/waterfall.py`.
- Pattern: Constructor takes `list[tuple[str, Callable]]`; `execute(**kwargs)` returns `(source_name, result)` or raises `WaterfallExhaustedError`.
- Purpose: Per-state scraping with shared HTTP/Playwright behavior.
- Examples: `app/scrapers/base.py`, `app/scrapers/playwright_base.py`, `app/scrapers/registry.py`, `app/scrapers/states/*.py`.
- Pattern: Registry maps state codes to scraper classes; rate limiting in `app/scrapers/rate_limiter.py`.
- Purpose: Encode detect → act → verify loop as a graph.
- Examples: `agent/graph.py` (nodes as functions wired with `StateGraph`, state type `AgentState`).
- Pattern: LangGraph `StateGraph` with checkpoint saver hookup as implemented in that file.
- Purpose: Postgres-backed work queue (SKIP LOCKED pattern described in `AGENTS.md` and `.kiln/docs/architecture.md`).
- Examples: `app/services/job_queue.py`, model `app/models/job.py`.
## Entry Points
- Location: `app/main.py`
- Triggers: `uvicorn app.main:app` (Railway `web` in `Procfile`).
- Responsibilities: Create `FastAPI` app, mount `app.dashboard.routes.router` and `app.export.webhook.router`, expose `GET /health`, configure logging and engine disposal on lifespan.
- Location: `agent/main.py`
- Triggers: `uvicorn agent.main:app` (Railway `agent` in `Procfile`).
- Responsibilities: Start agent cycle and heartbeat asyncio tasks on lifespan; `GET /health`.
- Location: `watchdog/main.py`
- Triggers: `uvicorn watchdog.main:app` (Railway `watchdog` in `Procfile`).
- Responsibilities: Start `watchdog.monitor.run_watchdog_loop` on lifespan; `GET /health`; Sentry init without importing `app` or `agent`.
## Error Handling
- Enrichment: circuit breaker module `app/enrichment/circuit_breaker.py` coordinates with waterfall execution.
- Compliance: sequential gates in `app/compliance/gate.py` with explicit block vs pass semantics (C-02).
- Agent cycle: try/except in `agent/main.py` `_agent_loop` logs `agent_cycle_failed` without stopping the loop.
## Cross-Cutting Concerns
<!-- gsd-architecture-end -->

<!-- gsd-skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.cursor/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- gsd-skills-end -->

<!-- gsd-workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- gsd-workflow-end -->



<!-- gsd-profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- gsd-profile-end -->
