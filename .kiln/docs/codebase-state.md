<!-- status: complete -->
# Codebase State

## TL;DR
Current milestone: M1 Foundation, Database, and CI/CD. 0/14 deliverables complete. Key files: pyproject.toml, app/main.py, app/db.py (none exist yet).
Last change: Greenfield -- no source code exists. Build iteration 1.

## Milestone: M1 Foundation, Database, and CI/CD
Status: not started

### Deliverables
- [ ] Python project structure with pyproject.toml and all declared dependencies -- pyproject.toml
- [ ] Configuration module (pydantic-settings) with env var validation -- app/config.py
- [ ] SQLAlchemy 2.0 async engine and session factory -- app/db.py
- [ ] ORM models for all 13 tables -- app/models/
- [ ] Alembic migration infrastructure with initial migration -- migrations/
- [ ] Postgres job queue (SELECT FOR UPDATE SKIP LOCKED) -- app/models/job.py + job queue service
- [ ] structlog JSON logging configuration -- app/logging.py
- [ ] Health check endpoints for all three services -- app/main.py, agent/main.py, watchdog/main.py
- [ ] FastAPI application entry point; stub entry points for agent and watchdog -- app/main.py, agent/main.py, watchdog/main.py
- [ ] Procfile and railway.toml with restart policies and health checks -- Procfile, railway.toml
- [ ] GitHub Actions workflow (pytest on push/PR) -- .github/workflows/ci.yml
- [ ] Sentry SDK initialized in all three service entry points -- app/main.py, agent/main.py, watchdog/main.py
- [ ] pytest configuration with conftest and foundational tests -- tests/conftest.py, pytest section in pyproject.toml
- [ ] Environment variable reference file -- .env.example

### Target Module Layout (from architecture.md)
```
app/                    -- Pipeline service (FastAPI)
  main.py               -- Entry point
  config.py             -- pydantic-settings
  db.py                 -- SQLAlchemy async engine + session
  models/               -- ORM models (13 tables)
    filing.py, lead.py, mca_alias.py, dnc.py, job.py, operations.py
  scrapers/             -- (M2)
  detection/            -- (M3)
  scoring/              -- (M3)
  enrichment/           -- (M4)
  compliance/           -- (M5)
  dedup/                -- (M6)
  export/               -- (M6)
  recycling/            -- (M6)
  dashboard/            -- (M7)
  scheduler/            -- (M2)
agent/                  -- Self-healing agent service (M8)
  main.py, graph.py, nodes/, heartbeat.py
watchdog/               -- Heartbeat watchdog service (M9)
  main.py, checker.py, alerter.py
migrations/             -- Alembic
tests/                  -- unit/, integration/, smoke/, contract/
```

### Database Tables (all created in M1)
ucc_filings, leads, mca_aliases, enrichment_cache, internal_dnc, compliance_checks, state_priority, scraper_runs, job_queue, enrichment_retry_queue, agent_heartbeat, pipeline_events, langgraph_checkpoints

## Milestone: M2 Scraper Engine
Status: not started

## Milestone: M3 MCA Detection and Lead Scoring
Status: not started

## Milestone: M4 Enrichment Pipeline
Status: not started

## Milestone: M5 Compliance Gate
Status: not started

## Milestone: M6 Deduplication and Campaign Export
Status: not started

## Milestone: M7 Manager Dashboard
Status: not started

## Milestone: M8 Self-Healing Agent
Status: not started

## Milestone: M9 Heartbeat Watchdog
Status: not started

## Milestone: M10 End-to-End Integration and Production Readiness
Status: not started

## Existing Files
- `.kiln/` -- Planning docs only (architecture, tech-stack, constraints, decisions, master-plan)
- `MEMORY.md` -- Project memory file
- No source code, no pyproject.toml, no tests, no configuration files
