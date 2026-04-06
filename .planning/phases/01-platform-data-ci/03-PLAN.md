---
phase: 01-platform-data-ci
plan: "03"
type: execute
wave: 3
depends_on:
  - "02"
requirements_addressed:
  - PLAT-02
  - PLAT-06
  - PLAT-07
  - PLAT-08
autonomous: true
files_modified:
  - app/main.py
  - agent/main.py
  - watchdog/main.py
  - watchdog/logging_config.py
  - tests/unit/test_app_main.py
  - tests/unit/test_agent_main.py
  - tests/unit/test_watchdog_main.py
  - tests/unit/test_watchdog_logging.py
  - tests/unit/test_sentry_entrypoints.py
must_haves:
  truths:
    - "Pipeline and agent call `sentry_sdk.init` with DSN sourced from validated `Settings().SENTRY_DSN` (or single helper fed by Settings)—no silent bypass of pydantic-settings for those processes."
    - "Watchdog still does not import `app` or `agent`; Sentry DSN read from `os.environ` only; structured JSON logging added under `watchdog/` only."
    - "`GET /health` responses distinguish degraded vs healthy via explicit JSON fields (documented); HTTP status policy matches Railway liveness expectations (prefer 200 with `status` ok/degraded unless project chooses 503 for DB down—document in README if 503 used)."
    - "Watchdog logs at least one lifecycle event with required structlog fields using local config."
  artifacts:
    - path: watchdog/logging_config.py
      provides: "PLAT-07 without violating C-07"
    - path: app/main.py
      provides: "Settings-backed Sentry + health enrichment"
---

<objective>
Reconcile configuration and observability: pydantic-settings owns required secrets for pipeline/agent Sentry init, enrich health endpoints for Railway operators, and add watchdog structured logging without importing `app` or `agent`.

Purpose: Satisfy PLAT-02 (fast-fail Settings for app processes), PLAT-06 (meaningful health), PLAT-07 (all three services), PLAT-08 (consistent Sentry story per service boundary).

Output: Updated entrypoints, new `watchdog/logging_config.py`, extended health handlers, tests.
</objective>

<context>
@app/config.py
@app/db.py
@watchdog/main.py
@watchdog/monitor.py
@.cursor/rules/gsd-project-context.md (C-07)
Constraint **C-07**: `watchdog` MUST NOT import `app` or `agent`. Watchdog config remains env-based; do not import `Settings`.
</context>

<threat_model>
## Trust boundaries

| Boundary | Description |
|----------|-------------|
| Internet → `GET /health` | Unauthenticated; response must not expose secrets, stack traces, or detailed internal topology beyond coarse status. |
| Logs → log drain | Must not include API keys, DSNs, or manager email content in `context`. |
| Sentry → error backend | Configure to avoid PII in events (`send_default_pii=False`; scrub request data if added later). |

