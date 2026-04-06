# External Integrations

**Analysis Date:** 2026-04-06

## APIs & External Services

**Campaign platform (GoHighLevel):**
- REST API v2 base `https://services.leadconnectorhq.com` — contact upsert and workflow enrollment via `httpx` in `app/export/ghl_adapter.py`; auth header `Bearer` + API version header; settings `GHL_API_KEY`, `GHL_LOCATION_ID`, tier workflow IDs in `app/config.py`.
- Inbound webhooks — `POST /webhooks/ghl` in `app/export/webhook.py`; optional HMAC verification with `GHL_WEBHOOK_SECRET`; updates `Lead` disposition and may append internal DNC via `app/compliance/internal_dnc.py`.

**Enrichment:**
- People Data Labs — `https://api.peopledatalabs.com/v5/company/enrich` in `app/enrichment/sources.py`; `PDL_API_KEY` header `X-Api-Key`.
- Apollo.io — `https://api.apollo.io/v1/organizations/enrich` in `app/enrichment/sources.py`; `APOLLO_API_KEY`.
- OpenCorporates — `https://api.opencorporates.com/v0.4/companies/search` in `app/enrichment/sources.py`; `OPENCORPORATES_API_KEY` as query param `api_token`.
- Whitepages Pro — `https://proapi.whitepages.com/3.0/business` in `app/enrichment/sources.py`; `WHITEPAGES_API_KEY`.
- Twilio Lookup v2 — `https://lookups.twilio.com/v2/PhoneNumbers/{phone}` in `app/enrichment/sources.py`; HTTP basic auth `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN`.

**Compliance (4-layer gate):**
- Internal DNC — Postgres table `InternalDNC` via SQLAlchemy in `app/compliance/gate.py` (`check_internal_dnc`); no external API.
- DataMerch — `https://api.datamerch.com/v1/check` in `app/compliance/gate.py`; `Authorization: Bearer` + `DATAMERCH_API_KEY`; unconfigured key logs warning and fails open per code comments (C-15).
- DNC scrub (documented as DNC.com / CCC) — `https://api.dnc.com/v1/check` in `app/compliance/gate.py`; `DNC_SCRUB_API_KEY`.
- Blacklist Alliance — `https://api.blacklistalliance.com/v1/lookup` in `app/compliance/gate.py`; `BLACKLIST_API_KEY`.

**LLM (self-healing agent):**
- Anthropic Messages API — `anthropic.AsyncAnthropic` in `agent/graph.py`; model `claude-sonnet-4-20250514`; `ANTHROPIC_API_KEY` from `app.config.Settings`.

**GitHub:**
- REST API `https://api.github.com/repos/{owner}/{repo}/...` — raw `httpx` calls in `agent/graph.py`; `GITHUB_TOKEN` (Bearer) and `GITHUB_REPO` (e.g. `owner/repo`) in `app/config.py`.

**Email (SendGrid):**
- `https://api.sendgrid.com/v3/mail/send` — `httpx` JSON posts in `watchdog/monitor.py` (`SENDGRID_API_KEY`, `MANAGER_EMAIL` from environment only) and `agent/graph.py` (via `Settings` / env patterns in that module).

**Error tracking:**
- Sentry — `sentry_sdk.init` in `app/main.py`, `agent/main.py`, `watchdog/main.py`; DSN from `SENTRY_DSN` (required field on `Settings` in `app/config.py`; CI uses placeholder in `.github/workflows/ci.yml`).

**Scraping / browser:**
- Target SOS and public filing sites — per-state modules under `app/scrapers/states/` using `httpx` and/or Playwright (`playwright.async_api`).
- Optional HTTP proxy — `PROXY_URL` in `app/config.py`, consumed by `app/scrapers/rate_limiter.py` for tier-3 behavior (see docstring in `app/scrapers/rate_limiter.py`).

## Data Storage

**Databases:**
- PostgreSQL — single logical database via `DATABASE_URL` (asyncpg URL). Engine/session in `app/db.py`; watchdog uses its own `create_async_engine` in `watchdog/monitor.py` for heartbeat queries only (no import of `app.db`).
- ORM models — `app/models/` (`Lead`, `UCCFiling`, `ScraperRun`, `AgentHeartbeat`, `LanggraphCheckpoint`, etc.).

**File Storage:**
- Local filesystem only for templates and static-served HTML generation; no S3/blob client in `pyproject.toml` dependencies.

**Caching:**
- Enrichment cache persisted in Postgres (`app/enrichment/cache.py`, `EnrichmentCache` model) — not an external cache service.

## Authentication & Identity

**Auth Provider:**
- No end-user OAuth/login for the manager dashboard in the analyzed routes — dashboard HTML is served without a separate auth middleware in `app/dashboard/routes.py`.
- External API authentication is per-vendor API keys and tokens defined in `app/config.py` and `.env.example`.
- GHL webhook authenticity: HMAC-SHA256 in `app/export/webhook.py` when `GHL_WEBHOOK_SECRET` is set.

## Monitoring & Observability

**Error Tracking:**
- Sentry — see above.

**Logs:**
- structlog JSON to stdout (`app/logging.py`); agent and pipeline components use `get_logger(component=...)`.

## CI/CD & Deployment

**Hosting:**
- Railway — `railway.toml`, `Procfile` (three processes: web / agent / watchdog).

**CI Pipeline:**
- GitHub Actions — `.github/workflows/ci.yml` on `main`/`master` and PRs; Python 3.12, `pip install -e ".[dev]"`, `pytest`.

## Environment Configuration

**Required env vars (app `Settings` in `app/config.py`):**
- `DATABASE_URL`, `SENTRY_DSN` — required at startup for `Settings()`.

**Documented optional / integration vars:**
- See `.env.example` for full list names (GHL, enrichment, compliance, agent, GitHub, SendGrid, etc.). Do not commit populated `.env` files.

**Secrets location:**
- Railway and local operator environment; `.env` may be used locally (`Settings.model_config` in `app/config.py`). A committed template exists at `.env.example`.

## Webhooks & Callbacks

**Incoming:**
- `POST /webhooks/ghl` — `app/export/webhook.py` (`APIRouter` included from `app/main.py`).

**Outgoing:**
- None defined as dedicated outbound webhook subscriptions in code; agent may open GitHub issues and send email via HTTP APIs (`agent/graph.py`).

---

*Integration audit: 2026-04-06*
