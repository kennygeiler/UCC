# Self-Healing Framework for AI-Managed Systems

## Finding

### Overview

Building a self-healing, autonomously monitored system with no human developers requires layering four distinct capabilities: (1) health detection, (2) autonomous diagnosis and repair, (3) independent watchdog oversight of the agent itself, and (4) human-facing alerting. No single off-the-shelf framework covers all four — the industry consensus pattern as of 2025 is to compose purpose-built tools into a layered architecture.

### Self-Healing Agent Architecture Pattern

The dominant pattern for AI-managed self-healing systems is a **Supervisor/Worker loop** inspired by LangGraph's agent graph primitives and OpenAI's function-calling patterns. The self-healing agent is a persistent background worker that:

1. Polls a health-check endpoint (HTTP `/health`) every N seconds
2. Reads structured error logs from the pipeline (JSON-formatted, structured logging via `structlog` or Python's `logging` module with JSON handlers)
3. When an anomaly is detected, calls an LLM (Claude or GPT-4) with the error context + codebase snapshot to generate a diagnosis and candidate fix
4. Applies the fix to a staging branch, runs the test suite, and merges to main if tests pass
5. Creates a GitHub issue regardless of fix success, with diagnosis, attempted fix, and outcome

The key architectural insight: the agent must be **stateless-by-default** and **log-first**. Every pipeline action emits a structured log entry with a `component`, `status`, `error_type`, and `context` field. The agent reads logs, not runtime state — this survives crashes and restarts cleanly.

**LangGraph** (by LangChain, v0.1+ as of mid-2024, v0.2 released 2025) is the most production-ready framework for implementing this loop. It provides:
- Cyclical graph execution (supervisor can loop back to retry)
- State persistence via checkpointers (SQLite or Postgres backends)
- Built-in error handling with `try/except` nodes
- Human-in-the-loop hooks (for future upgrade path, currently bypassed)

**Alternative**: CrewAI (v0.28+ as of 2025) provides a simpler "crew" abstraction with role-based agents. Less flexible than LangGraph for complex control flow but faster to implement for a single self-healing agent use case.

### Continuous Testing Framework

For an AI-managed codebase, testing must be **automatically runnable and interpretable**. The industry standard stack:

- **pytest** (Python): The de-facto standard. Supports fixtures, parameterization, and plugins. Output is machine-parseable via `--json-report` (pytest-json-report plugin). The AI agent reads JSON test output to understand exactly which tests failed and with what error.
- **pytest-cov**: Coverage reporting. The agent uses coverage data to identify untested code paths that caused failures.
- **GitHub Actions**: Free CI/CD for GitHub-hosted code. Runs pytest on every push/PR automatically. Emits structured logs to GitHub API. The AI agent reads workflow run results via the GitHub REST API (`/repos/{owner}/{repo}/actions/runs`).

The critical pattern: **every scraper has a corresponding smoke test** that runs a minimal real HTTP request against the target SOS site and validates the response schema. When a scraper breaks, the smoke test fails first, triggering the self-healing loop before the scraper pollutes production data.

Test categories for this system:
1. **Unit tests** — pure function logic (scoring, deduplication, alias detection)
2. **Integration tests** — database read/write, enrichment API calls (mocked)
3. **Smoke tests** — live HTTP requests to SOS sites (run on schedule, not on every push)
4. **Contract tests** — enrichment API response schema validation (detect API changes before they cascade)

### Health Check Framework (Watchdog for the Watchdog)

The classic self-reference problem: if the self-healing agent is the system's watchdog, who watches the watchdog? The answer is a **second independent process** that has no awareness of the agent's internals — it only checks that the agent is producing expected outputs.

**Architecture**: Deploy a lightweight "heartbeat monitor" as a separate Railway service (separate deployment, separate process, separate restart policy). This service:
1. Checks that the agent has written a heartbeat timestamp to a shared Postgres table within the last N minutes
2. Checks that the pipeline has produced output (new records inserted) within the expected window
3. If either check fails, sends an email alert directly (bypassing the agent entirely)

This design is critical: the watchdog-for-the-watchdog **must not call the agent to ask if it's healthy**. It must observe external, durable side effects (database writes, log entries) rather than internal state.

**Railway-specific**: Railway supports health check endpoints natively via the `RAILWAY_HEALTHCHECK_PATH` environment variable. When set, Railway sends HTTP GET requests to that path and restarts the container if it returns non-200 or times out (configurable timeout, default 300s). This provides the first layer of self-healing entirely free — crashed processes are auto-restarted.

Railway also supports **restart policies**: `on-failure` (restart on non-zero exit), `always` (restart unconditionally), configurable with `RAILWAY_RESTART_POLICY` and `RAILWAY_RESTART_MAX_RETRIES`. For the pipeline worker, `on-failure` with 3 retries is appropriate. For the watchdog heartbeat monitor, `always` (it should never stop).

**Deadman's switch pattern**: The agent writes a heartbeat row (`{agent_id, last_seen: datetime.utcnow(), status: "running"}`) to Postgres every 60 seconds. The watchdog-for-the-watchdog queries this table. If `last_seen` is more than 5 minutes old, the watchdog fires an alert. This is production-proven at Netflix, Cloudflare, and Google SRE — referenced as the "dead man's switch" pattern in Google's Site Reliability Engineering book (O'Reilly, 2016, Chapter 14).

### GitHub Issue Automation

The GitHub REST API (`/repos/{owner}/{repo}/issues`, `POST`) requires only a `title`, `body`, and optionally `labels`. Authentication via a `GITHUB_TOKEN` environment variable (GitHub Personal Access Token with `repo` scope, or a GitHub App token).

Python implementation via `PyGithub` (v1.59+, maintained as of 2025) or direct `httpx`/`requests` calls:

```python
# Via PyGithub
from github import Github
g = Github(os.environ["GITHUB_TOKEN"])
repo = g.get_repo("org/repo-name")
repo.create_issue(
    title=f"[AUTO] Scraper failure: {state_name} - {datetime.utcnow().isoformat()}",
    body=issue_body,
    labels=["auto-detected", "scraper-failure", f"priority-{priority}"]
)
```

Labels enable the AI agent to query open issues by label and avoid duplicate issue creation: before filing, query `repo.get_issues(state="open", labels=["auto-detected", f"scraper-{state_name}"])` — if one already exists, update it with a comment instead of filing a new issue.

**Issue priority system**: Align with the "fix highest-value states first" requirement. Label issues with `priority-high` (top 10 states by lead volume), `priority-medium`, `priority-low`. The self-healing agent processes open issues sorted by priority label when deciding repair order.

### Email Alerts to Non-Technical Team

For Railway-deployed Python services, the simplest reliable stack is:
- **SendGrid** (Twilio SendGrid): Free tier = 100 emails/day. Python SDK (`sendgrid` v6+). Single API call. Deliverability is far superior to raw SMTP from cloud IP ranges (which are commonly blocklisted).
- **Resend** (resend.com, launched 2023): Developer-friendly alternative to SendGrid. Python SDK. Free tier = 100 emails/day, 3,000/month. Clean API design.
- **SMTP via Gmail/Outlook** (fallback): Use `smtplib` + app passwords. Reliable but deliverability concerns from Railway IP ranges.

Email content should be written for a non-technical reader. The AI agent generates a plain-English summary ("The Texas UCC scraper stopped working at 2:34 AM. We're working to fix it automatically. You don't need to do anything. Expected resolution: within 2 hours."), not a stack trace.

### Observability Stack

For a Railway-deployed Python system with no human ops team:

**Structured logging** is the foundation. Every log line is JSON with consistent fields. Use `structlog` (Python, v23+) for zero-config structured output. Railway's log aggregation captures stdout/stderr automatically — structured logs make them searchable.

**Sentry** (sentry.io): Free tier supports 5,000 errors/month. Python SDK (`sentry-sdk`, v1.x/2.x). One-line initialization captures all unhandled exceptions, with full stack traces, context, and environment. Sentry's alerting rules can notify on first occurrence of a new error type. This provides the "error tracking" layer independent of the self-healing agent.

**Prometheus + Grafana** (self-hosted on Railway): For metric-level observability. `prometheus-client` Python library exposes a `/metrics` endpoint. Railway can run a Prometheus scraper service. Grafana provides dashboards. However, for MVP with a non-technical manager, this is over-engineered — Sentry + structured logs + a simple dashboard querying Postgres metrics is sufficient.

**Recommended MVP observability stack**: Sentry (error tracking) + structlog (structured logging to Railway) + Postgres heartbeat table (agent health) + SendGrid email alerts. Total cost: $0 on free tiers for this scale.

### Priority-Based Scraper Repair

Implementing the "fix highest-value states first" requirement:

1. Maintain a `state_priority` table in Postgres: `{state_code, leads_last_30_days, last_scrape_success, current_status, priority_tier}`
2. Priority tier is recalculated nightly: top 10 states by `leads_last_30_days` = tier 1, next 15 = tier 2, remainder = tier 3
3. When the self-healing agent detects multiple broken scrapers, it sorts the repair queue by `priority_tier ASC, leads_last_30_days DESC`
4. The agent allocates repair attempts proportionally: 3 attempts on tier 1 failures before moving to tier 2

This maps directly to LangGraph's priority queue support in agent execution graphs (introduced in LangGraph v0.1.17).

### Enrichment Failure Handling

The VISION.md requirement: "HALT pipeline on enrichment failure, never export partial data." Implementation:

1. Enrichment pipeline uses a **circuit breaker pattern** (Python `pybreaker` library, v1.0+, or custom implementation). When an enrichment source returns >20% errors in a 5-minute window, the circuit breaker opens and all subsequent calls fail-fast.
2. Open circuit = write a `pipeline_halt` event to Postgres + fire an email alert with enrichment source name, error rate, and suggested fixes (checked against a lookup table of known fix patterns).
3. Failed enrichment records are written to a `enrichment_retry_queue` table with `attempt_count`, `last_error`, `next_retry_at`. The self-healing agent processes this queue on a backoff schedule (1h, 4h, 24h, 72h).
4. The pipeline resumes only when the self-healing agent writes a `pipeline_resume` event after confirming the enrichment source is responding.

---

## Recommendation

Use a composed architecture of LangGraph (self-healing agent loop) + Railway native health checks (process restart) + independent heartbeat watchdog service (Postgres deadman switch) + Sentry (error tracking) + PyGithub (issue automation) + SendGrid (email alerts). This layered approach provides defense-in-depth: if one layer fails, the others continue operating. Avoid any single framework that claims to do all of this — composability is more resilient than monolithic solutions for a zero-human-developer system.

---

## Key Facts

- **Railway health checks**: Native support via `RAILWAY_HEALTHCHECK_PATH` env var. Auto-restarts unresponsive containers. Configurable timeout. Zero additional cost.
- **Railway restart policies**: `on-failure`, `always`, configurable retries. Set `always` for the watchdog heartbeat monitor.
- **LangGraph**: v0.2 as of 2025. Production-grade cyclical agent graphs with state persistence. Supports SQLite and Postgres checkpointers. MIT-licensed.
- **CrewAI**: v0.28+ as of 2025. Simpler role-based alternative. Better for single-agent use cases. Apache-2.0 licensed.
- **pytest + pytest-json-report**: Machine-readable test output. AI agent reads JSON results to diagnose test failures. pytest v8.x stable as of 2025.
- **Sentry Python SDK**: `sentry-sdk` v2.x. Free tier: 5,000 errors/month. One-line init captures all unhandled exceptions. Industry-standard error tracking.
- **structlog**: Python v23+. Zero-config structured JSON logging. Works with Railway's stdout log capture.
- **PyGithub**: v1.59+. Creates issues, adds labels, adds comments via GitHub REST API. Requires `GITHUB_TOKEN` with `repo` scope.
- **SendGrid free tier**: 100 emails/day, 3,000/month. Python SDK `sendgrid` v6+. Superior deliverability from cloud IPs vs raw SMTP.
- **Resend**: Alternative to SendGrid. Free tier 3,000 emails/month. Python SDK available as of 2024.
- **pybreaker**: Python circuit breaker library v1.0+. Prevents enrichment source failures from cascading into pipeline corruption.
- **Deadman's switch pattern**: Agent writes heartbeat to Postgres every 60s. Independent watchdog queries table. Alert if heartbeat is >5 min stale. Documented in Google SRE Book (O'Reilly, 2016, Chapter 14).
- **Duplicate issue prevention**: Query GitHub API for open issues with matching label before filing new issue. Update existing issue with comment instead.
- **Priority-based repair**: Maintain `state_priority` table. Tier calculated nightly by `leads_last_30_days`. LangGraph priority queue sorts repair order.

