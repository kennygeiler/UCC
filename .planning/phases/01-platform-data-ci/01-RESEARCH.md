# Phase 1: Platform, data & CI - Research

**Researched:** 2026-04-06  
**Domain:** Python 3.12+ monorepo (`app` / `agent` / `watchdog`), FastAPI, SQLAlchemy 2 async, Alembic, pytest, GitHub Actions, Railway  
**Confidence:** HIGH for repo-grounded gaps; MEDIUM for ecosystem “best practice” beyond what the roadmap already states

## User Constraints

**None from CONTEXT.md** (no discuss-phase artifact for this phase). Locked engineering constraints come from:

- `AGENTS.md` (three services, single Postgres, async SQLAlchemy, pydantic-settings, structlog fields, job queue pattern, watchdog isolation C-07, adapter rules C-06, etc.)
- `.kiln/docs/arch-constraints.md` and `.kiln/master-plan.md` for milestone intent
- `.cursor/rules/gsd-project-context.md` — embedded stack map and conventions (authoritative for GSD/planner context)

### Project constraints (from `.cursor/rules/`)

| Source | Directive |
|--------|-----------|
| `gsd-project-context.md` | Prefer GSD entry points (`/gsd-quick`, `/gsd-debug`, `/gsd-execute-phase`) for file-changing work so planning artifacts stay aligned. |
| Same | Python 3.12+, pip editable install `pip install -e ".[dev]"`; no lockfile in repo today — document implications for reproducibility. |
| Same | Watchdog **must not** import `app` or `agent` (C-07); it uses raw `os.environ` for config — plans must not “fix” this by importing `app.config`. |
| Same | Pipeline config should go through `app.config` / `Settings`; **note:** entrypoints currently read `SENTRY_DSN` via `os.environ` for `sentry_sdk.init` — planner should reconcile with PLAT-02/PLAT-08 without violating C-07. |
| Same | Logging: use `configure_logging()` + `get_logger(component)`; meaningful events should carry `component`, `status`, `error_type`, `context` per `AGENTS.md`. |

## Summary

Phase 1 is **brownfield hardening and evidence**, not greenfield scaffolding. The repository already contains `pyproject.toml` with setuptools discovery for `app*`, `agent*`, `watchdog*`; `app/config.py` (`pydantic-settings`); `app/db.py` (async engine + session factory); `migrations/` with an initial revision claiming all 13 tables; `app/services/job_queue.py` implementing `SELECT FOR UPDATE SKIP LOCKED`; three FastAPI entrypoints with `/health`; `structlog` in `app/logging.py`; `sentry_sdk.init` in `app/main.py`, `agent/main.py`, and `watchdog/main.py`; and `.github/workflows/ci.yml` running `pip install -e ".[dev]"` plus `pytest`. [VERIFIED: codebase]

Planning should focus on **closing verification gaps** against PLAT-01–PLAT-08 and the five Phase 1 success criteria in `ROADMAP.md`: documented developer install path, parity between local and CI test execution, fast-fail configuration semantics, migration fidelity to all ORM models, **proven** concurrent job claiming, Railway-meaningful health differentiation, consistent structured logging fields across services, and Sentry initialization behavior that is explicit per environment (including tests).

**Primary recommendation:** Treat Phase 1 plans as a **checklist-driven audit**: for each PLAT-* requirement, add or extend automated checks (pytest, CI job steps, optional `alembic check` / metadata-vs-revision diff) and minimal code changes only where the baseline diverges from locked constraints (`AGENTS.md`, C-01–C-17, `.kiln` docs).

<phase_requirements>
## Phase requirements

