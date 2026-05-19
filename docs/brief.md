---
title: "UCC Lead Generation Platform — Project Brief"
status: draft
created: 2026-05-19
updated: 2026-05-19
generated_by: bmad-product-brief (Analyst, applied manually)
source_inputs:
  - README.md
  - AGENTS.md
  - DEPLOY.md
  - .env.example
  - pyproject.toml
  - railway.toml
  - Procfile
  - .kiln/master-plan.md
  - .kiln/REPORT.md
  - .kiln/docs/architecture.md
  - .kiln/docs/tech-stack.md
  - .kiln/docs/arch-constraints.md
  - .planning/PROJECT.md
  - .planning/REQUIREMENTS.md
  - app/, agent/, watchdog/, migrations/, tests/
---

# Product Brief: UCC Lead Generation Platform (UCC)

## Executive Summary

UCC is a Python-only, fully AI-maintained pipeline that turns public Secretary of State UCC filings into compliant, qualified **Merchant Cash Advance (MCA) refinance leads** ready for outbound campaigns. It scrapes ~40 state SOS portals, detects businesses with MCA debt, enriches them into actionable leads, runs a four-layer legal compliance gate (TCPA / DNC), deduplicates across states, and exports cleared leads into GoHighLevel — all on three independent Railway services backed by a single Postgres database.

It replaces a recurring **$30K–$150K/yr third-party lead-broker spend** with an in-house pipeline that costs roughly **$1,000–$1,700/month** to operate, while keeping the compliance gate, audit trail, and DNC list under the operator's direct control. The system is designed for a single non-technical manager: a server-rendered HTMX dashboard surfaces business outcomes, and a LangGraph "self-healing agent" plus an independent heartbeat watchdog cover the operational role that a human engineer would normally occupy.

It matters **now** because (a) the MCA industry has a stable, public, structured signal (UCC-1 filings against the same debtor by multiple funders) that maps cleanly to "stacked / refinance-eligible" merchants, (b) TCPA exposure has made compliance-clean lead supply scarce and expensive, and (c) modern AI tooling (Claude, LangGraph, Sentry-as-input) finally makes an "AI-only maintained" codebase plausible — provided the architecture is shaped to make that maintenance easy.

## The Problem

MCA brokerages live or die on lead quality and lead cost.

- **Bought lists are expensive and noisy.** Third-party "MCA lead" lists run $30K–$150K per year and ship a mix of stale, scrubbed-but-uncertain, and outright DNC-tainted records. Buyers absorb the noise as wasted dial time and TCPA risk.
- **Public UCC data is the right signal but hard to use.** Every state SOS exposes UCC filings in a different shape — some as HTML tables, some as JSON, some as JS-rendered portals (CA, FL, TX, NJ, NY are all bespoke), with bespoke rate limits and anti-bot behavior. Building this once is hard. Maintaining it across 40+ states forever is harder.
- **Enrichment APIs are flaky and billable.** PDL, Apollo, OpenCorporates, Whitepages, Twilio Lookup each fail differently. Naively chaining them risks blowing budget on duplicate calls, marking leads "complete" with partial data, or cascading a vendor outage into pipeline-wide failure.
- **Compliance is asymmetric.** A single illegal call/text is **$500–$1,500 per violation** under TCPA. There is no acceptable "soft warning" or "export with caveat" path. The cost of one bypassed check dwarfs months of platform spend.
- **There are no engineers.** The operator is non-technical. Anything that requires a person to triage a stack trace, write a fix, or push a PR is a sustainability failure.

The cost of the status quo: paying broker rents, eating TCPA exposure, and depending on a human engineer who does not exist.

## The Solution

UCC takes seven pipeline stages and wraps them in two safety systems and one dashboard.

**Seven-stage pipeline (`app/` service):**

