# Codebase Concerns

**Analysis Date:** 2026-04-06

## Tech Debt

**Planning and onboarding docs out of sync with the repository:**

- Issue: `AGENTS.md` still states M1 has not been built, lists `pyproject.toml`, `app/main.py`, and other paths as "NOT YET CREATED," and claims no commands are available, while the repo contains a full Python package, tests, migrations, and three service entry points.
- Files: `AGENTS.md`
- Impact: New contributors and automation (e.g. GSD plan/execute) may underestimate delivered scope, skip existing patterns, or re-plan work that already exists.
- Fix approach: Refresh `AGENTS.md` "Commands" and "Key Files" to match current tree; align milestone language with `.kiln/master-plan.md` or a single source of truth.

**Kiln codebase state snapshot is stale:**

- Issue: `.kiln/docs/codebase-state.md` describes a greenfield tree with no `pyproject.toml`, no `app/`, and all milestones "not started."
- Files: `.kiln/docs/codebase-state.md`
- Impact: Architecture and milestone audits read as false negatives; risk of duplicate foundation work and conflicting narratives with `AGENTS.md` and the actual code.
- Fix approach: Regenerate or manually update the deliverable checklists and "Existing Files" section against the live tree.

**Self-healing repair path replaces entire files from LLM output:**

- Issue: `repair` in `agent/graph.py` asks the model for full file content and commits it via the GitHub Contents API, which can overwrite large modules in one shot if JSON parsing succeeds.
- Files: `agent/graph.py`
- Impact: High blast radius on bad or hallucinated patches; difficult review; potential secret leakage into commits if prompts/responses mishandled.
- Fix approach: Prefer minimal diffs, human-in-the-loop merge, or scoped patch application; add strict path allowlists and size limits; validate syntax/tests before PR creation.

**Large operational scripts:**

- Issue: `scripts/dashboard_local.py` is a very large single module mixing UI, env wiring, and integrations (per structure and grep patterns).
- Files: `scripts/dashboard_local.py`, `scripts/e2e_local.py`
- Impact: Hard to test, review, and reuse; easy to introduce env/secret handling inconsistencies next to `app/config.py`.
- Fix approach: Split into small modules; route configuration through `app/config.Settings` where appropriate; keep local-only defaults clearly isolated.

## Known Bugs

**No reproducible defects filed from static analysis:**

- Symptoms: Not detected in this pass.
- Files: Not applicable
- Trigger: Not applicable
- Workaround: Not applicable

## Security Considerations

**High-privilege GitHub token for automated repair:**

- Risk: `GITHUB_TOKEN` with repo contents and PR scope can push branches and open PRs; misconfiguration or compromised token has repository-wide impact.
- Files: `agent/graph.py`, `app/config.py`
- Current mitigation: Repair skips when `GITHUB_TOKEN` or `GITHUB_REPO` unset (`repair_skipped_no_github_config` path in `agent/graph.py`).
- Recommendations: Use fine-scoped tokens, branch protection, required reviews on default branch, and logging/alerting on auto-created PRs.

**Compliance gate fallback when DataMerch is unconfigured:**

- Risk: `check_datamerch` logs a warning and returns not-blocked when `DATAMERCH_API_KEY` is missing (`app/compliance/gate.py`), which matches documented fallback (C-15) but can silently weaken compliance in production if env is wrong.
- Files: `app/compliance/gate.py`, `app/config.py`
- Current mitigation: Warning log path when unconfigured.
- Recommendations: Fail closed in production profile or add an explicit `COMPLIANCE_STRICT` flag; monitor for `datamerch_unconfigured` in logs.

**Local scripts set placeholder Sentry DSN:**

- Risk: `scripts/e2e_local.py` and `scripts/dashboard_local.py` assign a placeholder `SENTRY_DSN` when unset, which could send events to an invalid project if copied into real env patterns.
- Files: `scripts/e2e_local.py`, `scripts/dashboard_local.py`
- Current mitigation: Intended for local convenience only.
- Recommendations: Document clearly; avoid mirroring this pattern in service entry points.

**Watchdog reads secrets from raw environment:**

- Risk: `watchdog/monitor.py` reads `DATABASE_URL`, `SENDGRID_API_KEY`, and `MANAGER_EMAIL` via `os.environ` (required by C-07 to avoid `app` imports); mis-set vars fail quietly for alerts (`send_alert` returns `False`).
- Files: `watchdog/monitor.py`, `watchdog/main.py`
- Current mitigation: Independence from pipeline package.
- Recommendations: Startup validation or health detail when alert channel is unconfigured; document required vars next to `app/config.py` in `.env.example`.

## Performance Bottlenecks

**New async engine per heartbeat check in watchdog:**

- Problem: `check_heartbeat` in `watchdog/monitor.py` creates and disposes an `create_async_engine` on each call inside the monitoring loop.
- Files: `watchdog/monitor.py`
- Cause: No long-lived pool reuse across iterations.
- Improvement path: Reuse a module-level engine or connection pool with proper lifecycle tied to FastAPI lifespan in `watchdog/main.py`.

