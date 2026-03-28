<!-- status: complete -->
# Pitfalls & Anti-Patterns

Known gotchas, fragile areas, and mitigations for the UCC Lead Generation Platform.

---

### PF-001: Compliance Gate Bypass via Early Return
- **Area**: `app/compliance/gate.py`
- **Issue**: Any `return ComplianceResult(passed=True)` inserted above or outside the 4-layer sequential loop silently bypasses the entire compliance check. This can happen when adding error-handling shortcuts or "fast paths" for test data.
- **Impact**: Non-compliant leads exported to GHL. TCPA violations: $500–$1,500 per call/text. Catastrophic legal exposure.
- **Resolution**: The gate orchestrator function must have exactly one success return path, which is only reached after all 4 layers pass. Add a negative test that verifies no code path reaches export without a compliance_checks row for every layer.
- **Prevention**: Negative testing (M5 AC explicitly requires this). Code review rule: any PR touching `gate.py` requires a test proving the bypass does not exist.

### PF-002: Enrichment Cache TTL or Deletion
- **Area**: `app/enrichment/cache.py`, any Alembic migration touching `enrichment_cache`
- **Issue**: Adding an `expires_at` column or any `DELETE FROM enrichment_cache` statement in migrations, cron jobs, or cleanup scripts violates C-08 (indefinite data retention).
- **Impact**: Re-billing for enrichment API calls on already-processed entities. At $0.05–$1.50/record this accumulates rapidly. Also invalidates the "permanent cache prevents duplicate billing" architecture guarantee.
- **Resolution**: Remove any TTL column, scheduled deletion job, or cleanup migration immediately. Cache writes are insert-only.
- **Prevention**: No `DELETE` statement may reference `enrichment_cache`. No migration may add an `expires_at` or similar column to this table.

### PF-003: Watchdog Importing from app/ or agent/
- **Area**: `watchdog/` package (all files)
- **Issue**: Adding `from app.models.operations import AgentHeartbeat` or any other import from `app/` or `agent/` into watchdog code creates a hidden runtime dependency. If the pipeline service crashes and leaves shared memory or file state inconsistent, the watchdog may also fail.
- **Impact**: The independent deadman switch is no longer independent. Watchdog fails precisely when it needs to work (when pipeline/agent is down). C-07 violated.
- **Resolution**: Watchdog connects to Postgres using its own direct `asyncpg` or minimal SQLAlchemy connection. It queries `agent_heartbeat` by raw SQL or its own minimal model definition — never importing from `app/`.
- **Prevention**: `tests/unit/test_watchdog_isolation.py` must verify `watchdog.checker` and `watchdog.alerter` have no imports from `app` or `agent` namespaces (inspect module `__file__` or use `importlib` audit).

### PF-004: Shared AsyncSession Across Coroutines
- **Area**: Any async function using `AsyncSession` (`app/db.py` pattern consumers)
- **Issue**: Passing a single `AsyncSession` instance into multiple `asyncio.gather()` coroutines causes `sqlalchemy.exc.MissingGreenlet` or silent data corruption because SQLAlchemy async sessions are not concurrency-safe.
- **Impact**: Data corruption, duplicate writes, or cryptic runtime errors that are hard to diagnose.
- **Resolution**: Each coroutine that needs database access must open its own session via `async with async_session() as session`. Never pass a session into `gather()`.
- **Prevention**: Pattern P-010. Sessions are function-scoped. If a function signature accepts `session: AsyncSession`, it is the sole owner of that session for the duration of the call.

### PF-005: Partially Enriched Lead Reaching Export Queue
- **Area**: `app/enrichment/waterfall.py`, `app/export/` pipeline wiring
- **Issue**: A lead is written to the job_queue for export while `enrichment_status != "complete"` — for example if the waterfall executor catches an exception and returns a partial result, or if the status column is updated before all sources finish.
- **Impact**: Leads exported to GHL with missing phone, email, or revenue data. Downstream campaign quality degrades. Violates C-03.
- **Resolution**: Export queue insertion must assert `lead.enrichment_status == "complete"`. Waterfall executor must only update `enrichment_status` to `complete` if all required fields are populated. Failed enrichments go to `enrichment_retry_queue`.
- **Prevention**: Integration test that forces a mid-waterfall failure and verifies the lead is in `enrichment_retry_queue`, not the export queue.