1. **Scrape** — Per-state scrapers (`app/scrapers/states/*.py`, 40 implementations) pull recent UCC filings via `httpx` (with Playwright base ready for JS-rendered portals) on a tiered APScheduler cadence (Tier 1 daily, Tier 2 every 36h, Tier 3 every 48h). A shared rate limiter enforces per-state delays, jitter, exponential backoff, and proxy rotation for Tier 3.
2. **Detect MCA** — `app/mca/detector.py` normalizes secured-party names and matches them against the `mca_aliases` table (exact → fuzzy via `rapidfuzz` → shell-company patterns → collateral keywords). A nightly alias updater improves coverage automatically.
3. **Score** — `app/mca/scorer.py` aggregates position count across states (primary signal), recency (recency boost), and collateral type. Position-count buckets become `hot` / `warm` / `cold` tiers.
4. **Enrich** — A generic `WaterfallExecutor` (`app/enrichment/waterfall.py`) tries PDL → Apollo → OpenCorporates per lead, with a permanent Postgres enrichment cache (no TTL, C-08), `pybreaker` circuit breakers per source, and a retry queue with 1h/4h/24h/72h backoff. A rolling failure-rate window (>20% in 5 min) trips a pipeline-wide HALT.
5. **Compliance gate** — Strictly sequential 4-layer check in `app/compliance/gate.py`: Internal DNC → DataMerch → DNC.com/CCC → Blacklist Alliance. Any failure → permanent block (no override). Every check is recorded in `compliance_checks`. Internal DNC is **append-only**; reversal requires an explicit audit row (`dnc_reversal_audit`).
6. **Deduplicate** — Cross-state exact + fuzzy matching collapses the same business filed in multiple jurisdictions.
7. **Export** — Only via the abstract `CampaignPlatformAdapter` (`app/export/adapter.py`). The concrete `GHLAdapter` upserts contacts to GoHighLevel API v2, enrolls them in tier-specific workflows, exposes a webhook receiver for disposition feedback, and falls back to CSV when the API is down. `require_compliance_cleared` is enforced at the adapter boundary.

**Two safety systems:**

- **Self-healing agent (`agent/` service)** — A LangGraph cycle (detect → diagnose → repair → verify → alert) reads `pipeline_events`, `scraper_runs`, structured logs, and Sentry events; calls Claude for diagnosis; opens GitHub PRs for repairs; merges on green CI or files a priority-labeled issue on failure; emails the manager in plain English via SendGrid (rate-limited per failure fingerprint). Heartbeats every 60s into `agent_heartbeat`.
- **Heartbeat watchdog (`watchdog/` service)** — An **independent** deadman switch with **zero imports from `app/` or `agent/`** (C-07). Polls the heartbeat table every 5 minutes; if stale and business hours, emails the manager directly. Restart policy is `always`.

**One dashboard:** FastAPI + Jinja2 + HTMX (no JS toolchain, C-14) rendered from the same pipeline service. Shows pipeline health, lead funnel counts, compliance pass rates, scraper status by state, and recent alerts in business language — no stack traces, no error codes (C-11).

## What Makes This Different

- **Compliance is an architectural invariant, not a feature.** The gate is sequential, append-only, internally-checked first (before billing), and the export adapter refuses anything without `compliance_status == "cleared"`. Negative tests verify there is no code path that bypasses it (C-02).
- **Built for AI maintenance, not human maintenance.** Functions under 50 lines, mandatory docstrings, one-file-per-state scrapers, explicit registries instead of dynamic imports, structured JSON logs with required fields (`component`, `status`, `error_type`, `context`), and a self-healing agent that consumes those logs (C-01). The codebase is shaped so an AI can read it in chunks without losing context.
- **Single Postgres, three services, no Redis/Kafka.** Job queue uses `SELECT FOR UPDATE SKIP LOCKED`, LangGraph checkpoints in Postgres, circuit-breaker state in Postgres, enrichment cache in Postgres. Operating surface stays tiny (C-04, C-05).
- **Independent watchdog domain.** If the agent crashes, the watchdog still emails the manager. If `app/` is broken, the watchdog still runs (it imports nothing from it). Failure domains are physically isolated.
- **Vendor-swappable export.** Pipeline code never touches `ghl_adapter` directly; it only knows `CampaignPlatformAdapter`. Swapping GHL out is one new adapter class, not a refactor (C-06).

What it is **not**: a moat built on proprietary data, a slicker UI, or a faster scraper. The differentiator is operational: a system that the operator can run alone, sustain on AI maintenance, and trust to never accidentally export a non-compliant lead.

## Who This Serves

**Primary user — The Operator (1 person, non-technical).** Owns an MCA brokerage; lives in GoHighLevel; cannot read a Python stack trace and shouldn't have to. Success looks like: "I open the dashboard, I see today's compliant leads loaded into the tier-1 workflow, I see no red alerts, and when something breaks I get a one-paragraph email telling me what's happening and what (if anything) I need to do."

**Direct downstream users — Sales reps inside GoHighLevel.** They never touch UCC; they just receive better-targeted contacts in their existing GHL workflows, tagged by tier with custom fields (`mca_position_count`, `lead_score`, `ucc_filing_state`, `estimated_revenue`, etc., C-13). Success looks like: contact rate and conversion both go up, and DNC/TCPA complaints stay at zero.

