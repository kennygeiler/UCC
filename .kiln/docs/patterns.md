<!-- status: complete -->
# Patterns & Quality Guide

## TL;DR
Key patterns: short single-purpose functions (<50 lines, C-01), platform-agnostic adapter for campaign output (C-06), Postgres SELECT FOR UPDATE SKIP LOCKED job queue (C-04/C-05). Known pitfalls: compliance gate bypass via short-circuit, enrichment cache TTL deletion violating C-08, watchdog importing from app/ breaking isolation (C-07). Test approach: pytest with unit/integration/smoke/contract tiers; every scraper has a smoke test; every module has a corresponding test file.

---

## Patterns

### P-001: Function Length Hard Limit
- **Category**: structure
- **Rule**: Every function must be under 50 lines including docstring and blank lines. No exceptions. Applies to all three services (app/, agent/, watchdog/).
- **Example**:
  ```python
  async def claim_job(session: AsyncSession, job_type: str) -> Job | None:
      """Claim the next available job of the given type using SKIP LOCKED."""
      stmt = (
          select(Job)
          .where(Job.job_type == job_type, Job.status == "pending")
          .order_by(Job.priority.desc(), Job.scheduled_at)
          .limit(1)
          .with_for_update(skip_locked=True)
      )
      result = await session.execute(stmt)
      job = result.scalar_one_or_none()
      if job:
          job.status = "running"
          job.started_at = datetime.utcnow()
      return job
  ```
- **Counter-example**: A function combining job claiming, payload parsing, business logic execution, error handling, and logging in one block — split each concern into its own function.

### P-002: Single-Purpose Modules
- **Category**: structure
- **Rule**: Each module (file) owns exactly one concern. Scraper modules only scrape. Compliance modules only check compliance. No cross-domain imports within the same service except through explicit interfaces.
- **Example**: `app/compliance/gate.py` imports `internal_dnc.py`, `datamerch.py`, `dnc_scrub.py`, `blacklist_alliance.py` — but never imports from `app/enrichment/` or `app/export/`.

### P-003: Docstrings on All Functions and Modules
- **Category**: structure
- **Rule**: Every function and every module must have a docstring. Docstring must describe what it does and any constraints or side effects. This is AI-maintainability infrastructure (C-01).
- **Example**:
  ```python
  """
  enrichment/waterfall.py — Generic waterfall executor for enrichment and compliance.

  Tries each source callable in order and returns the first successful result.
  Logs each attempt. Raises WaterfallExhausted if all sources fail.
  """

  async def run_waterfall(sources: list[Callable], input_data: dict) -> dict:
      """Try each source in order; return first success. Raise WaterfallExhausted on total failure."""
      for source in sources:
          try:
              return await source(input_data)
          except Exception as exc:
              log.warning("waterfall.source_failed", source=source.__name__, error=str(exc))
      raise WaterfallExhausted("All enrichment sources exhausted")
  ```

### P-004: Structured JSON Logging via structlog
- **Category**: error-handling
- **Rule**: Every meaningful state change emits a structlog JSON log event with required fields: `component`, `status`, and either `context` or `error_type`. Never use `print()` or stdlib `logging` directly.
- **Example**:
  ```python
  import structlog
  log = structlog.get_logger()

  log.info("scraper.run_complete",
      component="scraper",
      status="success",
      state="CA",
      records_found=142,
      context={"duration_seconds": 18.4}
  )

  log.error("enrichment.circuit_open",
      component="enrichment",
      status="halted",
      error_type="circuit_breaker_open",
      context={"source": "pdl", "error_rate": 0.27}
  )
  ```
- **Counter-example**: `print(f"Scraper done: {count} records")` — invisible to the self-healing agent, not machine-readable.