| ID | Description (from `REQUIREMENTS.md`) | Research support |
|----|--------------------------------------|------------------|
| PLAT-01 | Documented editable install; full pytest locally and in CI | Gap: no root `README.md`; CI has no Postgres service — safe today only while tests stay non-DB or mock-only. |
| PLAT-02 | pydantic-settings; fast failure when required vars missing | `Settings` enforces `DATABASE_URL` + `SENTRY_DSN`. Gap: service entrypoints use `os.environ.get("SENTRY_DSN", "")` for Sentry, bypassing `Settings` for that one concern. |
| PLAT-03 | Async SQLAlchemy + sessions for all ORM modules; one Postgres | `app/db.py` + models package present; engine uses `pool_pre_ping=True`. |
| PLAT-04 | Alembic `upgrade head` maintains all tables for pipeline, agent, watchdog | `migrations/env.py` imports full model set; `001_initial_schema.py` documents 13 tables. Gap: CI does not run `alembic upgrade head` or drift detection. |
| PLAT-05 | Job queue concurrent claim/complete via `SKIP LOCKED` (or documented equivalent) | Implemented in `app/services/job_queue.py`. Gap: **no `claim()` unit test**; no concurrency/integration test proving single ownership under parallel workers. |
| PLAT-06 | Health endpoints suitable for Railway; unhealthy distinguishable | All three apps expose `GET /health` → `{"status":"ok"}`. Gap: no dependency-aware health (DB, loop status) — weak alignment with roadmap criterion 4. |
| PLAT-07 | Structured JSON logs with `component`, `status`, `error_type`, `context` on meaningful transitions | `app/logging.py` configures JSON structlog; `get_logger` pre-binds keys (often `null`). Gap: call sites may omit fields; **watchdog package does not use structlog at all** (grep: no matches). |
| PLAT-08 | Sentry initialized on all three entrypoints | All three call `sentry_sdk.init`. [CITED: https://docs.sentry.io/platforms/python/configuration/options/] — if DSN is not set, the SDK does not send data; explicit `dsn` overrides env. Gap: tests do not assert init wiring; watchdog has no shared logging/Sentry test beyond import-level checks. |
</phase_requirements>

## Standard stack

### Core

| Library | Version (declared) | Purpose | Why standard |
|---------|-------------------|---------|--------------|
| Python | `>=3.12` (`pyproject.toml`) | Runtime | Matches `AGENTS.md` / CI pin 3.12 [VERIFIED: pyproject.toml, ci.yml] |
| FastAPI + Uvicorn | `>=0.110` / `>=0.27` | HTTP services | Railway + ASGI norm [VERIFIED: pyproject.toml] |
| SQLAlchemy [asyncio] + asyncpg | `>=2.0` / `>=0.29` | Async ORM + driver | Single-DB async pattern [VERIFIED: app/db.py] |
| Alembic | `>=1.13` | Migrations | Required for PLAT-04 [VERIFIED: migrations/] |
| pydantic-settings | `>=2.0` | Typed env config | PLAT-02 [VERIFIED: app/config.py] |
| structlog | `>=23.0` | JSON logging | PLAT-07 [VERIFIED: app/logging.py] |
| sentry-sdk | `>=2.0` | Error tracking | PLAT-08 [VERIFIED: three main.py] |
| pytest + pytest-asyncio | dev extra | Test runner | PLAT-01 [VERIFIED: pyproject.toml] |

**Version verification:** Registry queries were not run in this session (host Python 3.14 + PEP 668 blocked `pip install` without a venv). Treat `pyproject.toml` lower bounds as declared; planner should confirm current minors in a 3.12 venv before pinning upgrades.

### Supporting

| Library | Purpose | When to use |
|---------|---------|-------------|
| httpx | ASGI tests, HTTP clients | Health route tests, integration [VERIFIED: tests] |

### Alternatives considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Postgres `SKIP LOCKED` queue | Redis / SQS | Violates documented ADR-style “Postgres queue” pattern in codebase docstrings [VERIFIED: app/services/job_queue.py] — do not replace in Phase 1 without architecture change. |

## Brownfield gap analysis (baseline → PLAT / success criteria)

| Area | Evidence it exists | Likely gap for planning |
|------|---------------------|-------------------------|
| **Install / docs** | `AGENTS.md` commands; `.env.example`; `pyproject.toml` | No `README.md` at repo root [VERIFIED: glob]; onboarding story is fragmented (PLAT-01 / success #1). |
| **CI vs local** | `ci.yml` mirrors install + pytest env vars | CI does **not** start Postgres; `DATABASE_URL` points at `localhost:5432` [VERIFIED: ci.yml] — fragile if future tests open real connections. |
| **Settings** | `Settings` requires `DATABASE_URL`, `SENTRY_DSN` | Watchdog intentionally avoids `Settings` (C-07); pipeline/agent Sentry uses `os.environ`, not `Settings.SENTRY_DSN` — document and optionally unify **without** breaking C-07. |
| **Migrations** | `001_initial_schema.py` + `env.py` model import | No automated “models == revision” check in CI; planner should add a wave-0 or phase task (e.g. `alembic check` or compare `Base.metadata` to DB after upgrade). |
| **Job queue** | `SKIP LOCKED` in `claim()` | Tests mock DB; **no test for `claim()`**; no concurrency proof (PLAT-05 / success #3). |
| **Health** | Static JSON OK | Railway can hit `/health` [VERIFIED: railway.toml] but cannot distinguish DB down vs up (success #4). |
| **Logging** | Pipeline/agent use structlog | Watchdog: no structlog; PLAT-07 “each service” vs C-07 needs a pattern (e.g. duplicate minimal JSON logger in `watchdog/` without importing `app.logging`). |
| **Sentry** | `sentry_sdk.init` in all mains | Empty/missing DSN: SDK sends nothing [CITED: Sentry Python options — `dsn`]. `PLAT-08` wording (“test exceptions capturable”) implies tests should validate init side effects or use Sentry test utilities — currently shallow. |

## Architecture patterns

### Recommended approach for this phase (verify-first)

1. **Requirement × artifact matrix** — For PLAT-01–08, list: code path, test file, CI step, manual operator check.
2. **Minimal prod behavior changes** — Prefer extending tests and health JSON schema over large refactors.
3. **Watchdog boundary** — Any shared logging/Sentry helpers for watchdog must live under `watchdog/` (or duplicated thin wrapper), never `app.*`.

### Pattern: Postgres queue claim in one transaction

**What:** `claim()` runs a `SELECT … FOR UPDATE SKIP LOCKED`, mutates the row to `running`, and relies on the caller’s session transaction.  
**When:** Any worker loop dequeuing `job_queue`.  
**Pitfall:** Callers must commit/rollback explicitly; `get_session()` commits on success — integration tests should mirror real caller patterns.  
[VERIFIED: app/services/job_queue.py]

### Anti-patterns to avoid

- **Importing `app.config` in watchdog** to “fix” settings — violates C-07 [VERIFIED: gsd-project-context / AGENTS.md].
- **Replacing health checks with deep DB checks without defining “degraded” semantics** — Railway may kill processes; align `restartPolicyType` with health design [VERIFIED: railway.toml].
- **Silent `sentry_sdk.init()` with fake DSN in prod** — PLAT-02 expects missing secrets to fail fast for pipeline **app** startup via `Settings`, not for optional integrations — clarify which services must hard-fail on missing DSN in production.

## Don’t hand-roll

| Problem | Don’t build | Use instead | Why |
|---------|-------------|-------------|-----|
| JSON logging | Custom `print`/`json.dumps` | structlog processors already in `app/logging.py` | Consistent field shapes for agent diagnosis [VERIFIED: app/logging.py] |
| Migrations | Raw SQL-only drift | Alembic revisions + autogenerate workflow | PLAT-04 traceability |
| Distributed locks for jobs | Ad-hoc polling | Keep `SKIP LOCKED` pattern | Battle-tested for Postgres job queues [ASSUMED: common pattern; implementation verified in repo] |

## Common pitfalls

### Pitfall 1: CI passes while integration assumptions are false

**What goes wrong:** Tests use mocks; CI has no Postgres; later phases add DB integration tests and CI breaks silently until merge.  
**Why:** `DATABASE_URL` in CI targets localhost without a service container.  
**How to avoid:** Add `services: postgres` in GitHub Actions **or** strict test tiers (`unit` vs `integration`) with documented local Postgres for integration.  
**Warning signs:** New tests hang or skip on DB connection errors.

### Pitfall 2: Health check always “ok” during partial outages

**What goes wrong:** Railway reports healthy while dashboard cannot reach DB.  
**Why:** Static `/health` response.  
**How to avoid:** Add optional `db: true/false` field and HTTP 503 policy **only if** ops agree on restart behavior; document in ROADMAP success criterion terms.

### Pitfall 3: Structured log field drift

**What goes wrong:** `AGENTS.md` requires fields that many call sites omit; watchdog logs unstructured.  
**Why:** structlog does not enforce per-event schema.  
**How to avoid:** Spot-audit high-traffic modules; add a small helper `log_state(component, status, **context)` or lint/sample tests on JSON output for critical paths.

### Pitfall 4: Sentry double-init or env bypass

**What goes wrong:** Future code path calls `init` twice or reads DSN from two sources inconsistently.  
**Why:** Today `Settings` and `os.environ` both exist for Sentry.  
**How to avoid:** Single initialization function per process, documented in planner tasks.

## Code examples

### Sentry DSN optional behavior (official)

From Sentry Python configuration options: the DSN tells the SDK where to send events; **if this option is not set, the SDK will just not send any data**; explicit `dsn` takes precedence over `SENTRY_DSN`.  
[CITED: https://docs.sentry.io/platforms/python/configuration/options/]

### JSON log shape (existing test pattern)

`tests/unit/test_logging.py` demonstrates asserting parsed JSON includes `component` and `status` when passed explicitly — extend similar assertions for critical pipeline events.  
[VERIFIED: tests/unit/test_logging.py]

## State of the art

| Old approach | Current approach | Notes |
|--------------|------------------|-------|
| sync SQLAlchemy + psycopg2 | async SQLAlchemy 2 + asyncpg | Matches `app/db.py` [VERIFIED] |
| implicit env defaults for secrets | pydantic-settings required fields | `DATABASE_URL` + `SENTRY_DSN` required [VERIFIED: app/config.py] |

## Assumptions log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | Concurrent `claim()` calls in separate sessions cannot double-claim the same job row when committed correctly | Job queue | Duplicate work or stuck jobs — needs integration proof |
| A2 | Current test suite does not require a live Postgres listener on CI | CI | CI could fail when integration DB tests are added |

**If empty:** N/A — table lists `[ASSUMED]` items.

## Open questions

1. **Should `/health` ever return non-200 when DB is unreachable?**  
   - What we know: Railway uses `/health` for liveness-style checks [VERIFIED: railway.toml].  
   - What’s unclear: desired restart semantics vs degraded operation.  
   - Recommendation: decide in PLAN with ops input; document in success criterion #4 terms.

2. **Should `SENTRY_DSN` remain required in `Settings` for local dev?**  
   - What we know: tests use fake DSN via `conftest.py` [VERIFIED].  
   - What’s unclear: whether production-only strictness is preferred.  
   - Recommendation: align `Settings` and `sentry_sdk.init` so validation story matches PLAT-02.

3. **Watchdog structured logging without importing `app.logging`?**  
   - What we know: watchdog has zero structlog usage [VERIFIED: grep].  
   - What’s unclear: duplicate config vs shared neutral package.  
   - Recommendation: smallest duplicate `watchdog/logging_config.py` mirroring JSON shape.

## Environment availability

**Step 2.6 note:** Probed in this session: **Python 3.14** on PATH; `pip install -e ".[dev]"` failed under **PEP 668** (externally managed environment). Project requires **3.12+** [VERIFIED: pyproject.toml]; CI pins **3.12** [VERIFIED: ci.yml].

| Dependency | Required by | Available (this session) | Version | Fallback |
|------------|-------------|----------------------------|---------|----------|
| Python 3.12+ | pyproject / CI | Partial (3.14 present; not 3.12) | 3.14.3 | Use `python3.12` + venv in docs |
| pip editable install | PLAT-01 | Blocked without venv | PEP 668 | Document `python -m venv .venv` |
| PostgreSQL | Future integration tests / alembic online | Not probed as running | — | Docker / local Postgres per `.env.example` |
| GitHub Actions ubuntu | CI | ✓ (implicit) | ubuntu-latest | — |

**Missing dependencies with no fallback:**

- None identified for *writing* research; **developers** need a 3.12+ venv for faithful local runs.

## Validation architecture

> Nyquist / Dimension 8 — how Phase 1 completion is **verified** (not just implemented).

### Test framework

| Property | Value |
|----------|-------|
| Framework | pytest (>=8) + pytest-asyncio (`asyncio_mode = auto`) [VERIFIED: pyproject.toml] |
| Config file | `[tool.pytest.ini_options]` in `pyproject.toml` |
| Quick run command | `pytest tests/unit/ -q --tb=short` [ASSUMED: fast slice; adjust if markers added] |
| Full suite command | `pytest` (per `AGENTS.md` / CI) |

### Phase requirements → test map

| Req ID | Behavior to prove | Test type | Automated command | File exists? |
|--------|-------------------|-----------|-------------------|--------------|
| PLAT-01 | Editable install + tests runnable | CI + doc review | GitHub Actions `pip install -e ".[dev]"` + `pytest` | ✅ ci.yml |
| PLAT-02 | Missing required env → ValidationError | unit | `pytest tests/unit/test_config.py -q` | ✅ |
| PLAT-03 | Engine URL asyncpg; session factory | unit | `pytest tests/unit/test_db.py -q` | ✅ |
| PLAT-04 | Migrations apply to schema | integration / CI step | `DATABASE_URL=… alembic upgrade head` (add to CI or manual gate) | ❌ not in CI yet |
| PLAT-05 | No duplicate claims under concurrency | integration (2+ sessions) | New test module e.g. `tests/integration/test_job_queue_concurrency.py` | ❌ |
| PLAT-06 | `/health` 200 + JSON | unit (ASGI) | `pytest tests/unit/test_app_main.py tests/unit/test_agent_main.py tests/unit/test_watchdog_main.py` | ✅ |
| PLAT-07 | JSON logs contain required keys when emitted | unit + sampling | `pytest tests/unit/test_logging.py`; extend + watchdog coverage | ⚠️ partial |
| PLAT-08 | Sentry `init` invoked / client configured | unit (mock `sentry_sdk.init`) | New tests on each `main.py` | ❌ |

### Roadmap success criteria → verification

| # | Success criterion | Verification |
|---|-------------------|--------------|
| 1 | Documented install; pytest local + CI | README (or `AGENTS.md` pointer) + green CI workflow |
| 2 | Missing required settings → immediate validation errors | `test_config.py` + manual: unset `DATABASE_URL` and attempt `Settings()` |
| 3 | Single Postgres; alembic head; async sessions; concurrent job claiming | `alembic upgrade head` on clean DB; **new** concurrency test for `claim()` |
| 4 | Railway-suitable health; unhealthy distinguishable | Extend health payload and/or docs; contract test on JSON schema |
| 5 | Structlog fields + Sentry on all three entrypoints | Log JSON audit; optional `sentry_sdk.Hub`/`client` assertions in tests; align watchdog logging |

### Sampling rate (recommended for execution phase)

- **Per task commit:** `pytest tests/unit/test_<module>.py -q` for touched areas  
- **Per wave merge:** full `pytest`  
- **Phase gate:** full `pytest` + `alembic upgrade head` against disposable Postgres + manual smoke: start three uvicorn processes with test env

### Wave 0 gaps

- [ ] Postgres service (or documented local-only integration tier) for CI  
- [ ] `alembic upgrade head` in CI or explicit “manual gate” checklist  
- [ ] Integration test: concurrent `claim()`  
- [ ] Unit tests: `claim()` happy path (even with mocked execute returning a row)  
- [ ] Sentry init tests for each service entrypoint  
- [ ] Watchdog structured logging parity (PLAT-07)  

## Security domain

### Applicable ASVS categories (Phase 1 scope)

| ASVS category | Applies | Standard control |
|---------------|---------|------------------|
| V2 Authentication | No (not in this phase) | — |
| V3 Session | No | — |
| V4 Access control | Minimal (future dashboard auth) | — |
| V5 Input validation | Yes | pydantic-settings for env; FastAPI request validation elsewhere [VERIFIED: stack] |
| V7 Error handling / logging | Yes | No secrets in log `context`; review `send_alert` / logs for PII [VERIFIED: need audit in execution] |
| V12 Secure logging | Yes | Structured fields; avoid logging full API keys [ASSUMED: policy] |

### Threat patterns

| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Misconfiguration / missing secrets | Elevation? | Fail fast on required settings (PLAT-02) [VERIFIED: test_config] |
| Logging sensitive data | Information disclosure | Code review + tests sampling log output for redaction |

## Sources

### Primary (HIGH confidence)

- Repository files: `pyproject.toml`, `app/config.py`, `app/db.py`, `app/logging.py`, `app/services/job_queue.py`, `app/main.py`, `agent/main.py`, `watchdog/main.py`, `watchdog/monitor.py`, `migrations/env.py`, `migrations/versions/001_initial_schema.py`, `.github/workflows/ci.yml`, `tests/**`, `railway.toml`, `.env.example`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
- [CITED: https://docs.sentry.io/platforms/python/configuration/options/] — DSN / send behavior

### Secondary (MEDIUM confidence)

- `.cursor/rules/gsd-project-context.md` — conventions and stack narrative (synced from codebase map)

### Tertiary (LOW confidence)

- PostgreSQL `SKIP LOCKED` concurrency semantics under load — implementation present; formal proof deferred to integration tests (A1)

## Metadata

**Confidence breakdown:**

- Standard stack: **HIGH** — read from `pyproject.toml` and imports  
- Architecture / gaps: **HIGH** — file-level audit  
- Pitfalls: **MEDIUM** — mix of repo evidence and common CI/ops patterns  

**Research date:** 2026-04-06  
**Valid until:** ~2026-05-06 (revisit if CI, health, or logging design changes)

---

## RESEARCH COMPLETE

- **Phase:** 1 — Platform, data & CI (brownfield gap analysis)  
- **File created:** `.planning/phases/01-platform-data-ci/01-RESEARCH.md`  
- **Key findings:**
  - Baseline already covers pyproject, Settings, async DB, Alembic, job queue pattern, `/health`, structlog (app/agent), Sentry on three mains, and CI pytest.
  - Largest verification gaps: **no README**, **CI without Postgres / alembic**, **job queue lacks `claim` + concurrency tests**, **static health checks**, **watchdog lacks structlog**, **Sentry/settings split across `os.environ` vs `Settings`**.
  - Nyquist Dimension 8: map each PLAT-* to an automated command or explicit manual gate; add Wave 0 items before feature work.
- **Ready for planning:** Yes — `gsd-planner` can derive PLAN.md tasks directly from the gap table and Validation Architecture section.
