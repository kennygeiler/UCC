# Debate Resolution: Claude Plan vs Miyamoto Plan

## Agreements (Strong Signals — Adopted Directly)

Both plans agree on:

1. **Milestone 1 scope**: Project foundation, database schema, Alembic migrations, config, logging, health checks, FastAPI entry point. Both include all core tables.
2. **Milestone 2 scope**: Scraper engine with abstract base, registry, per-state rate limiting, httpx + Playwright, session management, APScheduler, smoke tests. Tier 1 states first.
3. **Milestone 3 scope**: MCA detection with alias matching, alias updater, lead scoring (position count, recency, collateral), pipeline wiring from scraper to scored leads.
4. **Milestone 4 scope**: Enrichment waterfall executor, all 6 sources, circuit breaker (pybreaker), permanent cache, retry queue with backoff, HALT mechanism, contract tests.
5. **Milestone 7 scope**: Dashboard with FastAPI + Jinja2 + HTMX + Tailwind CDN + Chart.js CDN, CSV upload for tier assignment, no technical jargon, <3s load time.
6. **Milestone 8 scope**: LangGraph self-healing agent with 5 nodes (detect, diagnose, repair, verify, alert), Postgres checkpointer, GitHub issue automation, heartbeat writer, priority-based repair.
7. **Milestone 9 scope**: Independent watchdog, 5-min check cycle, heartbeat staleness detection, lead flow check, direct SendGrid email, zero code dependency on other services, always restart policy.
8. **10 milestones total**, linear pipeline dependency chain for stages 1-6.
9. **Risk analysis**: Both identify the same major risks (SOS changes, anti-bot, DataMerch access, enrichment degradation, GHL changes, agent bad repairs, compliance bypass).
10. **All 17 constraints explicitly addressed** in both plans.

## Conflicts and Resolutions

### Conflict 1: CI/CD Placement

- **Claude Plan**: CI/CD is Milestone 10 (final milestone), bundled with deployment, integration testing, and Tier 2/3 state expansion.
- **Miyamoto Plan**: CI/CD is part of Milestone 1 (foundation), with GitHub Actions, Railway config, Procfile, railway.toml, and Sentry all established from day one.

**Resolution: Miyamoto's approach (CI/CD in Milestone 1).** Establishing CI from day one means every subsequent milestone inherits automated testing on push/PR. This aligns with C-01 (AI maintainability) and C-16 (GitHub as source of truth). Deferring CI to the final milestone means 9 milestones ship without automated pipeline protection. Railway service stubs with health checks in M1 also validate C-04 early.

### Conflict 2: Compliance and Dedup Grouping

- **Claude Plan**: Compliance (M5) and Dedup + Export (M6) are separate milestones. Dedup is grouped with campaign export, webhook receiver, and lead recycling.
- **Miyamoto Plan**: Compliance and Dedup are combined into a single M5. Export, webhooks, and recycling are a separate M6.

**Resolution: Claude's approach (separate compliance and dedup milestones).** The compliance gate (C-02) is the single most legally critical component. It deserves its own milestone with focused acceptance criteria and negative testing. Combining it with dedup dilutes focus. Dedup naturally pairs with export since both deal with the lead's journey to GHL.

### Conflict 3: Self-Healing Agent Dependencies

- **Claude Plan**: Agent (M8) depends on M1 + M2 + M4 — can start after enrichment is built. Positioned for parallel development alongside M5-M7.
- **Miyamoto Plan**: Agent (M8) depends on M1, M2, M4, and M5 — requires compliance events too.

**Resolution: Claude's approach (M1 + M2 + M4 dependencies).** The agent's core value is monitoring scrapers and enrichment — the two most failure-prone components. Compliance is a gate, not a monitoring target (it blocks or passes; it rarely breaks in ways the agent repairs). Starting agent work earlier enables parallel progress.

### Conflict 4: Tier 2/3 State Scraper Expansion

- **Claude Plan**: Tier 2/3 scrapers are deferred to M10 (final integration milestone).
- **Miyamoto Plan**: All tiers (Tier 1, 2, 3) are built in M2, with Tier 4 stubbed.

**Resolution: Miyamoto's approach (all tiers in M2).** SC-01 requires 45+ states. Building only Tier 1 (10 states) in M2 and deferring the rest to the final milestone creates a bottleneck. The scraper framework (base class, registry, rate limiter) is the same for all tiers — building them together is more coherent. Tier 4 (DC, NYC) remains skipped at MVP per C-17.

### Conflict 5: Sentry Integration Timing

- **Claude Plan**: Sentry SDK integration is in M10 (final milestone).
- **Miyamoto Plan**: Sentry SDK initialized in M1 for all three services.

**Resolution: Miyamoto's approach (Sentry in M1).** The self-healing agent (M8) reads Sentry events. Error tracking should be present from the first milestone so every subsequent milestone benefits from exception capture. Deferring it to M10 means 9 milestones run blind.

### Conflict 6: Final Milestone Scope

- **Claude Plan M10**: CI/CD + deployment + Tier 2/3 scrapers + Sentry + end-to-end testing.
- **Miyamoto Plan M10**: Pure end-to-end integration, hardening, production readiness, constraint audit.

**Resolution: Miyamoto's approach (M10 as pure integration/hardening).** With CI/CD, Sentry, and Tier 2/3 scrapers moved to earlier milestones, M10 becomes a focused integration and validation milestone. This is cleaner — the final milestone validates everything works together rather than introducing new infrastructure.

### Conflict 7: Postgres Job Queue Explicit Deliverable

- **Claude Plan**: Explicitly includes Postgres job queue implementation (SELECT FOR UPDATE SKIP LOCKED) as a M1 deliverable.
- **Miyamoto Plan**: Mentions job_queue table in schema but does not call out the queue implementation pattern as a deliverable.

**Resolution: Claude's approach (explicit job queue deliverable).** ADR-010 specifies this pattern. It is a non-trivial piece of infrastructure that other milestones depend on. Making it an explicit deliverable ensures it gets built and tested.

### Conflict 8: Dashboard Dependencies

- **Claude Plan**: Dashboard (M7) depends on M1, M2, M5, M6 — needs real data from all pipeline stages.
- **Miyamoto Plan**: Dashboard (M7) depends on M1 through M6 — requires all pipeline milestones.

**Resolution: Both essentially agree.** Dashboard needs data from all pipeline stages. Miyamoto is more explicit (lists M1-M6). Adopted as M1-M6 dependency.

## Plan Purity Sweep

Both plans contain some implementation-level detail that must be abstracted:

- **Claude Plan**: References specific file paths (app/dashboard/routes.py, app/main.py), specific API response patterns. These are stripped.
- **Miyamoto Plan**: References specific file paths extensively (app/scrapers/base.py, app/enrichment/waterfall.py, etc.), specific module names. These are stripped.

The master plan uses deliverable descriptions without file paths or function signatures.