### P-005: Postgres Job Queue — SELECT FOR UPDATE SKIP LOCKED
- **Category**: data-flow
- **Rule**: All background work is enqueued in the `job_queue` table. Workers claim jobs using `SELECT FOR UPDATE SKIP LOCKED` inside an async SQLAlchemy session. Never use Redis, Celery, RabbitMQ, or Kafka (C-04, C-05).
- **Example**:
  ```python
  async def claim_next_job(session: AsyncSession, job_type: str) -> Job | None:
      """Claim the highest-priority pending job of the given type atomically."""
      stmt = (
          select(Job)
          .where(Job.job_type == job_type, Job.status == JobStatus.PENDING)
          .order_by(Job.priority.desc(), Job.scheduled_at.asc())
          .limit(1)
          .with_for_update(skip_locked=True)
      )
      result = await session.execute(stmt)
      return result.scalar_one_or_none()
  ```

### P-006: CampaignPlatformAdapter — Never Import Concrete Adapters in Pipeline Code
- **Category**: structure
- **Rule**: All pipeline code that exports leads imports only `CampaignPlatformAdapter` (the abstract interface from `app/export/adapter.py`). GHL-specific code lives exclusively in `app/export/ghl_adapter.py`. The concrete adapter is wired at application startup via dependency injection (C-06).
- **Example**:
  ```python
  # app/export/adapter.py
  from abc import ABC, abstractmethod

  class CampaignPlatformAdapter(ABC):
      @abstractmethod
      async def upsert_lead(self, lead: Lead) -> str: ...

      @abstractmethod
      async def enroll_in_campaign(self, external_id: str, tier: str) -> None: ...

      @abstractmethod
      async def get_disposition_updates(self, since: datetime) -> list[DispositionUpdate]: ...

      @abstractmethod
      async def parse_webhook_payload(self, raw: dict) -> DispositionUpdate | None: ...

  # pipeline code — correct
  from app.export.adapter import CampaignPlatformAdapter  # abstract only

  # pipeline code — WRONG
  from app.export.ghl_adapter import GHLAdapter  # never in pipeline code
  ```

### P-007: Compliance Gate — Sequential 4-Layer Enforcement
- **Category**: data-flow
- **Rule**: Compliance checks must execute in strict order: (1) Internal DNC, (2) DataMerch, (3) Federal/State DNC, (4) Blacklist Alliance. A failure at any layer immediately blocks the lead and writes the result to `compliance_checks`. No layer may be skipped except DataMerch when unconfigured (with mandatory warning log). There is no override, soft flag, or conditional bypass (C-02).
- **Example**:
  ```python
  async def run_compliance_gate(lead: Lead, session: AsyncSession) -> ComplianceResult:
      """Run all 4 compliance layers sequentially. Block on first failure."""
      layers = [
          ("internal_dnc", check_internal_dnc),
          ("datamerch", check_datamerch_or_fallback),
          ("dnc_scrub", check_federal_state_dnc),
          ("blacklist_alliance", check_blacklist_alliance),
      ]
      for gate_name, check_fn in layers:
          result = await check_fn(lead, session)
          await log_compliance_check(session, lead.id, gate_name, result)
          if not result.passed:
              return ComplianceResult(passed=False, blocked_by=gate_name)
      return ComplianceResult(passed=True)
  ```

### P-008: Enrichment Cache — Permanent, No TTL
- **Category**: data-flow
- **Rule**: All enrichment API results are written to `enrichment_cache` permanently. Never set a TTL or expiration. Never delete cache entries programmatically. A cache hit must include the `fetched_at` timestamp in the returned result. This prevents re-billing for the same entity (C-08).
- **Example**:
  ```python
  async def get_or_fetch(session: AsyncSession, source: str, key: str,
                          fetch_fn: Callable) -> dict:
      """Return cached enrichment result or fetch and cache it permanently."""
      cached = await get_cache(session, source, key)
      if cached:
          return {"data": cached.result_json, "fetched_at": cached.fetched_at, "from_cache": True}
      result = await fetch_fn(key)
      await write_cache(session, source, key, result)
      return {"data": result, "fetched_at": datetime.utcnow(), "from_cache": False}
  ```