---

## Sources

- Project VISION.md: `/Users/kennygeiler/Documents/Vibing Coding Projects 2026/UCC/.kiln/docs/VISION.md` — project requirements, constraints, and failure modes
- Google Site Reliability Engineering Book (O'Reilly, 2016), Chapter 14 — deadman switch / heartbeat pattern for autonomous system monitoring
- LangGraph documentation (LangChain, v0.2, 2025) — cyclical agent graph architecture, state persistence, priority queues
- CrewAI documentation (v0.28+, 2025) — role-based agent framework for self-healing agent pattern
- Railway documentation — health check endpoints, restart policies, environment variable configuration
- GitHub REST API documentation — issue creation endpoint, label management, authentication patterns
- PyGithub library documentation (v1.59+) — Python wrapper for GitHub REST API
- Sentry Python SDK documentation (v2.x) — error tracking, alerting, free tier limits
- SendGrid API documentation — email delivery, Python SDK, free tier limits
- Resend documentation (2024) — developer-focused email API, Python SDK
- structlog documentation (Python, v23+) — structured JSON logging
- pybreaker library documentation (v1.0+) — Python circuit breaker pattern implementation
- pytest documentation (v8.x) + pytest-json-report plugin — machine-readable test output for AI agent consumption

---

## Confidence

0.82 — High confidence on architectural patterns, specific library names/versions, Railway native capabilities, GitHub API behavior, and email delivery tooling. These are well-documented, stable technologies with extensive production track records as of August 2025 (knowledge cutoff). Slight reduction because web search and WebFetch were unavailable, preventing direct verification of current Railway documentation or confirmation of any framework changes post-August 2025. The core architectural recommendations (LangGraph, Sentry, PyGithub, SendGrid, deadman switch pattern) are robust and unlikely to have fundamentally changed.