### PF-006: Internal DNC Entry Deleted or Updated by Automated Code
- **Area**: `app/compliance/internal_dnc.py`, any migration or cleanup job
- **Issue**: Any `DELETE FROM internal_dnc` or `UPDATE internal_dnc SET ... WHERE ...` issued by automated pipeline code violates C-12. This includes "deduplication cleanup" jobs that might merge or remove duplicate DNC entries.
- **Impact**: Previously opted-out contacts may be called again. TCPA liability. Irrevocable legal violation.
- **Resolution**: The only write operation on `internal_dnc` is `INSERT`. Any reversal goes through a separate manager audit trail mechanism — never an automated delete.
- **Prevention**: No `DELETE` or `UPDATE` statement may reference `internal_dnc` in application code. Migrations must never drop or truncate this table.

### PF-007: GHL-Specific Import in Pipeline Code
- **Area**: Any file in `app/` except `app/export/ghl_adapter.py`
- **Issue**: Importing `GHLAdapter` directly into pipeline code (e.g., `app/export/webhook_handler.py` importing from `ghl_adapter.py` instead of using the abstract interface) locks the platform to GHL and violates C-06.
- **Impact**: Swapping campaign platforms requires hunting down and changing every import, defeating the adapter pattern.
- **Resolution**: All pipeline code uses `CampaignPlatformAdapter` from `app/export/adapter.py`. The concrete adapter is injected at startup. Webhook handler receives a `CampaignPlatformAdapter` instance.
- **Prevention**: M6 AC explicitly states "pipeline code imports only the abstract adapter." Grep for `from app.export.ghl_adapter` in any file outside `ghl_adapter.py` itself — flag as violation.

### PF-008: APScheduler Jobs Using Sync Functions in Async Context
- **Area**: `app/scheduler/jobs.py`, APScheduler configuration
- **Issue**: APScheduler 3.x `AsyncIOScheduler` requires async job functions. If a sync function is registered as a job and it makes database calls, it will block the event loop or fail silently depending on the SQLAlchemy driver.
- **Impact**: Scheduled scraping jobs silently skip or deadlock. The pipeline appears healthy but no data flows.
- **Resolution**: All APScheduler job functions must be `async def`. Use `AsyncIOScheduler`. Never register a sync function that does I/O.
- **Prevention**: Convention: all job functions in `app/scheduler/jobs.py` are `async def`. CI lint rule to flag sync functions in this module.

### PF-009: Missing Scraper Run Log Entry on Failure
- **Area**: `app/scrapers/states/*.py`, `app/scrapers/base.py`
- **Issue**: If a scraper raises an exception that is caught at a higher level, the `scraper_runs` table entry may never be written (or written with status "running" instead of "failed"). The self-healing agent uses `scraper_runs` as its primary signal for scraper health — missing entries are invisible failures.
- **Impact**: Self-healing agent cannot detect or repair the broken scraper. Tier 1 states silently stop producing data.
- **Resolution**: Scraper base class must write a `scraper_runs` entry in a `try/finally` block. Status is set to "failed" with `error_detail` on exception, "success" on completion. This must execute even if the scraper function raises.
- **Prevention**: Base class pattern enforces this. Unit test verifies that a scraper that raises still produces a `scraper_runs` row with `status="failed"`.

