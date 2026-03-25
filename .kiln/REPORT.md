# Project Report — UCC Business Debt Lead Generation Platform

## Executive Summary

Built a complete internal lead generation pipeline that replaces third-party data brokers with an in-house automated system. The platform scrapes UCC filings from ~40 state Secretary of State websites, identifies businesses with MCA (Merchant Cash Advance) debt, enriches leads with contact information, enforces a 4-layer compliance gate, and exports qualified leads to GoHighLevel for campaign execution.

**Key metrics:**
- 122 Python source files
- 7,133 lines of code
- 12 commits across 10 milestones
- 40 state scrapers (10 Tier 1, 24 Tier 2, 6 Tier 3)
- 13 database tables
- 4-layer compliance gate (Internal DNC → DataMerch → DNC.com → Blacklist Alliance)
- 3 independent Railway services (pipeline, agent, watchdog)

## Architecture

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy 2.0 async / Postgres 16+ / HTMX / LangGraph

**Three Services:**
1. **Pipeline Service** (`app/`) — Core data pipeline, dashboard, API endpoints
2. **Self-Healing Agent** (`agent/`) — LangGraph-based autonomous monitoring and repair
3. **Heartbeat Watchdog** (`watchdog/`) — Independent deadman switch (zero app/agent imports)

**Data Flow:**
```
UCC Scraping → MCA Detection → Lead Scoring → Enrichment → Compliance Gate → Dedup → GHL Export
     ↑                                                                              |
     └── Disposition Feedback ← GHL Webhooks ← Campaign Execution ← Lead Recycling ←┘
```

## Milestone Summary

| # | Milestone | Files | Key Deliverables |
|---|-----------|-------|------------------|
| M1 | Foundation + CI/CD | 31 | 13 ORM models, Alembic, job queue, structlog, 3 FastAPI services, GitHub Actions |
| M2 | Scraper Engine | 53 | 40 state scrapers, rate limiter, UA rotation, APScheduler, Playwright stub |
| M3 | MCA Detection | 8 | Alias detector, lead scorer, self-improving updater, pipeline wiring |
| M4 | Enrichment Pipeline | 7 | Waterfall executor, 5 source connectors, circuit breakers, cache, retry queue |
| M5 | Compliance Gate | 4 | 4-layer absolute gate, internal DNC (irrevocable), audit trail |
| M6 | Campaign Export | 7 | GHL adapter, CSV fallback, webhook receiver, lead recycler, dedup |
| M7 | Dashboard | 7 | HTMX dashboard, pipeline metrics, scraper status, alerts, CSV tier upload |
| M8 | Self-Healing Agent | 1 | LangGraph graph (detect/diagnose/repair/verify/alert), GitHub issue automation |
| M9 | Watchdog | 1 | Independent heartbeat monitor, SendGrid alerts, alert deduplication |
| M10 | Integration | 2 | Route wiring, end-to-end tests, constraint verification |

## Compliance Architecture (Critical)

The compliance gate is the legally critical component — non-compliant leads **never** enter GoHighLevel.

**4-Layer Sequential Gate:**
1. **Internal DNC** — checked first (before paid APIs). Append-only, irrevocable.
2. **DataMerch** — MCA default history. Fails open with warning when unconfigured (C-15).
3. **DNC.com/CCC** — Federal + state DNC list scrub.
4. **Blacklist Alliance** — TCPA professional litigator screening.

Any layer failure = permanent block. No override. No soft flag. Full audit trail in `compliance_checks` table.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ADR-002 | Single Postgres (no Redis) | Railway simplicity, job queue via SKIP LOCKED |
| ADR-004 | GHL API v2 primary | Real-time upsert + workflow enrollment, CSV fallback |
| ADR-008 | Generic waterfall executor | Shared pattern for enrichment, compliance, scraper fallback |
| C-06 | Platform-agnostic adapter | GHL can be swapped without touching pipeline code |
| C-07 | Watchdog isolation | Zero imports from app/agent — independent failure domain |

## Deployment

**Railway Configuration:**
- `web` (pipeline): on-failure restart, /health check
- `agent` (self-healing): on-failure restart, /health check
- `watchdog` (deadman switch): always restart, /health check

**Required Environment Variables:**
- `DATABASE_URL` — Postgres connection string
- `SENTRY_DSN` — Error tracking
- All others optional with graceful fallbacks (see `.env.example`)

## Next Steps

1. **DataMerch Outreach** — Contact datamerch.com for API access (vendor requires manual approval)
2. **Railway Deployment** — Set up 3 services, configure env vars, run `alembic upgrade head`
3. **GitHub Repository** — Push to GitHub, configure Actions secrets
4. **GHL Setup** — Create custom fields, workflows for 3 tiers, configure webhook URL
5. **Seed MCA Aliases** — Run initial seed data load for alias detection
6. **Scraper Calibration** — Run Tier 1 scrapers against live state portals, adjust parsers
7. **Compliance API Keys** — Set up DNC.com and Blacklist Alliance accounts
8. **Enrichment API Keys** — Set up PDL, Apollo, OpenCorporates accounts

## V2 Roadmap

- **AI Learning Engine** — Disposition feedback → scoring evolution, conversion pattern detection
- **Fallback Scraping** — Third-party data brokers for blocked states
- **GHL Replacement** — Alternative campaign platform via adapter pattern
- **Playwright Scrapers** — JS-rendered state portals (stub exists)

## Cost Projections (from Research)

| Category | Monthly Cost | Notes |
|----------|-------------|-------|
| Enrichment (PDL + Apollo) | ~$600-800 | For 10K leads/month |
| Compliance (CCC + Blacklist) | ~$400-700 | DNC scrub + litigator screening |
| Railway | ~$20-50 | 3 services + Postgres |
| DataMerch | ~$250-1,500 | Depends on volume and tier |
| **Total** | **~$1,270-3,050** | vs $30K-150K/yr for third-party lead gen |

---

*Generated by Kiln Pipeline v0.98.3 · Run kiln-384252 · 2026-03-25*
