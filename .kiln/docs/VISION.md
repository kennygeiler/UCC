# VISION.md — UCC Business Debt Lead Generation Platform

---

## 1. Problem Statement

**What:** Financial relief firms spend heavily on third-party lead generation services to find businesses burdened by Merchant Cash Advance (MCA) debt. These services are expensive, opaque, and deliver inconsistent lead quality. There is no in-house capability to identify, qualify, and contact distressed businesses directly.

**Who:** An internal financial relief firm with a team of 5 callers, 5 closers, and 1 non-technical manager. The firm has zero in-house developers — the entire system must be AI-built and AI-maintained.

**Why now:** UCC filings are public record across ~45 US states. The data exists to build an automated pipeline that identifies MCA-burdened businesses, enriches them into actionable leads, scrubs for legal compliance, and feeds them directly into campaign execution. Speed to lead is a competitive advantage — the firm that contacts a distressed business first wins the deal. Replacing third-party lead gen with an owned pipeline eliminates a major cost center and creates a proprietary data asset.

---

## 2. Target Users

**Primary User — Non-Technical Manager:**
- Job-to-be-done: Monitor pipeline health, understand lead flow, assign team tiers, and ensure campaigns are running on qualified, compliant leads.
- Needs a clean, high-level dashboard. No technical knowledge required.

**Secondary Users — Sales Team (5 Callers, 5 Closers):**
- Job-to-be-done: Receive pre-qualified, compliant leads through GoHighLevel campaigns and close deals.
- Interact with leads exclusively through GHL. Do not touch this system directly.

**Tertiary User — AI Agent (System Operator):**
- Job-to-be-done: Maintain, monitor, and self-heal the entire pipeline without human developer intervention.
- The system's own AI agent is a first-class user of the codebase.

---

## 3. Goals

1. **Eliminate third-party lead gen dependency** — build a fully owned, automated pipeline from public UCC filings to campaign-ready leads.
2. **Maximize speed to lead** — scrape, score, enrich, and deliver leads as fast as state SOS update cadences allow.
3. **Ensure 100% legal compliance** — no lead enters a campaign without passing DNC/TCPA scrub, litigator screening, and DataMerch check. Zero tolerance.
4. **Operate without human developers** — the system must be fully AI-managed with self-healing capabilities, automated testing, and autonomous issue resolution.
5. **Deliver actionable intelligence to a non-technical manager** — dashboard shows pipeline health, lead metrics, and compliance stats at a glance.
6. **Build a proprietary data asset** — store all data indefinitely for historical analysis and scoring improvement.
7. **Maintain platform agnosticism** — architect for GHL today, but design so the campaign platform can be swapped without rebuilding the pipeline.

---

## 4. Constraints

**Technical:**
- Deployed on Railway (cloud). Code hosted on GitHub.
- No human coders — 100% AI-managed codebase. Every fix, update, and feature is handled by AI agents.
- ~45 state Secretary of State websites with varying structures, update cadences, rate limits, and anti-bot measures.
- GoHighLevel integration via CSV upload (API exploration in research phase).

**Team:**
- 1 non-technical manager is the sole operator of this tool. UI must be intuitive and require zero technical knowledge.
- Sales team (10 people) never touches this system — they work exclusively in GHL.

**Regulatory:**
- DNC/TCPA compliance is a legal survival requirement. Violations carry severe financial penalties.
- Professional litigator screening is mandatory — contacting known TCPA litigators is an existential risk.
- Any DNC request received through ANY channel must result in permanent, irrevocable blocking.

**Operational:**
- Data stored indefinitely. No data expiration policy.
- Failed enrichment must never result in partially enriched leads entering campaigns.
- Deduplication must work across states and across scrape cycles.

---

## 5. Non-Goals

1. **No campaign execution in this tool.** GoHighLevel owns SMS, email, calls, funnels, and follow-up sequences. This tool is the source of truth for lead data only. Rationale: GHL is purpose-built for campaign execution; duplicating it creates maintenance burden and feature lag.

2. **No complex manager portal.** Tier assignment is manual CSV upload. No drag-and-drop team builders, no scheduling tools, no performance reviews. Rationale: the manager's job is to monitor the pipeline and assign tiers — nothing more. Keep it simple.

3. **No direct sales team interface.** Callers and closers never log into this system. Rationale: they live in GHL. Adding a sales-facing UI is scope creep with zero ROI.

4. **No AI-generated content for outreach.** This tool does not write SMS copy, email templates, or call scripts. Rationale: GHL handles campaign content. This tool delivers data, not messaging.

5. **No real-time scraping on demand.** Scraping runs on scheduled cadences matching state SOS update frequencies. Rationale: real-time scraping invites rate limiting and IP bans with minimal benefit over cadenced runs.

---

## 6. Tech Stack

No specific technology preferences from the operator. The AI agent will select the most scalable and maintainable stack during the architecture phase, optimized for:

