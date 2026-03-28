# Architectural Decision Records

---

### ADR-001: Python as Sole Implementation Language
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The platform needs a language for scraping, data pipeline, AI agent, dashboard, and testing. All research domains converged on Python. The system is 100% AI-managed with no human developers.
- **Decision**: Use Python 3.12+ as the sole implementation language. No JavaScript, no TypeScript, no secondary languages.
- **Alternatives**: Node.js/TypeScript (strong async, but weaker scraping ecosystem and AI agent frameworks). Go (fast, but poor fit for rapid AI-managed iteration). Mixed Python+JS (adds build toolchain complexity).
- **Rationale**: Every required library exists in Python (httpx, Playwright, LangGraph, pytest, SQLAlchemy). AI code generation models produce highest-quality Python. Single language eliminates polyglot maintenance burden for AI agents. Railway supports Python natively.
- **Consequences**: Dashboard must use server-rendered templates (no React/Vue SPA). No Node.js build toolchain to maintain. All team members (AI agents) work in one language.

---

### ADR-002: Single Postgres Database for All Storage
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The system needs storage for leads, enrichment cache, DNC list, heartbeat watchdog, job queue, LangGraph state, and circuit breaker state. Railway offers managed Postgres.
- **Decision**: Use a single Railway Postgres 16+ instance for all data storage and queueing. No Redis, no message brokers, no additional databases.
- **Alternatives**: Postgres + Redis (adds operational complexity for caching/queueing). Postgres + SQLite (LangGraph supports SQLite checkpointer, but adds a second data store). Multi-database sharding (premature optimization at 10K leads/month).
- **Rationale**: At MVP scale (10K leads/month), Postgres handles all workloads including job queueing (SELECT FOR UPDATE SKIP LOCKED pattern), caching, and state persistence. One database means one backup strategy, one connection pool, one failure domain. Railway Postgres plugin provides managed backups.
- **Consequences**: Job queueing uses Postgres polling rather than pub/sub. Acceptable latency for daily-cadence pipeline. May need Redis at scale beyond 100K leads/month.

---

### ADR-003: FastAPI + HTMX for Dashboard (No SPA)
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The manager dashboard must load in under 3 seconds, display pipeline metrics, and require zero technical knowledge. The sole user is one non-technical manager.
- **Decision**: Server-rendered HTML using FastAPI + Jinja2 templates + HTMX for dynamic updates. Tailwind CSS and Chart.js via CDN. No JavaScript build toolchain.
- **Alternatives**: React/Next.js (full SPA -- adds Node.js build chain, increases AI maintenance complexity). Streamlit (rapid prototyping but limited customization and poor production fit). Django (heavier than needed for a single-user dashboard).
- **Rationale**: HTMX provides dynamic behavior (polling, partial page updates) with zero JS build toolchain. Jinja2 templates are Python-native and trivial for AI agents to maintain. Sub-3-second page loads are achievable with server-rendered HTML + Postgres queries. Eliminates React/Vue version churn and npm dependency management.
- **Consequences**: No client-side state management. All interactivity is server-driven. Sufficient for a monitoring dashboard; would not scale to a complex multi-user application.

---

### ADR-004: GHL API v2 as Primary Integration (Not CSV)
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: Research confirmed GHL API v2 supports upsert, workflow enrollment, and webhook-based disposition feedback. CSV was the original MVP plan per VISION.md.
- **Decision**: Use GHL API v2 as the primary integration path. CSV export retained as manual fallback only.
- **Alternatives**: CSV-only (simpler but no automation for workflow enrollment or disposition feedback). CSV primary with API secondary (unnecessary complexity when API covers all needs).
- **Rationale**: API enables full automation: upsert handles dedup, workflow enrollment handles tiered routing, webhooks handle real-time disposition feedback. CSV requires manual upload and provides no feedback loop. The two-call pattern (upsert + enroll) is simple and well within rate limits (100 req/10s).
- **Consequences**: Requires GHL API key setup. Requires webhook endpoint in pipeline API. Disposition feedback is real-time rather than batch. CSV fallback is available if API is temporarily unavailable.

---

### ADR-005: CampaignPlatformAdapter Interface for Platform Agnosticism
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: VISION.md requires platform-agnostic architecture. GHL is the current campaign platform but may be replaced.
- **Decision**: All campaign platform calls go through a `CampaignPlatformAdapter` abstract interface. The `GHLAdapter` is the concrete implementation. Pipeline code never imports GHL-specific modules.
- **Alternatives**: Direct GHL calls throughout pipeline (faster to build but creates vendor lock-in). Configuration-driven adapter selection (over-engineered for a single platform swap).
- **Rationale**: The adapter pattern is a well-established anti-corruption layer. Adding it from day one costs minimal development time but saves weeks of refactoring if GHL is replaced. The interface has only 4 methods -- low abstraction overhead.
- **Consequences**: All GHL-specific logic is isolated in one module. Swapping to HubSpot, Close, or Salesforce requires implementing one new class.

