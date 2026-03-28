# Architectural Constraints — UCC Lead Generation Platform

These are hard constraints. Planners and builders must not violate any of these.

---

## C-01: Zero Human Developers

The system has no human developers. Every fix, update, feature, and deployment is performed by AI agents. All code must be written with AI maintainability as a first-class concern:
- Functions must be short (<50 lines), single-purpose, with docstrings.
- All modules must have corresponding test files.
- No clever abstractions, no metaprogramming, no dynamic imports.
- Structured logging (JSON via structlog) on every meaningful state change.
- Every scraper must have a corresponding smoke test.

## C-02: Compliance Gate is Absolute

No lead may enter GoHighLevel (or any campaign platform) without passing ALL four compliance layers in order:
1. Internal DNC table check
2. DataMerch MCA default check
3. Federal + state DNC scrub (DNC.com or CCC)
4. Blacklist Alliance TCPA litigator screen

A failure at any layer permanently blocks that lead from export. There is no override, no soft flag, no "export with warning." This is a legal survival requirement (TCPA violations: $500-$1,500 per call/text).

## C-03: Enrichment Failure Halts Pipeline

If an enrichment source returns >20% errors in a 5-minute window, the circuit breaker opens and the pipeline HALTS. Partially enriched leads must NEVER enter the export queue. The pipeline resumes only after the self-healing agent confirms the source is responding. Failed records go to `enrichment_retry_queue` with exponential backoff (1h, 4h, 24h, 72h).

## C-04: Railway Deployment Only

All services deploy to Railway. No AWS, GCP, Azure, or self-hosted infrastructure. Architecture must use only services Railway supports:
- Python services (Docker or Nixpacks)
- Railway Postgres plugin (managed)
- Railway health check endpoints (`RAILWAY_HEALTHCHECK_PATH`)
- Railway restart policies (`on-failure`, `always`)
- Environment variables for all secrets and configuration
- No Redis, no RabbitMQ, no Kafka -- use Postgres for all queueing and state.

## C-05: Single Postgres Database

All data lives in one Railway Postgres instance at MVP scale. This includes:
- Lead records and UCC filing data
- Enrichment cache (permanent, to avoid re-billing)
- Internal DNC table
- Heartbeat watchdog table
- State priority table
- LangGraph state persistence (checkpointer)
- Circuit breaker state
- Pipeline job queue (Postgres-based, not Redis)

No additional databases or caching layers at MVP. Postgres handles all storage and queueing needs at this scale (10K leads/month).

## C-06: Platform-Agnostic Campaign Output

All campaign platform calls must go through a `CampaignPlatformAdapter` interface. Pipeline code never imports GHL-specific modules directly. The adapter interface defines:
- `upsert_lead(lead) -> external_id`
- `enroll_in_campaign(external_id, tier) -> None`
- `get_disposition_updates(since) -> list[DispositionUpdate]`
- `parse_webhook_payload(raw) -> DispositionUpdate | None`

Swapping GHL for another platform = implementing a new adapter class. Zero pipeline code changes.

## C-07: Three Independent Railway Services

The system must deploy as three separate Railway services with independent failure domains:
1. **Pipeline service** — scraping, enrichment, scoring, compliance, export. Restart policy: `on-failure` (3 retries).
2. **Self-healing agent** — LangGraph-based monitoring, diagnosis, repair. Restart policy: `on-failure`.
3. **Heartbeat watchdog** — Independent deadman switch monitor. Restart policy: `always`. This service must have NO dependency on the other two services' code or runtime state.

## C-08: Data Retention is Indefinite

All data is stored permanently. No TTL, no data expiration, no automatic deletion. This includes:
- All UCC filing records (even from closed/terminated filings)
- All enrichment results (serves as permanent cache)
- All compliance check results with timestamps
- All disposition history from GHL
- All internal DNC entries (permanent and irrevocable)
- All scraper run logs and health check results

## C-09: Per-State Rate Limiting