- High-volume web scraping across ~45 heterogeneous state websites
- Data pipeline processing (scoring, enrichment, deduplication, compliance)
- Dashboard UI for a non-technical user
- Deployment on Railway
- Self-healing and automated testing capabilities
- Long-term data storage with historical query support

**Deployment:** Railway (cloud)
**Source Control:** GitHub
**Campaign Platform:** GoHighLevel (via CSV export; platform-agnostic architecture)

---

## 7. Success Criteria

- **SC-01:** Pipeline scrapes UCC filings from 45+ state SOS websites on cadence without manual intervention.
- **SC-02:** MCA alias detection correctly identifies MCA lenders and their known shell companies with a self-improving detection rate over time.
- **SC-03:** Lead scoring accurately ranks leads by financial distress level (position count), with hot leads (multiple filings) prioritized for top-tier campaigns.
- **SC-04:** Enrichment pipeline returns phone, email, revenue, and owner name for the majority of leads. Failed enrichments are bucketed for automatic resubmission.
- **SC-05:** 100% of leads exported to GHL have passed DNC/TCPA scrub, litigator screening, and DataMerch check. Zero non-compliant leads enter campaigns.
- **SC-06:** No duplicate leads exist in the system across states or scrape cycles.
- **SC-07:** Manager dashboard loads in under 3 seconds and displays real-time pipeline metrics without requiring technical knowledge to interpret.
- **SC-08:** Self-healing AI agent detects, diagnoses, and resolves scraper failures and enrichment errors autonomously, creating GitHub issues and sending email alerts.
- **SC-09:** Health check framework successfully monitors the AI agent itself (watchdog for the watchdog) and alerts on agent failures.
- **SC-10:** Lead recycling correctly re-queues disposition-tagged leads (e.g., "have debt, not interested") for new campaigns after the configured cooldown period (default: 30 days).
- **SC-11:** The system operates with zero human developer intervention for routine maintenance, fixes, and monitoring.

---

## 8. Risks & Unknowns

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R-01 | State SOS websites change structure, breaking scrapers | High | High | Self-healing AI agent with automated detection and repair. Fix highest-value states first. Prioritize fixes around what is working. |
| R-02 | Anti-bot measures (CAPTCHAs, rate limits, IP blocks) on state SOS sites | High | High | Research phase maps technical landscape per state. Fallback to third-party data brokers for blocked states (V2). |
| R-03 | DNC/TCPA compliance failure leads to legal action | Low (by design) | Critical | Hard compliance gate — non-compliant leads NEVER enter GHL. Daily automatic scrub. Professional litigator screening. Permanent DNC blocking on any request through any channel. |
| R-04 | Enrichment source APIs change, degrade, or become cost-prohibitive | Medium | High | Pipeline HALTS on enrichment failure — never exports partially enriched leads. Failed enrichments bucketed for resubmission. Multiple enrichment sources for redundancy. |
| R-05 | Self-healing AI agent itself fails or creates bad fixes | Medium | High | Health check framework monitors the AI agent (watchdog for watchdog). Automated testing validates all changes before deployment. |
| R-06 | GoHighLevel changes CSV import format or API | Low | Medium | Platform-agnostic architecture. CSV export layer is isolated and swappable. |
| R-07 | MCA lenders create new shell companies faster than detection adapts | Medium | Medium | Self-improving MCA alias detection engine. Daily analysis job. Historical pattern matching. |
| R-08 | Data storage costs grow unbounded with indefinite retention | Low | Low | Monitor storage costs. Archive cold data if needed. Railway scaling handles growth. |
| R-09 | No human developers available for emergency fixes | High (permanent) | High | Entire system designed for AI self-management. Comprehensive automated testing. Multiple alert channels. |

---

## 9. Open Questions

**OQ-1**: Which enrichment data sources and APIs are most reliable and cost-effective for phone, email, revenue, and owner name lookups? | Priority: high | Timing: before-build | Context: The enrichment pipeline is core to lead quality. Source selection determines data accuracy, cost per lead, and API reliability. Multiple sources needed for redundancy.

**OQ-2**: Which DNC/TCPA scrubbing services are optimal — free vs. paid — and what are their update frequencies? | Priority: high | Timing: before-build | Context: Compliance is a legal survival requirement. The chosen service must support daily automatic scrubbing and have comprehensive, up-to-date DNC lists.

**OQ-3**: Where can professional litigator lists be sourced, and how frequently are they updated? | Priority: high | Timing: before-build | Context: Contacting known TCPA litigators is an existential legal risk. The list source must be comprehensive and current.

**OQ-4**: What is DataMerch's API availability, pricing, and integration approach for MCA default history lookups? | Priority: high | Timing: before-build | Context: DataMerch scrub is a required step in the compliance gate. Need to confirm programmatic access is available and understand rate limits.