---

### ADR-006: Three Independent Railway Services
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The system has three distinct concerns: pipeline execution, self-healing monitoring, and watchdog oversight. The watchdog must survive failures in the other two.
- **Decision**: Deploy as three separate Railway services: (1) Pipeline service, (2) Self-healing agent, (3) Heartbeat watchdog. Each has independent restart policies and failure domains.
- **Alternatives**: Single monolith (simpler deployment but watchdog cannot survive pipeline crash). Two services (combine agent + watchdog -- defeats the purpose of independent oversight).
- **Rationale**: The watchdog-for-the-watchdog pattern requires physical separation. If the self-healing agent crashes, the watchdog detects the stale heartbeat and sends an email alert. Railway restart policies provide the first layer of recovery. Three services at Railway's scale cost ~$20-50/mo total.
- **Consequences**: Three Railway service configurations to maintain. Shared Postgres is the communication channel. No inter-service HTTP calls needed (all coordination via database).

---

### ADR-007: LangGraph for Self-Healing Agent
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The self-healing agent needs cyclical execution (detect -> diagnose -> repair -> verify -> loop), state persistence across restarts, and priority-based repair ordering.
- **Decision**: Use LangGraph v0.2+ with Postgres checkpointer for the self-healing agent.
- **Alternatives**: CrewAI (simpler but less flexible for complex control flow). Custom state machine (more code to maintain, no community support). No agent framework (raw LLM calls -- loses state persistence and graph execution benefits).
- **Rationale**: LangGraph provides cyclical graphs (supervisor can loop back), Postgres state persistence (survives restarts), priority queue support (repair highest-value states first), and error handling nodes. Production-grade as of v0.2.
- **Consequences**: Adds LangGraph + LangChain as dependencies. Requires Postgres checkpointer table. Agent state is inspectable via Postgres queries.

---

### ADR-008: Waterfall Pattern as Core Architectural Primitive
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: Research identified waterfall pattern recurring across three domains: enrichment (try cheapest source first), compliance (internal DNC first, then external APIs), and scraping (direct HTTP first, headless browser fallback).
- **Decision**: Implement a generic waterfall executor that accepts an ordered list of strategy callables and returns the first successful result. Use this primitive across enrichment, compliance, and scraping subsystems.
- **Alternatives**: Per-domain ad-hoc fallback logic (duplicates pattern, harder to test). Single enrichment source per data point (lower coverage, higher cost).
- **Rationale**: A shared waterfall executor reduces code duplication, makes the fallback order configurable, and provides a single place to add logging, metrics, and circuit breaker integration. Each domain configures its own waterfall with domain-specific strategies.
- **Consequences**: All fallback/cascade logic follows the same pattern. Adding a new enrichment source = adding one strategy function to the waterfall configuration.

---

### ADR-009: Structured Logging via structlog (JSON)
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The self-healing agent reads logs to diagnose failures. Railway captures stdout. Logs must be machine-readable.
- **Decision**: Use structlog with JSON output for all logging. Every log entry includes `component`, `status`, `error_type`, and `context` fields.
- **Alternatives**: Python stdlib logging with custom JSON formatter (works but more boilerplate). Loguru (popular but less structured output by default).
- **Rationale**: structlog produces zero-config JSON output. Consistent field names across all services mean the self-healing agent can parse logs reliably. Railway's log viewer works well with JSON.
- **Consequences**: All services must use structlog, not print() or stdlib logging. Log format is a contract between services and the self-healing agent.

---

### ADR-010: Postgres-Based Job Queue (No Redis/Celery)
- **Date**: 2026-03-24
- **Status**: accepted
- **Context**: The pipeline needs job queueing for scrape tasks, enrichment batches, and retry scheduling. Railway does not offer managed Redis.
- **Decision**: Use Postgres as the job queue via SELECT FOR UPDATE SKIP LOCKED pattern. Jobs stored in a `job_queue` table with status, priority, scheduled_at, and retry metadata.
- **Alternatives**: Redis + Celery (industry standard but adds operational complexity and a second data store on Railway). RabbitMQ (same problem). AWS SQS (violates Railway-only constraint).
- **Rationale**: At 10K leads/month with daily scraping cadence, Postgres handles job queueing with minimal latency. The SELECT FOR UPDATE SKIP LOCKED pattern is battle-tested for this scale. One fewer service to manage and monitor.
- **Consequences**: Job throughput limited by Postgres connection pool. Acceptable at MVP scale. If throughput becomes a bottleneck beyond 100K leads/month, Redis can be added later.