**Secondary user — The AI maintainer (Claude / future agents).** Reads the codebase, opens PRs, files issues. Success looks like: small, well-tested modules with structured logs; rare human escalation; PRs that pass CI on first try.

## Success Criteria

User and operational signals:

- **Compliance integrity (existential).** Zero non-compliant leads in GHL after a full pipeline run with mixed test data. Every layer logs a row to `compliance_checks` for every lead, pass or fail. Negative tests show no bypass path exists (C-02, COMPLY-05).
- **End-to-end lead delivery.** A live UCC filing scraped from a Tier 1 state results in a GHL contact + workflow enrollment within one pipeline cycle (M10 acceptance).
- **Self-healing observable.** Injected scraper failure → detected, diagnosed, GitHub issue filed, manager email sent within ~10 minutes. No more than one email per unique failure fingerprint per 24h.
- **Watchdog independence.** Watchdog detects a stale agent heartbeat within 6 minutes and emails directly (mocked in tests, mocked + live in M10).
- **Dashboard usability.** Page load < 3 seconds on production-representative data. No technical jargon in the UI. CSV tier-upload works end-to-end (C-11, SC-07).

Business signals:

- **Cost displacement.** Total monthly run cost (enrichment + compliance + Railway + DataMerch) stays in the **$1,000–$1,700** band against an addressable market spending **$30K–$150K/yr** on bought lists.
- **Coverage breadth.** ~40 states scraping reliably (10 Tier 1, 24 Tier 2, 6 Tier 3); Tier 4 (DC, NYC) stubbed and skipped at MVP (C-17).
- **Constraint audit.** All 17 architectural constraints (C-01…C-17) have documented evidence at M10 sign-off.

## Scope

**In, for v1 (Milestones M1–M10):**

- Three Railway services (pipeline, agent, watchdog) sharing one Postgres
- ~40 state scrapers (Tier 1 + Tier 2 + Tier 3); APScheduler cadence
- MCA detection (alias map + fuzzy + shell patterns + collateral keywords) and lead scoring with hot/warm/cold tiers
- Enrichment waterfall (PDL → Apollo → OpenCorporates) with circuit breakers, permanent cache, retry queue, HALT semantics
- 4-layer compliance gate with append-only Internal DNC and audited reversal
- GHL adapter (upsert + tiered workflow + webhook receiver) + CSV fallback
- HTMX manager dashboard with pipeline health, scraper status, lead metrics, alerts, CSV tier upload
- LangGraph self-healing agent with GitHub repair loop and SendGrid alerts
- Independent watchdog with stale-heartbeat detection and lead-flow check during business hours
- Alembic migrations for all 13 tables, structlog JSON logging, Sentry in all three services, GitHub Actions CI (`pytest -m "not slow"` on PR, daily smoke schedule)

**Out, for v1 (explicit boundaries):**

- Tier 4 production scraping (DC, NYC) — stubs only
- Playwright-rendered scrapers in production (`playwright_base.py` exists but Tier 1+2+3 are httpx-based today)
- Any non-Python language or JS build toolchain (C-14)
- Any "export with warning" or compliance override path (C-02)
- Mutable Internal DNC without audit row (C-12)
- Multi-database / Redis / Kafka / per-service OLTP (C-04, C-05)
- Login / multi-user dashboard auth beyond Railway private networking or basic auth (C-11)

**Deferred to v2:**

- AI Learning Engine — disposition feedback → scoring evolution and conversion-pattern detection
- Third-party data-broker fallback for blocked states
- Alternative campaign platforms via new adapter classes (the seam exists; the work is per-platform)
- Playwright-based Tier 1 enhancement for JS-heavy portals

## Tech Stack (Snapshot)