**OQ-5**: What is the state-by-state SOS website technical landscape — which states have CAPTCHAs, rate limits, IP blocking, or other anti-bot measures? | Priority: high | Timing: before-build | Context: Determines scraping strategy per state, which states launch at MVP, and where fallback data sources are needed.

**OQ-6**: What are GoHighLevel's CSV import specifications and API capabilities for lead upload and disposition feedback? | Priority: high | Timing: before-build | Context: GHL is the campaign execution platform. Integration approach (CSV vs API) affects automation level and disposition feedback loop design.

**OQ-7**: What is the best self-healing and monitoring framework for an AI-managed system with no human developers? | Priority: high | Timing: before-build | Context: The system must operate autonomously. Framework choice determines how effectively the AI agent can detect, diagnose, and resolve issues.

**OQ-8**: What is the optimal tech stack for scalable web scraping + data pipeline + dashboard deployed on Railway? | Priority: high | Timing: before-build | Context: Stack selection affects development speed, scalability, Railway compatibility, and AI agent maintainability.

**OQ-9**: What continuous testing frameworks work best for AI-managed codebases where the AI agent writes and maintains tests? | Priority: medium | Timing: before-build | Context: Testing is the safety net for an AI-managed system. Framework must support automated test generation, execution, and reporting.

---

## 10. Key Decisions

| Decision | Alternatives Considered | Rationale |
|----------|------------------------|-----------|
| Build in-house lead gen pipeline vs. continue buying from third-party brokers | Third-party lead gen services | Cost reduction, data ownership, speed to lead advantage, proprietary data asset, quality control. |
| GoHighLevel for campaign execution, this tool for lead data only | Build campaign execution into this tool | GHL is purpose-built for campaigns. Separation of concerns. Avoids duplicating mature functionality. |
| CSV export to GHL (MVP) | Direct API integration | Simpler MVP. CSV is reliable and well-understood. API integration can be explored in V2. |
| 100% AI-managed with self-healing agent | Hire developers | Team has no developers. AI management is a core requirement, not a preference. Self-healing agent is the only viable path. |
| HALT pipeline on enrichment failure | Export partial data with flags | Partially enriched leads waste sales team time and risk compliance gaps. Clean data or no data. |
| Fix highest-value states first when scraping breaks | Fix in order of failure, or fix all simultaneously | Maximizes revenue impact of fixes. Keeps lead flow running on the most valuable sources while lower-priority states are repaired. |
| Platform-agnostic architecture (prepare for GHL replacement) | Tight GHL integration | GHL may not be the long-term platform. Isolated export layer makes swapping painless. |
| Indefinite data storage | Time-based data expiration | Historical data enables scoring improvement, trend analysis, and reprocessing. Storage is cheap relative to data value. |
| Hard compliance gate (non-contactable leads NEVER enter GHL) | Soft flags with manual review | Zero tolerance is the only legally defensible position. Manual review does not scale and introduces human error risk. |
| Watchdog-for-the-watchdog health check design | Trust the AI agent to self-report | An agent monitoring itself has a blind spot for its own failures. Independent health checks close the loop. |
| Lead recycling based on disposition tags with configurable cooldown | Permanent removal of uninterested leads | "Not interested now" is not "not interested ever." Recycling with cooldown respects the prospect's current state while preserving future opportunity. |
| Manual tier assignment via CSV | Automated tier assignment by algorithm | Manager knows the team. Simple CSV upload keeps control where it belongs without over-engineering team management. |

---

## 11. Elicitation Log

| Method | Key Output |
|--------|------------|
| Problem framing | Identified core problem: expensive, opaque third-party lead gen. Solution: owned pipeline from UCC filings to GHL campaigns. |
| User persona mapping | Three user types: non-technical manager (primary), sales team (secondary, GHL-only), AI agent (system operator). |
| Pipeline architecture walkthrough | 7-stage pipeline: Scrape > Detect > Score > Enrich > Comply > Dedupe > Export. Each stage elicited independently. |
| Constraint elicitation | Hard constraints: Railway deployment, zero developers, DNC/TCPA compliance, non-technical manager UI. |
| Failure mode analysis | Three critical failure modes explored: self-healing paradox (watchdog for watchdog), enrichment cascade (HALT, never export partial), scraping fragility (fix highest-value first). |
| Stress testing | Challenged assumptions on AI self-management, partial data exports, and multi-state scraping resilience. All three answered with clear operational policies. |
| MVP vs. V2 scoping | 13 features in MVP (all day 1), 3 features deferred to V2. Aggressive but deliberate scope. |
| Integration boundary mapping | Clear boundary: this tool = lead data source of truth, GHL = campaign execution source of truth. Platform-agnostic architecture. |

---

## 12. Visual Direction

No visual direction specified. Build will proceed without design system generation.

---

*Generated during brainstorm phase. All content approved by operator.*
