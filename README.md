# UCC Lead Generation Platform

Python services that scrape public UCC filings, score MCA-related leads, run enrichment and compliance gates, and export to GoHighLevel—see `AGENTS.md` for architecture and constraints.

## Prerequisites

- **Python 3.12+** (CI uses 3.12; use a matching local version.)
- **PostgreSQL** when running migrations or integration tests (not required for all unit tests).

On macOS/Linux with **PEP 668** (externally managed Python), use a virtual environment—do not `pip install` globally.

## First-time setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set variables. Use a placeholder DSN shape only—never commit real credentials:

`postgresql+asyncpg://user:password@localhost:5432/dbname`

There is no lockfile; reproducibility relies on `pyproject.toml` lower bounds.

## Run tests

```bash
pytest
```

Default / PR CI runs **`pytest -m "not slow"`** (see `.github/workflows/ci.yml`) so network-heavy scraper smokes are excluded. Run slow smokes locally or via the scheduled workflow:

```bash
pytest tests/smoke/ -m slow -v
```

Unit tests use mocked DB settings via `tests/conftest.py`. Integration tests (`@pytest.mark.integration`) need a live Postgres and `DATABASE_URL` (see `tests/integration/`).

## Migrations

`DATABASE_URL` must be set (environment **or** `.env` at the project root — Alembic loads `.env` automatically).

```bash
python -m alembic upgrade head
```

If you see **`Connection refused`** / **`errno 61`** on port **5432**, Postgres is not listening locally. Start it (example: Homebrew `brew services start postgresql@16`, or Docker), create the database/user from your DSN, then retry. For a remote DB (e.g. Railway), point `DATABASE_URL` at that host instead of `localhost`.

## CI parity

GitHub Actions runs the same editable install, applies `alembic upgrade head` against a **Postgres service**, then runs `pytest -m "not slow"` with the same `DATABASE_URL` / `SENTRY_DSN` pattern as local development.

## Health endpoints

- **Pipeline and agent** (`/health`): HTTP **200** with JSON `status` of `ok` or `degraded` and `database` of `connected` or `unreachable`. Non-200 is not used for database outages so Railway liveness does not thrash on transient DB issues.
- **Watchdog** (`/health`): includes `monitor` (`active` once the monitoring task is scheduled).

## Service commands

Pipeline, agent, and watchdog commands (uvicorn, etc.) are documented in **`AGENTS.md`**.