| Layer | Choice | Version | Why |
|------|------|------|------|
| Language | Python | 3.12+ | C-14, best AI-codegen quality, Railway-native |
| Web | FastAPI + Uvicorn | 0.110+ / 0.27+ | Async-native HTTP for dashboard, webhook, health |
| DB | PostgreSQL via SQLAlchemy 2.0 async + asyncpg | 16+ / 2.0+ / 0.29+ | Single store for OLTP + queue + LangGraph state (C-05) |
| Migrations | Alembic | 1.13+ | Standard, AI-friendly |
| Scheduler | APScheduler | 3.10+ | In-process, no Redis (C-04) |
| HTTP | httpx | 0.27+ | Async, proxies, cookies for SOS portals |
| Headless | Playwright (base only) | 1.40+ | JS-portal capability, deferred |
| Parsing | BeautifulSoup4 | 4.12+ | HTML table extraction |
| Fuzzy match | rapidfuzz | 3.6+ | MCA alias matching |
| Circuit breaker | pybreaker | 1.0+ | Enrichment HALT (C-03) |
| Logging | structlog | 23.0+ | JSON logs for the agent + Railway |
| Errors | sentry-sdk | 2.0+ | Agent input + ops alerting |
| Agent | LangGraph + Anthropic | 0.2+ / 0.30+ | Cyclical self-healing graph |
| GitHub | PyGithub | 2.0+ | Agent issue/PR automation (C-16) |
| Email | sendgrid | 6.10+ | Manager alerts (agent + watchdog) |
| Phone | twilio | 9.0+ | Lookup + validation |
| Dashboard | Jinja2 + HTMX (CDN) + Tailwind (CDN) + Chart.js (CDN) | 3.1+ / 1.9 / 3.4 / 4.4 | No JS build toolchain (C-14) |
| Deploy | Railway (NIXPACKS) | — | C-04 |
| CI | GitHub Actions | — | C-16 |

## Constraints (Hard, Non-Negotiable)

All 17 architectural constraints carry over from the existing planning docs:

- **C-01** AI-maintainable code (short functions, docstrings, tests for everything)
- **C-02** Compliance gate is absolute (no bypass paths)
- **C-03** >20% enrichment errors in 5 min → HALT
- **C-04** Railway-only deployment
- **C-05** Single Postgres database for everything
- **C-06** `CampaignPlatformAdapter` is the only export surface
- **C-07** Watchdog has zero `app/` or `agent/` imports
- **C-08** Indefinite data retention; no TTL anywhere
- **C-09** Per-state rate limiting with jitter, backoff, proxy rotation for Tier 3
- **C-10** Cross-state dedup (exact + fuzzy)
- **C-11** Dashboard is non-technical, server-rendered, < 3 s
- **C-12** Internal DNC is append-only; reversal requires audit row
- **C-13** GHL custom fields pre-created (8 fields)
- **C-14** Python only, no JS build toolchain
- **C-15** DataMerch fallback path required (fail-open by default, configurable fail-closed)
- **C-16** GitHub as source of truth
- **C-17** Tiered scraping strategy (Tier 1 / 2 / 3, Tier 4 stubbed)

## Risks and Open Questions

| Risk | Mitigation | Constraint(s) |
|------|------------|---------------|
| State SOS portals change structure frequently | Per-scraper smoke tests on a scheduled (not PR) GitHub Action; self-healing agent diagnoses parser drift | C-09, C-17 |
| TCPA exposure from a single bypassed lead | Compliance milestone (M5) with negative tests; `require_compliance_cleared` enforced at adapter boundary | C-02, C-12 |
| Enrichment vendor outage | Per-source circuit breakers + permanent cache + retry queue + pipeline HALT semantics | C-03, C-08 |
| Self-healing agent makes a bad repair | Repair PR goes through CI; merge only on green; failures file priority-labeled GitHub issues; agent cannot touch compliance gate | C-16, AGENT-07 |
| DataMerch access denied / unconfigured | Fallback path with warning log; configurable `COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH` for strict deployments | C-15 |
| LangGraph API drift | Pinned floor in `pyproject.toml`; explicit state transitions tested | ADR-007 |
| Tier 3 IP bans | Proxy rotation, 10s minimum delay, jitter, backoff | C-09 |
| GHL API rate limits / breaking changes | Adapter isolation + CSV fallback + retry with exponential backoff | C-06 |

Open questions for v1 → v2:

1. Does DataMerch approval land in time, or do we ship with the documented fallback?
2. Tier 1 Playwright migration — when is it worth the operational cost? (Trigger: any Tier 1 state's httpx scraper consistently fails on JS-rendered pages.)
3. AI Learning Engine timing — when is the disposition signal volume high enough to be useful?

## Vision (2–3 Years Out)

A category-level shift: brokerages stop buying lead lists. Instead, every brokerage that wants in-house lead supply runs a UCC-style pipeline — possibly forks or self-hosts of this one, possibly hosted variants. The "compliance gate as a code invariant" pattern becomes table stakes. The AI-maintained, three-Railway-services + Postgres footprint becomes the reference architecture for one-operator regulated outbound systems.

In that world, this codebase's primary value isn't the scrapers (those constantly need maintenance) — it's the **shape**: the adapter seam at export, the irrevocable internal DNC, the agent/watchdog split, the structured-log → LangGraph diagnosis loop, and the "no human in the maintenance path" guarantee.