Every scraper must enforce per-state rate limits:
- Default: 1 request per 3 seconds
- Tier 3 states (NH, RI, DE, HI): 1 request per 10 seconds with proxy rotation
- Exponential backoff with jitter on any HTTP error
- User-Agent rotation
- Cookie/session persistence per state

Violating rate limits risks IP bans that could permanently block scraping for high-value states.

## C-10: Deduplication Across States and Cycles

A business may appear in UCC filings across multiple states and across multiple scrape cycles. The deduplication system must:
- Deduplicate by business name + state + filing number (exact match)
- Fuzzy-match business names across states (same business, different filing jurisdictions)
- Track all filing positions per business (position count = scoring signal)
- Never create duplicate lead records in the export queue
- GHL upsert endpoint provides an additional dedup layer (email/phone match)

## C-11: Manager Dashboard Must Be Non-Technical

The dashboard is for one non-technical manager. Constraints:
- No technical jargon in the UI
- Page load under 3 seconds (SC-07)
- Server-rendered HTML (HTMX + Jinja2), not a SPA
- No login/auth system at MVP (Railway private networking or basic auth)
- Displays: pipeline health, lead counts by stage, compliance pass rates, scraper status by state, recent alerts
- Tier assignment via CSV upload (manual, not algorithmic)

## C-12: Internal DNC is Irrevocable

Any opt-out received through ANY channel (SMS STOP, email unsubscribe, verbal request, web form, manual manager entry) results in permanent blocking. The internal DNC entry:
- Cannot be removed by the system automatically
- Can only be reversed by explicit manager action with an audit trail
- Is checked FIRST in the compliance gate (before any paid API calls)
- Applies to both phone and email independently

## C-13: GHL Custom Fields Must Be Pre-Created

The following custom fields must exist in the GHL sub-account before the pipeline can write to them:
- `ucc_filing_date` (date)
- `ucc_filing_state` (text)
- `lead_score` (number)
- `mca_position_count` (number)
- `estimated_revenue` (text/number)
- `owner_name` (text)
- `campaign_tier` (dropdown: tier-1, tier-2, tier-3)
- `source` (text, default: "ucc-pipeline")

This is a manual one-time setup in GHL before the pipeline goes live.

## C-14: Python Only, No JS Build Toolchain

The entire codebase is Python. The dashboard uses server-rendered templates (Jinja2) with HTMX and Tailwind CSS via CDN. There is no Node.js, no npm, no webpack, no Vite, no React, no Vue. This eliminates an entire class of build toolchain maintenance that AI agents handle poorly.

## C-15: DataMerch Requires Pre-Build Vendor Outreach

DataMerch API access is not self-serve. Account approval requires demonstrating MCA industry participation. The compliance gate architecture must have a fallback path if DataMerch access is denied:
- Primary: DataMerch API check
- Fallback: UCC filing pattern analysis (multiple MCA lender filings = strong MCA debt signal without DataMerch confirmation)

The pipeline must function with or without DataMerch. The compliance gate skips the DataMerch layer if access is not configured, but logs a warning on every lead processed.

## C-16: GitHub as Source of Truth

All code is hosted on GitHub. GitHub Actions runs CI (pytest) on every push/PR. The self-healing agent interacts with GitHub via PyGithub:
- Creates issues for detected failures
- Labels issues by priority (top 10 states = priority-high)
- Checks for duplicate open issues before filing new ones
- Reads workflow run results via GitHub REST API

## C-17: Scraping Strategy is Tiered

States are organized into tiers that determine scraping strategy:
- **Tier 1** (15 states, ~80% of MCA volume): Direct HTTP scraping, daily cadence, highest repair priority
- **Tier 2** (~24 states): HTTP scraping with session management, daily-to-48h cadence
- **Tier 3** (~6 states): Proxy rotation required, 48h+ cadence, lowest repair priority
- **Tier 4** (DC, NYC): Skip at MVP

Each tier has different rate limit settings, retry strategies, and repair priority levels.
