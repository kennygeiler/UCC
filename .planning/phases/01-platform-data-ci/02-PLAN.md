---
phase: 01-platform-data-ci
plan: "02"
type: execute
wave: 2
depends_on:
  - "01"
requirements_addressed:
  - PLAT-03
  - PLAT-05
  - PLAT-07
autonomous: true
files_modified:
  - tests/integration/test_db_postgres.py
  - tests/integration/test_job_queue_concurrency.py
  - tests/unit/test_logging.py
  - pyproject.toml
must_haves:
  truths:
    - "Integration test opens async session against CI Postgres (post-migrations) and executes a trivial query without error."
    - "Two concurrent workers cannot claim the same pending job row; second claimant gets None when only one job exists."
    - "Structured log JSON from pipeline logging helpers includes required keys when exercised in tests (extend existing patterns)."
  artifacts:
    - path: tests/integration/test_job_queue_concurrency.py
      provides: "PLAT-05 concurrency proof"
    - path: tests/integration/test_db_postgres.py
      provides: "PLAT-03 live session smoke"
---

<objective>
Add automated proof for async DB sessions against real Postgres, concurrent job claiming, and structured logging field coverage for app/agent—without changing production entrypoints in this plan.

Purpose: Close gaps identified in `01-RESEARCH.md` for PLAT-03, PLAT-05, PLAT-07 (app/agent). Sentry test assertions ship in plan `03` after Settings reconciliation.

Output: New/extended tests under `tests/integration/` and `tests/unit/`; optional pytest marker registration in `pyproject.toml`.
</objective>

<context>
@app/db.py
@app/services/job_queue.py
@app/models/job.py
@app/logging.py
@tests/unit/test_job_queue.py
@tests/unit/test_logging.py
@tests/conftest.py
</context>

<threat_model>
## Trust boundaries

| Boundary | Description |
|----------|-------------|
| Test process → Postgres | Uses CI/local test credentials only; tests must not log connection strings or row payloads containing PII. |

## STRIDE register

| Threat ID | Category | Component | Disposition | Mitigation |
|-----------|----------|-----------|-------------|------------|
| T-02-01 | Information disclosure | Integration test logs | mitigate | Task 1–2: use minimal fixtures; avoid logging full `DATABASE_URL` or job payloads with real business data—use synthetic job_type/payload. |
| T-02-02 | Denial of service | Concurrency test | accept | Bounded parallelism (2 tasks); single job row; short-lived. |
| T-02-03 | Repudiation | Missing test evidence | mitigate | Task 2: assert exactly one `running` job after concurrent claims. |
</threat_model>

<tasks>

<task type="auto">
  <name>Task 1: Integration — async session smoke after migrations (PLAT-03)</name>
  <read_first>
    - `app/db.py` (`get_session`, engine disposal)
    - `tests/conftest.py` for existing env assumptions
  </read_first>
  <action>
    Add `tests/integration/test_db_postgres.py` that skips when `DATABASE_URL` is unset or clearly non-runnable (use `pytest.importorskip` or a marker `integration`). When run (CI after plan 01): acquire `get_session()` (or equivalent project pattern), execute `SELECT 1` or `SELECT COUNT(*) FROM job_queue` (table must exist post-alembic), assert success, dispose cleanly. Register marker `integration` in `pyproject.toml` under `[tool.pytest.ini_options]` if not present (`markers = ["integration: requires Postgres"]`). Document in test module docstring: run via full `pytest` in CI, not required for offline unit-only runs if team later splits jobs.
  </action>
  <acceptance_criteria>
    - File exists: `tests/integration/test_db_postgres.py`
    - `pytest tests/integration/test_db_postgres.py -q --tb=short` passes in CI after `alembic upgrade head` (plan 01); locally passes when `DATABASE_URL` points at migrated DB or test skips with documented reason.
  </acceptance_criteria>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Integration — concurrent `claim()` single-job ownership (PLAT-05)</name>
  <read_first>
    - `app/services/job_queue.py` (`claim`, `enqueue`, `complete`)
    - `app/models/job.py` (`JobQueue` columns)
  </read_first>
  <behavior>
    - Given one pending job, two overlapping async tasks each using **separate** `AsyncSession` instances from the session factory, when both call `claim` with overlapping `job_types` and commit in real transactions, exactly one returns a non-None job and the job row ends as `running` with one `worker_id`.
    - Second claim on empty queue returns None.
  </behavior>
  <action>
    Add `tests/integration/test_job_queue_concurrency.py` using real Postgres: `enqueue` one job in a setup transaction; then run two concurrent `claim` calls with `asyncio.gather` using independent sessions; assert one None and one non-None OR deterministic ordering with row-level lock behavior; assert DB has exactly one `running` job. Use unique `worker_id` strings. Clean up job row in teardown (complete or delete) to avoid polluting parallel tests. Mark `integration`.
  </action>
  <acceptance_criteria>
    - `pytest tests/integration/test_job_queue_concurrency.py -q --tb=short` passes in CI with Postgres.
  </acceptance_criteria>
</task>

<task type="auto">
  <name>Task 3: Unit — structured log required fields sampling (PLAT-07, app/agent)</name>
  <read_first>`tests/unit/test_logging.py`, `app/logging.py`</read_first>
  <action>
    Extend `test_logging.py` (or add focused test) to assert that when `get_logger("test_component").info("evt", status="ok", error_type=None, context={"k": "v"})` (or project’s binding pattern), captured output JSON includes keys `component`, `status`, `error_type`, `context` per `AGENTS.md`. Keep watchdog out of this task (plan 03). Avoid logging secrets in fixture context values.
  </action>
  <acceptance_criteria>
    - `pytest tests/unit/test_logging.py -q --tb=short` passes.
    - `grep -E "component|status|error_type|context" tests/unit/test_logging.py`
  </acceptance_criteria>
</task>

</tasks>

<verification>
Full `pytest` green in CI with Postgres (from plan 01).
</verification>

<success_criteria>
PLAT-03, PLAT-05, and PLAT-07 (app/agent logging) have automated evidence.
</success_criteria>

<output>
After completion, create phase summary for plan 02 per project convention.
</output>
