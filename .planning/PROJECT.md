# UCC Lead Generation Platform

## What This Is

Automated US-wide UCC (Uniform Commercial Code) lead pipeline: scrape public Secretary of State filings, detect MCA-burdened businesses, enrich and score leads, enforce a four-layer legal compliance gate, deduplicate across states, and export compliant leads to GoHighLevel—with a manager-facing dashboard, a LangGraph self-healing agent, and an independent heartbeat watchdog. Built for AI-only maintenance (short modules, tests, structured logging) and Railway deployment.

**GSD note:** This `PROJECT.md` was initialized from existing repo sources—`AGENTS.md`, `.kiln/master-plan.md`, and `.planning/codebase/*`. Refine scope here as delivery progresses.

## Core Value

**Compliant, qualified MCA leads reach GHL without bypassing the compliance gate or platform-abstraction rules**—everything else is secondary to legal safety and adapter-isolated export.

## Requirements

### Validated

Capabilities evidenced by the current tree and `.planning/codebase/ARCHITECTURE.md` (brownfield snapshot; verify during phase work):

- ✓ Python 3.12+ package layout with `pyproject.toml`, pytest, and CI (`/.github/workflows/ci.yml`) — existing
- ✓ Three FastAPI entrypoints—`app/main.py`, `agent/main.py`, `watchdog/main.py`—and Railway-oriented process layout — existing
- ✓ Shared PostgreSQL schema via SQLAlchemy 2.0 async models (`app/models/`) and Alembic migrations (`migrations/`) — existing
- ✓ Pipeline subsystems present in code: scraping (`app/scrapers/`), MCA handling (`app/mca/`), enrichment (`app/enrichment/`), compliance (`app/compliance/`), export (`app/export/`), dashboard (`app/dashboard/`) — existing
- ✓ Operational services: LangGraph-style agent (`agent/`), independent watchdog (`watchdog/`) — existing
- ✓ MCA detection and scoring (Phase 3): state-scoped position counts, fuzzy/shell/collateral matching, filing-scoped lead pipeline with `debtor_name_normalized`, `mca_tier`, `source_filing_id`, optional nightly alias updater — tested.
- ✓ Enrichment (Phase 4): waterfall + breakers, aggregate Postgres cache, rolling error-rate HALT, retry backoff + scheduler job, normalized vendor mapping + completeness bar, contract fixtures — tested.

### Active

Work tracked in `.planning/REQUIREMENTS.md` and phased in `.planning/ROADMAP.md`—drives completion, hardening, and evidence against `.kiln/master-plan.md` milestones and constraints C-01–C-17.

### Out of Scope

| Exclusion | Reason |
|-----------|--------|
| Tier 4 (e.g. DC, NYC) full production scraping at MVP | Explicitly stubbed/skipped per master plan; revisit after core tiers |
| Non–Python UI toolchain (SPA bundler) | C-14: server-rendered dashboard only |
| Human-operated codebase without tests/logging | C-01 / project charter |
| Direct GHL imports from generic pipeline modules | C-06: `CampaignPlatformAdapter` only |
| Watchdog importing `app/` or `agent/` | C-07 |

## Context

- **Authoritative engineering narrative:** `.kiln/docs/architecture.md`, `.kiln/master-plan.md` (10 milestones, dependency graph, risk/constraints tables).
- **Live codebase map:** `.planning/codebase/*` (stack, structure, architecture, conventions, testing, integrations, concerns).
- **Cursor/AGENTS onboarding:** `AGENTS.md` (may lag repo; `.planning/codebase/CONCERNS.md` flags staleness).
- **Enrichment/compliance domains** are regulation-heavy; DataMerch fallback and DNC behavior are contractually critical (C-02, C-12, C-15).

## Constraints

- **C-01–C-17** (see `AGENTS.md` / `.kiln/docs/arch-constraints.md`): AI-maintainable code, absolute compliance gate, enrichment halt rules, Railway + single Postgres, adapter abstraction, three independent services, no enrichment TTL, rate limits, dedup, manager-simple dashboard, irrevocable internal DNC, GHL field prerequisites, Python-only surface for product code, DataMerch fallback, GitHub as source of truth, tiered scraping.
- **Deployment:** Railway; production secrets via platform env (never commit `.env` contents).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Align GSD phases to Kiln master-plan milestone boundaries | Dependencies already ordered (scrape → MCA → enrich → comply → export → dashboard; agent/watchdog parallel after foundation) | — Pending |
| Skip separate GSD domain web research at init | Kiln artifacts + codebase map already document domain and stack | ✓ Good |
| Track detailed v1 scope in `REQUIREMENTS.md` | Enables 100% roadmap coverage and traceability | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):

1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):

1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-06 — Phase 4 (Enrichment) complete*
