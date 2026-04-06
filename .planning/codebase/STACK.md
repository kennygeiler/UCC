# Technology Stack

**Analysis Date:** 2026-04-06

## Languages

**Primary:**
- Python 3.12+ — entire application (`app/`, `agent/`, `watchdog/`, `tests/`, `migrations/`). Declared in `pyproject.toml` as `requires-python = ">=3.12"`.

**Secondary:**
- SQL — schema migrations under `migrations/versions/` (Alembic-generated).

## Runtime

**Environment:**
- CPython 3.12 (CI pins 3.12 in `.github/workflows/ci.yml`).

**Package Manager:**
- pip (editable install: `pip install -e ".[dev]"` per `pyproject.toml` and `AGENTS.md`).
- Lockfile: not detected (no `uv.lock`, `poetry.lock`, or `requirements.txt` in repo root).

## Frameworks

**Core:**
- FastAPI (`>=0.110.0`) — HTTP apps for pipeline (`app/main.py`), agent (`agent/main.py`), watchdog (`watchdog/main.py`).
- Uvicorn (`uvicorn[standard]>=0.27.0`) — ASGI server; `Procfile` and `railway.toml` use `uvicorn` entrypoints.
- SQLAlchemy 2.0 async (`sqlalchemy[asyncio]>=2.0.0`) — ORM and async sessions (`app/db.py`, models under `app/models/`).
- asyncpg (`>=0.29.0`) — Postgres driver (URLs normalized to `postgresql+asyncpg://` in `app/db.py`, `migrations/env.py`).
- Alembic (`>=1.13.0`) — migrations; config in `alembic.ini`, scripts in `migrations/`.
- pydantic-settings (`>=2.0.0`) — typed env config in `app/config.py`.
- Jinja2 (`>=3.1.0`) — server-rendered dashboard via `fastapi.templating.Jinja2Templates` in `app/dashboard/routes.py`.
- python-multipart (`>=0.0.6`) — multipart uploads (e.g. dashboard CSV in `app/dashboard/routes.py`).

**Scraping & HTTP:**
- httpx (`>=0.27.0`) — async HTTP for enrichment, compliance, GHL, GitHub API calls, SendGrid from agent code.
- Playwright (`>=1.40.0`) — headless browser scraping (`app/scrapers/playwright_base.py`, state modules such as `app/scrapers/states/california.py`, `texas.py`, `new_york.py`, `new_jersey.py`).
- beautifulsoup4 (`>=4.12.0`) — HTML parsing (`app/scrapers/parsers.py` and related scrapers).

**Scheduling & resilience:**
- APScheduler (`>=3.10.0`) — in-process scheduling (`app/scrapers/scheduler.py`).
- pybreaker (`>=1.0.0`) — circuit breaker for enrichment (`app/enrichment/circuit_breaker.py`).

**Agent / LLM:**
- langgraph (`>=0.2.0`) — graph orchestration (`agent/graph.py`).
- anthropic (`>=0.30.0`) — Claude API for diagnosis (`agent/graph.py`).

**Automation & comms (libraries declared; usage in integration paths):**
- PyGithub (`>=2.0.0`) — GitHub automation (intended/agent paths; see `agent/graph.py`).
- sendgrid (`>=6.10.0`) — transactional email API (watchdog and agent).
- twilio (`>=9.0.0`) — Twilio Lookup HTTP API in `app/enrichment/sources.py`.

**Observability:**
- structlog (`>=23.0.0`) — JSON logging (`app/logging.py`).
- sentry-sdk (`>=2.0.0`) — error tracking init in `app/main.py`, `agent/main.py`, `watchdog/main.py`.

**Testing:**
- pytest (`>=8.0.0`), pytest-asyncio (`>=0.23.0`), pytest-cov (`>=4.0.0`) — optional dev extras in `pyproject.toml`; `testpaths = ["tests"]`, `asyncio_mode = "auto"`.

## Key Dependencies

**Critical:**
- `fastapi` + `uvicorn` — all three deployable services.
- `sqlalchemy[asyncio]` + `asyncpg` — single Postgres database pattern per `AGENTS.md` / architecture docs.
- `pydantic-settings` — central configuration surface (`app/config.py`).

**Infrastructure-aligned:**
- `alembic` — schema evolution (`migrations/env.py` reads `DATABASE_URL`).
- `sentry-sdk` — production error visibility.
- `langgraph` + `anthropic` — self-healing agent loop in `agent/graph.py`.

## Configuration

**Environment:**
- Primary definition: `app/config.py` (`Settings`); loads from process env and optional `.env` via `model_config` (do not commit real `.env`; template vars documented in `.env.example`).
- Watchdog intentionally avoids `app.config`: reads `DATABASE_URL`, `SENDGRID_API_KEY`, `MANAGER_EMAIL`, `SENTRY_DSN` from `os.environ` in `watchdog/monitor.py` (constraint C-07).
- Pipeline `app/main.py` and other entrypoints also call `sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))` in addition to `Settings` usage elsewhere.

**Build:**
- `pyproject.toml` — `[build-system]` setuptools; `[tool.setuptools.packages.find]` includes `app*`, `agent*`, `watchdog*`.
- `alembic.ini` — placeholder `sqlalchemy.url`; real URL overridden from env in `migrations/env.py`.

## Platform Requirements

**Development:**
- Python 3.12+, pip, network access for PyPI; Playwright requires browser install (`playwright install`) for scraper tests/runtime.
- Local DB: Postgres URL compatible with asyncpg (see `.env.example`).

**Production:**
- Railway: `railway.toml` (Nixpacks builder) defines `web`, `service.agent`, and `service.watchdog` start commands and `/health` checks; `Procfile` mirrors three-process layout.
- GitHub Actions: `.github/workflows/ci.yml` runs `pytest` with fake `DATABASE_URL` and `SENTRY_DSN`.

## Manager UI (current state)

- Server-rendered HTML with Jinja2 templates under `app/dashboard/templates/` (e.g. `dashboard.html`).
- HTMX and Tailwind loaded from public CDNs in `app/dashboard/templates/dashboard.html` (no npm/webpack toolchain).
- `.kiln/docs/tech-stack.md` mentions Chart.js via CDN; Chart.js is not referenced in `app/dashboard/templates/` at analysis time.

## Application code scope

- Application code is **not** minimal: substantial Python exists under `app/` (scrapers, enrichment, compliance, export, dashboard), `agent/`, `watchdog/`, plus `tests/` and `migrations/`.

---

*Stack analysis: 2026-04-06*
