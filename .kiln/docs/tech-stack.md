# Tech Stack — UCC Lead Generation Platform

## Language

| Choice | Version | Rationale |
|--------|---------|-----------|
| **Python** | 3.12+ | Every research domain converged on Python: scraping (requests, Playwright), data pipeline (pandas-free ETL via SQL), AI agent (LangGraph), testing (pytest), all enrichment/compliance APIs have Python SDKs. Railway supports Python natively. AI agents (Claude, GPT-4) produce highest-quality Python code. |

## Core Framework and Libraries

| Component | Library | Version | Purpose | Rationale |
|-----------|---------|---------|---------|-----------|
| Web framework | **FastAPI** | 0.110+ | HTTP API for webhooks, health checks, dashboard backend | Async-native, auto-generated OpenAPI docs, Pydantic validation. Lightweight enough for Railway. |
| Task scheduling | **APScheduler** | 3.10+ | Cron-based scrape scheduling, nightly recalculation jobs | In-process scheduler avoids separate Redis/Celery infrastructure. Sufficient for daily-cadence scraping. |
| HTTP scraping | **httpx** | 0.27+ | Stateful HTTP sessions for SOS portal scraping | Async support, cookie persistence, connection pooling. Preferred over requests for async pipeline. |
| Headless browser | **Playwright** | 1.42+ | JS-rendered SOS portals (~10% of states) | Chromium-based, async Python API, better than Selenium for modern SPAs. |
| HTML parsing | **BeautifulSoup4** | 4.12+ | Parse HTML tables from SOS portals | Industry standard for HTML extraction. lxml parser backend for speed. |
| AI agent framework | **LangGraph** | 0.2+ | Self-healing agent loop with cyclical graphs and state persistence | Production-grade cyclical execution, Postgres checkpointer, priority queue support. |
| LLM client | **anthropic** | 0.25+ | Claude API calls for diagnosis and repair | Primary LLM for self-healing agent code analysis. |
| Database ORM | **SQLAlchemy** | 2.0+ | Postgres access, schema management, migrations | Type-safe ORM with async support. Alembic for migrations. |
| Migrations | **Alembic** | 1.13+ | Database schema versioning | Standard companion to SQLAlchemy. AI agent can generate and apply migrations. |
| Circuit breaker | **pybreaker** | 1.0+ | Enrichment failure HALT | Prevents cascading failures from broken enrichment APIs. |
| Structured logging | **structlog** | 23.0+ | JSON-formatted log output | Machine-readable logs for self-healing agent and Railway log aggregation. |
| Error tracking | **sentry-sdk** | 2.0+ | Unhandled exception capture | Free tier (5K errors/mo). One-line init. Industry standard. |
| GitHub automation | **PyGithub** | 1.59+ | Issue creation, label management | Self-healing agent creates prioritized issues for detected failures. |
| Email alerts | **sendgrid** | 6.0+ | Plain-English alerts to manager | Free tier (100 emails/day). Superior deliverability from cloud IPs. |
| Phone validation | **twilio** | 8.0+ | Lookup API for phone validation and line-type | Pay-as-you-go ($0.005/req). No monthly minimum. |
| Testing | **pytest** | 8.0+ | Unit, integration, smoke, contract tests | De-facto Python standard. pytest-json-report for AI-readable output. |
| Coverage | **pytest-cov** | 4.0+ | Code coverage reporting | AI agent uses coverage data to identify untested failure paths. |
| Config management | **pydantic-settings** | 2.0+ | Environment variable parsing and validation | Type-safe config from env vars. Railway-native pattern. |

## Database

| Choice | Version | Rationale |
|--------|---------|-----------|
| **PostgreSQL** | 16+ | Single database serves all needs: lead storage, enrichment cache, internal DNC table, heartbeat watchdog, state_priority, LangGraph state persistence, circuit breaker state. Railway Postgres plugin provides managed instance. Indefinite data retention per VISION.md. |

## Deployment

| Component | Platform | Configuration |
|-----------|----------|---------------|
| Pipeline workers | **Railway** | Python service, `on-failure` restart policy, 3 retries |
| Self-healing agent | **Railway** | Separate service, `on-failure` restart policy |
| Heartbeat watchdog | **Railway** | Separate service, `always` restart policy |
| Dashboard API | **Railway** | FastAPI service, `RAILWAY_HEALTHCHECK_PATH=/health` |
| Database | **Railway Postgres** | Managed plugin, auto-backups |
| Source control | **GitHub** | Main branch, GitHub Actions CI |
| CI/CD | **GitHub Actions** | pytest on push/PR, auto-deploy to Railway on main merge |

## Dashboard / Manager UI

| Choice | Version | Rationale |
|--------|---------|-----------|
| **HTMX** + **Jinja2** templates | HTMX 1.9+, Jinja2 3.1+ | Server-rendered HTML with HTMX for dynamic updates. Zero JS build toolchain. Non-technical manager needs simple, fast-loading pages -- not a SPA. Eliminates React/Vue/Svelte complexity. AI agents maintain Python templates more reliably than JS frontends. Dashboard loads in under 3 seconds (SC-07). |
| **Tailwind CSS** (via CDN) | 3.4+ | Utility-first CSS for clean dashboard styling. CDN avoids build step. |
| **Chart.js** (via CDN) | 4.4+ | Simple pipeline metric charts. CDN delivery, no bundler needed. |

## External APIs (Enrichment)

| Service | Purpose | Pricing | Priority in Waterfall |
|---------|---------|---------|----------------------|
| **Apollo.io** | Email + company revenue | $49-99/mo | Primary email, primary revenue |
| **People Data Labs** | Phone + owner name | $98/mo | Primary phone |
| **OpenCorporates** | Registered officers (owner name) | $50/mo | Secondary owner name |
| **Twilio Lookup** | Phone validation + line-type | $0.005/req | Validation layer |
| **Whitepages Pro** | Reverse phone by business name | $0.05-0.15/req | Secondary phone |
| **SOS officer scraping** | Owner name from state portals | Free | First-try owner name |

## External APIs (Compliance)

| Service | Purpose | Pricing | Gate Order |
|---------|---------|---------|------------|
| **Internal DNC table** | Permanent opt-out list | Free (Postgres) | Gate 1 (checked first) |
| **DataMerch** | MCA default history | $0.25-1.50/record | Gate 2 |
| **DNC.com or CCC** | Federal + state DNC scrub | $149-299/mo | Gate 3 |
| **Blacklist Alliance** | TCPA litigator screening | $199-399/mo | Gate 4 |

## External APIs (Campaign Platform)

| Service | Purpose | Integration Pattern |
|---------|---------|-------------------|
| **GoHighLevel API v2** | Lead export + tiered workflow enrollment | Upsert + workflow enrollment via CampaignPlatformAdapter |
| **GHL Webhooks** | Disposition feedback (real-time) | OpportunityUpdate + ContactUpdate events |

## Estimated Monthly Costs

| Category | Low | High |
|----------|-----|------|
| Enrichment APIs | $600 | $800 |
| Compliance APIs | $400 | $700 |
| TX bulk subscription (optional) | $0 | $150 |
| Railway hosting | $20 | $50 |
| Email alerts (SendGrid) | $0 | $0 |
| Error tracking (Sentry) | $0 | $0 |
| **Total** | **$1,020** | **$1,700** |
