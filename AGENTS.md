# AGENTS.md

**First-time setup and CI parity:** see root [`README.md`](README.md) (venv, editable install, migrations, and how CI runs `alembic` + `pytest`).

## Commands
```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests (unit only, no DB required)
pytest -m "not slow"

# Run integration tests (requires DATABASE_URL pointing at a live Postgres)
pytest tests/integration/ -m integration -v

# Run pipeline service
uvicorn app.main:app --reload --port 8000

# Run agent service
python -m agent.main

# Run watchdog service
python -m watchdog.main

# Run database migrations (use project venv so `alembic` is on PATH, or -m below)
# source .venv/bin/activate   # macOS/Linux
python -m alembic upgrade head

# Generate new migration
python -m alembic revision --autogenerate -m "description"

# Scrape a Tier 1 state manually
python scripts/run_state_scrape.py --state FL
python scripts/run_state_scrape.py --state NY --quick

# Export MCA leads to CSV
python scripts/export_mca_accounts_csv.py --state FL
```

## Architecture TL;DR
UCC Lead Generation Platform -- a Python 3.12+ automated pipeline that scrapes public UCC filings from ~45 US state SOS websites, identifies MCA-burdened businesses, enriches them into leads, enforces 4-layer legal compliance, and exports to GoHighLevel. Three independent Railway services (pipeline, self-healing agent, heartbeat watchdog) share a single Postgres 16+ database. Server-rendered dashboard via FastAPI + Jinja2 + HTMX. Self-healing agent uses LangGraph with Postgres checkpointer. Zero human developers -- 100% AI-maintained.

## Conventions

### MCA settings (`app.config`)
- `MCA_FUZZY_MIN_ALIAS_LEN`, `MCA_FUZZY_SCORE_CUTOFF` — Rapidfuzz fuzzy alias match after exact match.
- `MCA_ALIAS_UPDATE_ENABLED` (default true; tests force false), `MCA_ALIAS_UPDATE_INTERVAL_HOURS` — optional nightly alias updater in the scraper scheduler.

### Enrichment settings (`app.config`)
- `ENRICH_BREAKER_ERROR_WINDOW_SECONDS`, `ENRICH_BREAKER_ERROR_RATE_THRESHOLD`, `ENRICH_RATE_MIN_ATTEMPTS_BEFORE_HALT` — rolling failure-rate window before pybreaker open + HALT.
- `ENRICH_RETRY_JOB_ENABLED` (default true; tests force false), `ENRICH_RETRY_INTERVAL_MINUTES` — scheduled `enrichment_retry_queue` processor.

### Compliance / DataMerch (C-15)
- `DATAMERCH_API_KEY` — optional in dev; when unset the DataMerch layer logs `datamerch_unconfigured` and **fail-opens** (not blocked) unless `COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH=true` (then the layer blocks).
- Export (`CampaignPlatformAdapter` implementations) calls `require_compliance_cleared` — `lead_data` must include `compliance_status == "cleared"`.
- Internal DNC is append-only; use `reverse_dnc_block` (audit row) instead of deleting rows (C-12).

### File Organization
- `app/` -- Pipeline service (FastAPI). Subpackages: models, scrapers, detection, scoring, enrichment, compliance, dedup, export, recycling, dashboard, scheduler.
- `agent/` -- Self-healing agent service. Subpackages: nodes.
- `watchdog/` -- Heartbeat watchdog. Zero imports from app/ or agent/.
- `migrations/` -- Alembic migration files.
- `tests/` -- Organized as unit/, integration/, smoke/, contract/. Every module has a corresponding test file.

### Naming
- Snake_case for all Python files and functions.
- One file per state scraper (e.g., `app/scrapers/states/california.py`).
- ORM models in `app/models/` with table-oriented file names.
- Test files mirror source: `tests/unit/test_config.py` tests `app/config.py`.

### Code Style (C-01)
- Functions under 50 lines, single-purpose, with docstrings.
- No metaprogramming, no dynamic imports, no clever abstractions.
- structlog JSON logging on every meaningful state change.
- Required log fields: component, status, error_type, context.

### Import Patterns
- Pipeline code imports only `app.export.adapter` (abstract), never `app.export.ghl_adapter` directly (C-06).
- Watchdog imports nothing from app/ or agent/ (C-07).
- All config via `app.config` (pydantic-settings), never raw os.environ.

### Scraper scheduler (pipeline)