### PF-010: LangGraph State Not Persisted to Postgres Checkpointer
- **Area**: `agent/graph.py`, LangGraph checkpointer configuration
- **Issue**: LangGraph defaults to in-memory state. If the Postgres checkpointer is not explicitly configured and passed to the graph compilation, agent state is lost on any service restart. Railway restarts the service on failure — state loss means the agent starts from scratch every time.
- **Impact**: Self-healing agent loses its repair context, re-detects the same failures, creates duplicate GitHub issues (despite the dedup check on open issues).
- **Resolution**: `agent/graph.py` must configure `PostgresSaver` (or `AsyncPostgresSaver`) and pass it as `checkpointer=` to `graph.compile()`. Verify with an integration test that kills and restarts the agent mid-graph and confirms state survives.
- **Prevention**: M8 AC explicitly requires "agent state survives service restart." Integration test for this is mandatory.

### PF-011: Function Exceeding 50 Lines (C-01 Violation)
- **Area**: All modules — most likely in complex scraper parse functions, waterfall executor, or LangGraph node handlers
- **Issue**: A single function grows beyond 50 lines as business logic accumulates. Common growth vectors: adding error cases to parse functions, adding logging, adding retry logic inline.
- **Impact**: Violates C-01. AI agents struggle to reason about, modify, or test long functions reliably. M10 audit will catch this but fixing it late is costly.
- **Resolution**: Decompose immediately. Parsing a state SOS response: one function to fetch, one to parse the HTML table, one to map rows to filing models. Each under 50 lines.
- **Prevention**: M10 deliverable explicitly includes a module audit. Establish the pattern early in M1 so it propagates. If a function needs a comment "# --- section ---", it is already too long.

### PF-012: Environment Variable Missing in Railway but Present Locally
- **Area**: Railway deployment configuration, `app/config.py`
- **Issue**: A new required environment variable is added to `Settings` but not added to the Railway service's environment variables. Local dev works because `.env` is present. The Railway deploy fails at startup with a `ValidationError` that may not surface clearly in Railway logs.
- **Impact**: Service startup failure in production. May affect all three services simultaneously if they share the same settings module.
- **Resolution**: The environment variable reference file (M1 deliverable) must be updated every time a new var is added to `Settings`. Railway env vars must be audited against this file before deployment.
- **Prevention**: `.env.example` file maintained in sync with `Settings`. M10 checklist explicitly validates all required vars are set in Railway.

### PF-013: Smoke Tests Running on Push (CI Timing)
- **Area**: `.github/workflows/ci.yml`, `tests/smoke/`
- **Issue**: Smoke tests hit live SOS portals. If triggered on every push/PR, they hit portals multiple times per day, risking IP bans on rate-limited states (especially Tier 3). They also make CI slow and flaky on portal unavailability.
- **Impact**: Tier 3 state IP bans. Flaky CI that blocks PRs on infrastructure issues unrelated to code changes. Violates the "smoke tests run on schedule, not on push" requirement (M2 AC).
- **Resolution**: Smoke tests are in `tests/smoke/` and excluded from the standard CI `pytest` invocation via `pytest -m "not smoke"`. A separate scheduled GitHub Actions workflow runs them daily.
- **Prevention**: `pyproject.toml` marks smoke tests with `@pytest.mark.smoke`. CI workflow explicitly excludes them.

### PF-014: DataMerch Gate Silently Skipped Without Warning Log
- **Area**: `app/compliance/datamerch.py`, `app/compliance/gate.py`
- **Issue**: When `DATAMERCH_API_KEY` is not set, the gate silently falls through to the UCC pattern fallback without emitting a warning. The manager has no visibility that Gate 2 is operating in degraded mode.
- **Impact**: Compliance audit trail shows Gate 2 as "passed" when it was actually skipped. Misrepresents compliance posture. Violates C-15.
- **Resolution**: A structlog `warning` must be emitted on every lead when DataMerch is unconfigured. The `compliance_checks` row for Gate 2 must record `gate_name="datamerch_fallback"` rather than `"datamerch"`.
- **Prevention**: M5 AC explicitly requires the warning log. Unit test verifies the warning is emitted and the audit log uses the fallback gate name.