## STRIDE register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-03-01 | Information disclosure | Health endpoint | mitigate | Task 2: return booleans/enum-like strings only (`db: "up"|"down"`); no connection strings, no hostnames of third parties. |
| T-03-02 | Information disclosure | Structured logs | mitigate | Task 1: bind `context` with stable keys; never log `SENDGRID_API_KEY`, `DATABASE_URL`, or full DSN; review watchdog monitor for existing log lines. |
| T-03-03 | Information disclosure | Sentry PII | mitigate | Task 3: init with `send_default_pii=False` explicitly; document in code comment; no user emails in `set_user` without future compliance review. |
| T-03-04 | Elevation of privilege | Settings import at startup | mitigate | Task 3: `Settings()` instantiation remains fail-fast on missing `DATABASE_URL`/`SENTRY_DSN` for app/agent only—watchdog unchanged. |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Watchdog structured JSON logging — no app imports (PLAT-07, C-07)</name>
  <read_first>
    - `app/logging.py` (processors, JSON renderer—copy patterns, not imports)
    - `watchdog/main.py`, `watchdog/monitor.py`
  </read_first>
  <action>
    Add `watchdog/logging_config.py` implementing `configure_logging()` and `get_logger(component: str)` using `structlog` with JSON output analogous to pipeline (same key names for required fields). Call `configure_logging()` at start of `watchdog/main.py` before Sentry init. In `watchdog/monitor.py`, replace or augment `print`/plain logging with `get_logger("watchdog_monitor").info(...)` for at least: loop start, heartbeat check outcome (use `status`, `error_type`, `context` keys—use `error_type=None` where N/A). **Forbidden:** `from app.` or `from agent.` anywhere in watchdog package for this task.
  </action>
  <acceptance_criteria>
    - `grep -r "from app" watchdog/` and `grep -r "from agent" watchdog/` show no matches (or only unrelated historical—must be zero after change).
    - `pytest tests/unit/test_watchdog_main.py -q --tb=short` passes.
    - New `tests/unit/test_watchdog_logging.py` parses captured log line and asserts presence of `component`, `status`, `error_type`, `context` for a synthetic event.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 2: Health endpoints — observable DB / monitor state (PLAT-06)</name>
  <read_first>
    - `app/main.py`, `app/db.py` (`get_engine` or session execute)
    - `agent/main.py` (whether agent should check DB—uses app DB)
    - `watchdog/main.py` (global task reference for cancellation state)
    - `railway.toml` health paths if present
  </read_first>
  <action>
    **Pipeline `app/main.py`:** Implement async health handler that attempts a cheap DB check (e.g. `SELECT 1` via `async_engine.connect()` or session) with timeout; include JSON fields: `status` (`ok` if DB up, `degraded` if DB down—define clearly), `database` (`connected`/`unreachable`). Default HTTP status: keep **200** for process alive if Railway treats non-200 as restart (align with `01-RESEARCH.md` open question—prefer 200 + `status: degraded` to avoid restart loops; document in README). **Agent:** add same `database` check if agent uses shared DB. **Watchdog:** add `monitor` field (`running`/`stopped` or `loop` last tick if implemented minimally via module-level flag set in loop). Do not import `app` in watchdog—use raw SQLAlchemy async engine from env like `monitor.py` for DB check optional or omit DB field for watchdog if no shared schema need—prefer `monitor: "active"` based on asyncio task state without querying pipeline tables. Ensure unhealthy is **distinguishable** in JSON per roadmap.
  </action>
  <acceptance_criteria>
    - `pytest tests/unit/test_app_main.py tests/unit/test_agent_main.py tests/unit/test_watchdog_main.py -q --tb=short` passes with updated response shape assertions.
    - Health JSON includes at minimum: pipeline `{ "status", "database" }`; document field meanings in test docstrings or README health subsection.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 3: Reconcile Sentry init with Settings for app/agent; env-only for watchdog (PLAT-02, PLAT-08)</name>
  <read_first>
    - `app/main.py`, `agent/main.py`, `app/config.py`
    - `tests/unit/test_config.py` (env patterns for `Settings`)
    - `tests/unit/test_app_main.py`, `tests/unit/test_agent_main.py`, `tests/unit/test_watchdog_main.py`
  </read_first>
  <action>
    In `app/main.py` and `agent/main.py`: instantiate `Settings()` **before** `sentry_sdk.init` and pass `settings.SENTRY_DSN` to `sentry_sdk.init(dsn=..., send_default_pii=False)`. Remove redundant `os.environ.get("SENTRY_DSN", "")` for init in those files. Ensure import order avoids loading heavy routers before settings validation fails. **Watchdog:** keep `os.environ.get("SENTRY_DSN", "")` only (C-07); after Task 1, Sentry init follows `configure_logging()`. Extend unit tests so **all three** entrypoints prove Sentry wiring: patch `sentry_sdk.init` and import/reload the FastAPI app module (or call a documented factory) such that `init` runs once per process story—app/agent assert DSN matches `Settings()` when env is set; watchdog asserts `init` receives env DSN string. Do not send real events. Missing `SENTRY_DSN` must still fail fast when constructing `Settings()` for app/agent (existing `test_config.py` behavior preserved).
  </action>
  <acceptance_criteria>
    - `pytest tests/unit/test_config.py tests/unit/test_app_main.py tests/unit/test_agent_main.py tests/unit/test_watchdog_main.py -q --tb=short` passes.
    - `grep -n "sentry_sdk.init" app/main.py agent/main.py watchdog/main.py`
    - `grep "os.environ.get(\"SENTRY_DSN\"" app/main.py agent/main.py` returns no matches (watchdog may still use this pattern).
    - At least one test file asserts `sentry_sdk.init` was called for each of the three services (grep `sentry_sdk` in the three test modules or a new `tests/unit/test_sentry_entrypoints.py`).
  </acceptance_criteria>
</task>

</tasks>

<verification>
- Full `pytest` in CI.
- Manual one-liner optional: `curl -s localhost:8000/health | jq` shows new fields (document in SUMMARY).
</verification>

<success_criteria>
PLAT-02 satisfied for pipeline/agent Sentry path; PLAT-06 health distinguishes degradation; PLAT-07 covers watchdog; PLAT-08 consistent per-service init story; C-07 preserved.
</success_criteria>

<output>
After completion, create phase summary for plan 03 per project convention.
</output>