**Tier-1 scrapers and Playwright:**

- Problem: States such as California use Playwright against WAF-protected portals (`app/scrapers/states/california.py`), which is CPU- and memory-heavy at scale.
- Files: `app/scrapers/states/california.py`, `app/scrapers/playwright_base.py`
- Cause: Browser automation for anti-bot surfaces.
- Improvement path: Concurrency caps, job queue back-pressure, dedicated worker sizing on Railway, caching of session tokens where legally and technically allowed.

## Fragile Areas

**External state SOS HTML and portal changes:**

- Files: `app/scrapers/states/*.py`, `app/scrapers/parsers.py`, `app/scrapers/base.py`
- Why fragile: Table layouts, query parameters, and WAF behavior change without notice; smoke tests are opt-in (`tests/smoke/test_scraper_smoke.py`, `pytest.mark.slow`).
- Safe modification: Run smoke tier manually after scraper edits; extend parser unit tests in `tests/unit/test_parsers.py` and `tests/unit/test_state_scrapers.py`.
- Test coverage: Live portal behavior not exercised in default CI (by design in smoke module docstring).

**Agent graph: JSON repair contract:**

- Files: `agent/graph.py`
- Why fragile: `json.loads(fix_text)` and path `file_path` from model output can throw or target wrong files; GitHub API errors branch to issue creation but do not rollback branch state automatically.
- Safe modification: Add schema validation, path prefix allowlist, and integration tests with mocked GitHub HTTP.

**Integration test named E2E is mostly in-process:**

- Files: `tests/integration/test_e2e_pipeline.py`
- Why fragile: Docstring claims full pipeline trace; several tests assert pure functions and interface presence (`callable(run_compliance_gate)`) rather than Postgres-backed flows, so regressions in DB wiring may not surface.
- Safe modification: Add true integration tests with database fixtures from `tests/conftest.py` and migration-aligned schema.

## Scaling Limits

**Single Postgres and job queue design:**

- Current capacity: One shared database per `AGENTS.md` / architecture intent; job queue uses `SELECT FOR UPDATE SKIP LOCKED` pattern in `app/services/job_queue.py`.
- Limit: Write throughput and connection pool size become bottlenecks under parallel scrapers and enrichment.
- Scaling path: Read replicas for reporting, pool tuning, horizontal workers with queue discipline; validate under load before production campaign volume.

## Dependencies at Risk

**Anthropic and Playwright stack:**

- Risk: Model ID strings and browser binaries are tied to external vendors; upgrades can change behavior or break CI images.
- Impact: Agent diagnosis/repair and scraper tiers depend on them.
- Migration plan: Pin versions in `pyproject.toml`; run smoke and agent integration tests on upgrade; keep fallback diagnosis path in `agent/graph.py` when API fails.

## Missing Critical Features

**Coverage vs ~45-state product goal:**

- Problem: `app/scrapers/registry.py` registers 42 state codes (10 tier 1 + 26 tier 2 + 6 tier 3); vision docs cite roughly 45 states.
- Blocks: Nationwide coverage parity and scheduling assumptions in `.kiln/docs/architecture.md`.
- Files: `app/scrapers/registry.py`

**Contract test suite absent:**

- Problem: `AGENTS.md` targets `tests/contract/`; repository has `tests/unit/`, `tests/integration/`, and `tests/smoke/` but no `tests/contract/` directory.
- Blocks: Formal external API contract verification (GHL, enrichment vendors) separate from unit tests.
- Files: `tests/` (missing subtree), `AGENTS.md`

**Agent `nodes/` package not present:**

- Problem: `AGENTS.md` describes `agent/nodes/`; implementation is monolithic in `agent/graph.py` with only `agent/heartbeat.py` and `agent/main.py` alongside.
- Blocks: Clear modularity for future graph node testing and ownership.
- Files: `agent/graph.py`, `AGENTS.md`

## Test Coverage Gaps

**Compliance gate with real database and external APIs:**

- What's not tested: End-to-end `run_compliance_gate` with populated `InternalDNC`, paid API mocks, and persistence of `ComplianceCheck` rows under failure modes.
- Files: `app/compliance/gate.py`, `tests/unit/test_compliance.py`
- Risk: Layer ordering and blocking semantics could drift without integration coverage.
- Priority: High

**GoHighLevel adapter against HTTP mocks or sandbox:**

- What's not tested: Live HTTP behavior of `GHLAdapter` (`upsert`, workflows, webhook parsing) beyond interface checks in `tests/integration/test_e2e_pipeline.py`.
- Files: `app/export/ghl_adapter.py`
- Risk: API version or payload mismatch breaks export silently after GHL changes.
- Priority: Medium

**Self-healing agent graph:**

- What's not tested: Full LangGraph cycle with checkpointing, GitHub API mocks, and repair success/failure branches.
- Files: `agent/graph.py`, `tests/unit/test_agent_main.py`
- Risk: Production-only failures on token scope, rate limits, or JSON repair format.
- Priority: High

---

*Concerns audit: 2026-04-06*