### P-009: Circuit Breaker Per Enrichment Source
- **Category**: error-handling
- **Rule**: Each enrichment source is wrapped in a `pybreaker.CircuitBreaker` instance. When any breaker opens (>20% errors in 5 min), write a HALT event to `pipeline_events` and suspend export queue processing. Resume only when the self-healing agent confirms the source is healthy (C-03).
- **Example**:
  ```python
  import pybreaker

  pdl_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=300)

  @pdl_breaker
  async def fetch_from_pdl(key: str) -> dict:
      """Fetch enrichment data from People Data Labs with circuit breaker protection."""
      ...
  ```

### P-010: SQLAlchemy 2.0 Async Sessions — One Session Per Request/Job
- **Category**: async
- **Rule**: Create one `AsyncSession` per FastAPI request or per job execution. Never share a session across coroutines. Use `async with async_session() as session` and commit explicitly. Use `session.begin()` for transactions that should rollback on exception.
- **Example**:
  ```python
  # app/db.py
  from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

  engine = create_async_engine(settings.DATABASE_URL, echo=False)
  async_session = async_sessionmaker(engine, expire_on_commit=False)

  # usage
  async with async_session() as session:
      async with session.begin():
          job = await claim_next_job(session, "enrichment")
  ```

### P-011: pydantic-settings Configuration — Fail Fast on Missing Vars
- **Category**: error-handling
- **Rule**: All configuration comes from environment variables parsed by `pydantic-settings`. Required variables have no default. The settings object is instantiated at module import time, so missing vars cause an immediate startup failure with a clear error — never a silent `None` at runtime.
- **Example**:
  ```python
  from pydantic_settings import BaseSettings

  class Settings(BaseSettings):
      DATABASE_URL: str                  # required — no default
      GHL_API_KEY: str                   # required
      DATAMERCH_API_KEY: str | None = None  # optional — fallback activates (C-15)
      SENTRY_DSN: str | None = None

  settings = Settings()  # raises ValidationError at startup if DATABASE_URL missing
  ```

### P-012: Per-State Rate Limiter — Async Sleep with Jitter
- **Category**: async
- **Rule**: Every scraper call must go through the per-state rate limiter. Default: 1 request / 3 seconds. Tier 3: 1 request / 10 seconds. Add jitter (±20%) on every delay. Apply exponential backoff with jitter on HTTP errors. Never issue two requests to the same state portal without rate limiter approval (C-09).
- **Example**:
  ```python
  import asyncio, random

  async def rate_limited_get(client: httpx.AsyncClient, url: str,
                              base_delay: float, state: str) -> httpx.Response:
      """Fetch URL with per-state rate limiting and jitter."""
      jitter = base_delay * 0.2 * random.uniform(-1, 1)
      await asyncio.sleep(base_delay + jitter)
      return await client.get(url)
  ```

### P-013: Watchdog Zero-Import Isolation
- **Category**: structure
- **Rule**: The `watchdog/` package must have zero imports from `app/` or `agent/`. It connects to Postgres directly via its own minimal db connection. It calls SendGrid directly. Any violation breaks the independence of the deadman switch (C-07).
- **Example**:
  ```python
  # watchdog/checker.py — correct
  import asyncpg  # or sqlalchemy directly, no app imports

  # WRONG — never do this
  from app.models.operations import AgentHeartbeat
  from app.db import async_session
  ```

### P-014: Internal DNC — Append-Only, Manager-Audit Reversal
- **Category**: data-flow
- **Rule**: The `internal_dnc` table is append-only. No `DELETE` or `UPDATE` may be issued by any automated code path. A reversal requires a separate explicit manager action that writes an audit trail entry. The `check_internal_dnc` function checks by phone AND email independently (C-12).
- **Example**:
  ```python
  async def add_to_dnc(session: AsyncSession, phone: str | None,
                        email: str | None, source_channel: str) -> None:
      """Append an opt-out to the internal DNC table. Never deletes or updates."""
      entry = InternalDNC(phone=phone, email=email,
                          source_channel=source_channel, added_at=datetime.utcnow())
      session.add(entry)
      # No session.delete(), no UPDATE statement — ever.
  ```

