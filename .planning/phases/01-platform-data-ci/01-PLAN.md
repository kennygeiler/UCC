---
phase: 01-platform-data-ci
plan: "01"
type: execute
wave: 1
depends_on: []
requirements:
  - PLAT-01
  - PLAT-04
  - PLAT-03
requirements_addressed:
  - PLAT-01
  - PLAT-04
  - PLAT-03
autonomous: true
files_modified:
  - README.md
  - .github/workflows/ci.yml
  - AGENTS.md
must_haves:
  truths:
    - "Root README documents Python 3.12+ venv, editable install, pytest, and points to AGENTS.md for service commands."
    - "GitHub Actions starts Postgres, waits for readiness, runs `alembic upgrade head`, then `pytest` with the same env pattern as documented locally."
    - "CI proves migrations apply to head against a disposable database (no silent skip of Alembic)."
  artifacts:
    - path: README.md
      provides: "Onboarding and install parity with CI"
    - path: .github/workflows/ci.yml
      provides: "Postgres service + migration + test job"
---

<objective>
Establish developer onboarding documentation and CI parity with a real Postgres instance, including a blocking Alembic migration gate before tests.

Purpose: Satisfy PLAT-01 (install + pytest local/CI), PLAT-04 (head applies), and baseline evidence for PLAT-03 (single DB URL used consistently in CI).

Output: `README.md`, updated `ci.yml`, optional small `AGENTS.md` cross-link only if README duplicates commands.
</objective>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-platform-data-ci/01-RESEARCH.md
@pyproject.toml
@alembic.ini
@migrations/env.py
</context>

<threat_model>
## Trust boundaries

| Boundary | Description |
|----------|-------------|
| CI runner → Postgres service | Ephemeral DB; credentials are test-only but must not leak into logs or artifacts. |
| Developer machine → DATABASE_URL | Local `.env` must not be committed; docs must warn against logging connection strings. |

## STRIDE register

| Threat ID | Category | Component | Disposition | Mitigation (mapped to tasks) |
|-----------|----------|-----------|-------------|------------------------------|
| T-01-01 | Information disclosure | CI logs | mitigate | Task 1: document never echoing `DATABASE_URL`; Task 2: use GitHub encrypted env pattern only if secrets added—keep test user/password as public test values, document they are non-prod. |
| T-01-02 | Elevation of privilege | Postgres in CI | accept | Ephemeral service scoped to job; no inbound from internet beyond Actions runner. |
| T-01-03 | Tampering | Migration output | mitigate | Task 2: fail job if `alembic upgrade head` exits non-zero. |
| T-01-04 | Information disclosure | README examples | mitigate | Task 1: use placeholder DSN in examples (`postgresql+asyncpg://user:pass@localhost:5432/dbname`), not real credentials. |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Root README and AGENTS.md cross-links (PLAT-01)</name>
  <files>README.md</files>
  <read_first>
    - `AGENTS.md` (commands section)
    - `pyproject.toml` (`[project]` and dev extras)
    - `.env.example` if present (variable names only)
  </read_first>
  <action>
    Add `README.md` at repo root: title, one-paragraph product summary, **Prerequisites** (Python 3.12+, Postgres for integration/migrations), **Editable install** (`python3.12 -m venv .venv`, `source .venv/bin/activate`, `pip install -e ".[dev]"`), **Run tests** (`pytest`), **Run migrations** (`alembic upgrade head` with `DATABASE_URL` set—reference asyncpg URL shape), **CI parity** sentence stating GitHub Actions runs the same install + Alembic + pytest. Link to `AGENTS.md` for uvicorn/agent/watchdog commands. Do not duplicate full constraint docs. Mention PEP 668: use a venv. No lockfile: note reproducibility uses `pyproject.toml` lower bounds.
  </action>
  <verify>
    <automated>test -f README.md && grep -q "pip install -e" README.md && grep -q pytest README.md && grep -q AGENTS.md README.md</automated>
  </verify>
  <done>Root `README.md` exists with venv + editable install, pytest, migrations + `DATABASE_URL` note, CI parity line, link to `AGENTS.md`, and placeholder DSN examples only (no real credentials).</done>
</task>

<task type="auto">
  <name>Task 2: [BLOCKING] CI Postgres service + `alembic upgrade head` + pytest (PLAT-01, PLAT-04, PLAT-03)</name>
  <files>.github/workflows/ci.yml</files>
  <read_first>
    - `.github/workflows/ci.yml`
    - `migrations/env.py` (async URL normalization)
    - `01-RESEARCH.md` CI gap section
  </read_first>
  <action>
    Update `ci.yml`: add `services.postgres` (e.g. `postgres:16`) with `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` matching a single `DATABASE_URL` for the job (use `localhost:5432` from job container). Add a step to wait for Postgres TCP readiness (e.g. `pg_isready` or retry loop) before migrations. Add step **after** install: run `alembic upgrade head` with `DATABASE_URL` set to `postgresql+asyncpg://...` (same shape as `migrations/env.py` expects). Then run `pytest` with identical `DATABASE_URL` and `SENTRY_DSN` (fake DSN acceptable). Ensure migration step is `[BLOCKING]`: `set -e` / non-zero exit fails the workflow. Do not print full `DATABASE_URL` in step names or echo commands that expose secrets if later switched to GitHub Secrets.
  </action>
  <verify>
    <automated>grep -q "services:" .github/workflows/ci.yml && grep -q "postgres" .github/workflows/ci.yml && grep -q "alembic upgrade head" .github/workflows/ci.yml</automated>
  </verify>
  <done>Workflow defines Postgres service, waits for DB readiness, runs `alembic upgrade head` as a blocking step before `pytest`, and sets `DATABASE_URL` / `SENTRY_DSN` without leaking secrets in log-oriented step output.</done>
</task>

<task type="auto">
  <name>Task 3: AGENTS.md pointer to README (PLAT-01)</name>
  <files>AGENTS.md</files>
  <read_first>`AGENTS.md` top sections</read_first>
  <action>
    Add one short subsection or bullet under **Commands** or after **Architecture TL;DR**: "First-time setup and CI parity: see root `README.md`."
  </action>
  <verify>
    <automated>grep -q README.md AGENTS.md</automated>
  </verify>
  <done>`AGENTS.md` points readers to root `README.md` for first-time setup and CI parity.</done>
</task>

</tasks>

<verification>
- Full workflow green on a branch with these changes (executor runs CI or `act` if configured).
- `alembic upgrade head` completes against CI Postgres before any test collection that needs tables.
</verification>

<success_criteria>
PLAT-01 documentation exists; CI runs pytest after successful `alembic upgrade head` against a real Postgres service.
</success_criteria>

<output>
After completion, create `.planning/phases/01-platform-data-ci/01-01-SUMMARY.md` (or project-standard summary name).
</output>