- **`SCRAPER_SCHEDULER_ENABLED`** (default `true`): when `true`, `app.main` lifespan starts APScheduler from `app.scrapers.scheduler.create_scheduler()` and shuts it down cleanly. Tests set this to `false` via `tests/conftest.py` so background jobs do not run under pytest.
- **Playwright:** browser-based scrapers need Chromium installed in the runtime image (`playwright install chromium` or an equivalent Dockerfile step). CI does not install browsers by default; scheduled smokes may add it when needed.

### Database
- SQLAlchemy 2.0 async with asyncpg driver.
- All 13 tables in one Postgres instance.
- Job queue uses SELECT FOR UPDATE SKIP LOCKED pattern.
- Enrichment cache has no TTL -- permanent (C-08).

### Key Patterns
- Waterfall executor: generic ordered-strategy pattern used by enrichment, compliance, and scraper fallback (ADR-008).
- Circuit breaker (pybreaker): per enrichment source, >20% errors in 5 min triggers HALT (C-03).
- CampaignPlatformAdapter: abstract interface for campaign platform isolation (ADR-005, C-06).

## Key Files
```
pyproject.toml               -- Project metadata, dependencies, pytest config
app/main.py                  -- FastAPI entry point for pipeline service
app/config.py                -- pydantic-settings configuration (all env vars)
app/db.py                    -- SQLAlchemy async engine + session factory
app/models/                  -- ORM models: filing, account, lead, dnc, job, mca_alias, operations
app/scrapers/states/         -- One file per state scraper (florida.py, new_york.py, etc.)
app/scrapers/scheduler.py    -- APScheduler: tiered cadence (Tier1=24h, Tier2=36h, Tier3=48h)
app/scrapers/registry.py     -- State→scraper class + tier mapping
app/mca/detector.py          -- MCA alias + fuzzy matching pipeline
app/mca/scorer.py            -- Lead scoring (hot/warm/cold) from filing patterns
app/consolidation/pipeline.py -- Post-scrape rollup: business_accounts + scoring
app/enrichment/pipeline.py   -- Waterfall enrichment executor with HALT circuit breaker
app/compliance/gate.py       -- 4-layer compliance gate (DNC→DataMerch→DNC.com→Blacklist)
app/export/adapter.py        -- CampaignPlatformAdapter abstract interface (C-06)
app/export/ghl_adapter.py    -- GoHighLevel concrete implementation
app/export/csv_export.py     -- CSV fallback export for MCA lead accounts
app/dashboard/routes.py      -- Dashboard HTTP routes (HTMX, Jinja2 templates)
app/dashboard/queries.py     -- All dashboard SQL queries (stats, filings, leads, accounts)
agent/graph.py               -- LangGraph self-healing agent (detect/diagnose/repair/verify/alert)
watchdog/monitor.py          -- Heartbeat watchdog deadman switch (zero app/agent imports)
Procfile                     -- Railway service definitions (web/agent/watchdog)
railway.toml                 -- Railway deployment config (restart policies, health checks)
.github/workflows/ci.yml     -- GitHub Actions CI (Postgres 16, alembic, pytest)
migrations/versions/         -- Alembic migration files (6 migrations, current head)
tests/conftest.py            -- Shared test fixtures (env vars, DB cache clearing)
scripts/run_state_scrape.py  -- CLI to run any Tier 1 state scraper manually
scripts/export_mca_accounts_csv.py -- CLI MCA leads CSV export
.kiln/master-plan.md         -- 10 milestones, dependency graph, constraint coverage
.kiln/docs/arch-constraints.md -- 17 hard constraints (C-01 through C-17)
```

## Constraints Summary (17 hard constraints)
- C-01: AI maintainability (short functions, docstrings, tests for everything)
- C-02: 4-layer compliance gate is absolute (no bypasses)
- C-03: Enrichment failure >20% halts pipeline
- C-04: Railway deployment only
- C-05: Single Postgres database
- C-06: CampaignPlatformAdapter abstraction (no direct GHL imports in pipeline)
- C-07: Three independent Railway services (watchdog has zero app/agent imports)
- C-08: Indefinite data retention (no TTL anywhere)
- C-09: Per-state rate limiting with backoff and jitter
- C-10: Cross-state deduplication (exact + fuzzy)
- C-11: Non-technical manager dashboard
- C-12: Internal DNC is irrevocable (append-only, manager-only reversal)
- C-13: GHL custom fields pre-created (8 fields)
- C-14: Python only, no JS build toolchain
- C-15: DataMerch fallback path required
- C-16: GitHub as source of truth
- C-17: Tiered scraping strategy (4 tiers)