### P-015: Test File Per Module
- **Category**: testing
- **Rule**: Every module in `app/`, `agent/`, and `watchdog/` must have a corresponding test file under `tests/`. Naming: `app/compliance/gate.py` -> `tests/unit/test_compliance_gate.py`. Every scraper must also have a smoke test under `tests/smoke/` (C-01, C-17).
- **Example**:
  ```
  app/scrapers/states/california.py  ->  tests/unit/test_scraper_california.py
                                         tests/smoke/test_smoke_california.py
  app/compliance/gate.py             ->  tests/unit/test_compliance_gate.py
  app/enrichment/waterfall.py        ->  tests/unit/test_enrichment_waterfall.py
                                         tests/integration/test_waterfall_integration.py
  ```

### P-016: Sentry Initialization in All Three Service Entry Points
- **Category**: error-handling
- **Rule**: `sentry_sdk.init()` must be called at the top of `app/main.py`, `agent/main.py`, and `watchdog/main.py` before any other application code runs. Use `SENTRY_DSN` from settings (may be None in test environments — init is a no-op when DSN is None).
- **Example**:
  ```python
  # app/main.py
  import sentry_sdk
  from app.config import settings

  sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
  ```

### P-017: DataMerch Optional with Mandatory Warning Log
- **Category**: error-handling
- **Rule**: When `DATAMERCH_API_KEY` is not set, the compliance gate must skip Gate 2 and emit a structlog `warning` event for every lead processed. The fallback path uses UCC filing pattern analysis (multiple MCA lender filings). This is not optional and not silenceable (C-15).
- **Example**:
  ```python
  async def check_datamerch_or_fallback(lead: Lead, session: AsyncSession) -> LayerResult:
      """Run DataMerch check or UCC pattern fallback if unconfigured."""
      if not settings.DATAMERCH_API_KEY:
          log.warning("compliance.datamerch_unconfigured",
              component="compliance", lead_id=str(lead.id),
              context={"fallback": "ucc_pattern_analysis"})
          return await check_ucc_pattern_fallback(lead, session)
      return await call_datamerch_api(lead, session)
  ```

### P-018: Health Check Endpoints on All Three Services
- **Category**: structure
- **Rule**: Each Railway service exposes a `GET /health` endpoint that returns `{"status": "ok"}` with HTTP 200. The path must match `RAILWAY_HEALTHCHECK_PATH`. This is the only mechanism Railway uses to determine if the service is alive (C-04).
- **Example**:
  ```python
  @app.get("/health")
  async def health_check() -> dict:
      """Railway health check endpoint. Must return 200 for service to be considered healthy."""
      return {"status": "ok"}
  ```

### P-019: No Metaprogramming, No Dynamic Imports
- **Category**: structure
- **Rule**: No `__import__()`, no `importlib.import_module()`, no `getattr(module, name)()` for dispatching. Use explicit registries (dicts mapping keys to callables). AI agents cannot safely reason about dynamic dispatch (C-01).
- **Example**:
  ```python
  # app/scrapers/registry.py — correct: explicit dict registry
  from app.scrapers.states.california import CaliforniaScraper
  from app.scrapers.states.texas import TexasScraper

  SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
      "CA": CaliforniaScraper,
      "TX": TexasScraper,
  }

  # WRONG — never do this
  scraper_class = importlib.import_module(f"app.scrapers.states.{state_lower}")
  ```

---

## Pitfalls
(see pitfalls.md for full detail — summary of top items below)

- **PF-001**: Compliance gate early return — any `return True` added above the 4-layer loop bypasses C-02 entirely.
- **PF-002**: Enrichment cache TTL — adding `expires_at` or deleting cache rows violates C-08 and causes re-billing.
- **PF-003**: Watchdog importing from app/ — silently breaks the independence guarantee of C-07; Railway will not catch this.
- **PF-004**: Shared SQLAlchemy session across coroutines — causes `MissingGreenlet` or data corruption under async concurrency.
- **PF-005**: Partially enriched lead reaching the export queue — violates C-03; check `enrichment_status == complete` before exporting.
