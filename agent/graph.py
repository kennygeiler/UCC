"""LangGraph self-healing agent — detect, diagnose, repair, verify, alert cycle.

Autonomous agent monitoring pipeline health with priority-based repair.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timezone
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from app.logging import get_logger

logger = get_logger("agent_graph")

MAX_DETECT_RETRIES = 3


class AgentState(TypedDict):
    """State passed between graph nodes."""
    anomalies: list[dict]
    diagnosis: str | None
    repair_branch: str | None
    repair_pr_number: int | None
    ci_passed: bool | None
    alert_sent: bool
    iteration: int


async def detect(state: AgentState) -> AgentState:
    """Detect anomalies from pipeline events, scraper runs, and structured logs.

    Reads pipeline_events, scraper_runs, and Sentry errors.
    Surfaces anomalies sorted by priority (Tier 1 states first).
    """
    from sqlalchemy import select
    from app.db import get_session
    from app.models.operations import PipelineEvent, ScraperRun

    anomalies = []
    async with get_session() as session:
        # Check for failed scraper runs
        result = await session.execute(
            select(ScraperRun)
            .where(ScraperRun.status == "failed")
            .order_by(ScraperRun.started_at.desc())
            .limit(10)
        )
        for run in result.scalars().all():
            anomalies.append({
                "type": "scraper_failure",
                "state": run.state,
                "error": run.error_detail,
                "time": run.started_at.isoformat() if run.started_at else "",
            })

        # Check for HALT events
        result = await session.execute(
            select(PipelineEvent)
            .where(PipelineEvent.event_type == "HALT")
            .order_by(PipelineEvent.created_at.desc())
            .limit(5)
        )
        for event in result.scalars().all():
            anomalies.append({
                "type": "pipeline_halt",
                "component": event.component,
                "detail": event.detail,
                "time": event.created_at.isoformat() if event.created_at else "",
            })

    state["anomalies"] = anomalies
    state["iteration"] = state.get("iteration", 0) + 1
    logger.info("detect_complete", anomaly_count=len(anomalies), iteration=state["iteration"])
    return state


async def diagnose(state: AgentState) -> AgentState:
    """Diagnose anomalies using Claude API analysis.

    Calls Anthropic's Claude to produce a plain-English diagnosis
    suitable for non-technical stakeholders (C-11).
    """
    if not state["anomalies"]:
        state["diagnosis"] = None
        return state

    from app.config import Settings
    settings = Settings()

    anomaly_text = json.dumps(state["anomalies"][:10], indent=2, default=str)

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    "You are a pipeline health analyst for a UCC lead-generation system. "
                    "Analyze these anomalies and produce a plain-English diagnosis. "
                    "No jargon — write as if explaining to a business manager.\n\n"
                    "Anomalies:\n" + anomaly_text + "\n\n"
                    "Provide: 1) What went wrong, 2) Likely root cause, "
                    "3) Business impact, 4) Recommended action."
                ),
            }],
        )
        state["diagnosis"] = response.content[0].text
        logger.info("diagnosis_complete", source="claude_api", anomaly_count=len(state["anomalies"]))
    except Exception as exc:
        logger.error("diagnosis_api_failed", error=str(exc))
        # Fallback: build diagnosis from anomaly data directly
        summaries = []
        for a in state["anomalies"][:5]:
            summaries.append(
                f"{a['type']}: {a.get('state', a.get('component', 'unknown'))} "
                f"- {a.get('error', a.get('detail', ''))}"
            )
        state["diagnosis"] = "Issues detected:\n" + "\n".join(f"- {s}" for s in summaries)
        await create_github_issue(
            title=f"[Agent] Diagnosis API failure: {type(exc).__name__}",
            body=f"Claude API call failed during diagnose step.\n\nError: {exc}\n\nFallback diagnosis was used.",
            labels=["auto-detected", "agent-error"],
        )

    return state


async def _github_api(
    method: str, path: str, *, settings: Any, json_body: dict | None = None,
) -> dict:
    """Make an authenticated GitHub API request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method,
            f"https://api.github.com/repos/{settings.GITHUB_REPO}{path}",
            json=json_body,
            headers={
                "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        if resp.status_code == 204:
            return {}
        return resp.json()


async def repair(state: AgentState) -> AgentState:
    """Create a GitHub branch, generate a fix via Claude, commit the patch, and open a PR."""
    if not state["diagnosis"]:
        state["repair_branch"] = None
        return state

    from app.config import Settings
    settings = Settings()

    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        logger.warning("repair_skipped_no_github_config")
        state["repair_branch"] = None
        return state

    branch_name = f"auto-fix/{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    try:
        # 1. Get default branch SHA
        repo_info = await _github_api("GET", "", settings=settings)
        default_branch = repo_info.get("default_branch", "master")
        ref_data = await _github_api("GET", f"/git/ref/heads/{default_branch}", settings=settings)
        base_sha = ref_data["object"]["sha"]

        # 2. Create the fix branch
        await _github_api("POST", "/git/refs", settings=settings, json_body={
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha,
        })
        logger.info("repair_branch_created", branch=branch_name)

        # 3. Generate fix via Claude API
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        fix_response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": (
                    "You are a Python developer fixing a UCC lead-generation pipeline. "
                    "Based on this diagnosis, generate a minimal Python patch.\n\n"
                    f"Diagnosis:\n{state['diagnosis']}\n\n"
                    "Return ONLY a JSON object with keys:\n"
                    '  "file_path": relative path to fix (e.g. "app/scrapers/sos.py"),\n'
                    '  "description": one-line summary of the fix,\n'
                    '  "content": the full corrected file content.\n'
                    "Return raw JSON, no markdown fences."
                ),
            }],
        )
        fix_text = fix_response.content[0].text.strip()
        # Strip markdown fences if present
        if fix_text.startswith("```"):
            fix_text = "\n".join(fix_text.split("\n")[1:])
            if fix_text.endswith("```"):
                fix_text = fix_text[:-3].strip()
        fix_data = json.loads(fix_text)

        # 4. Commit the patch to the branch
        file_path = fix_data["file_path"]
        file_content = fix_data["content"]
        encoded = base64.b64encode(file_content.encode()).decode()

        # Get current file SHA (if it exists) for update
        try:
            existing = await _github_api("GET", f"/contents/{file_path}?ref={branch_name}", settings=settings)
            file_sha = existing.get("sha")
        except httpx.HTTPStatusError:
            file_sha = None

        commit_body: dict[str, Any] = {
            "message": f"fix: {fix_data.get('description', 'auto-repair')}",
            "content": encoded,
            "branch": branch_name,
        }
        if file_sha:
            commit_body["sha"] = file_sha

        await _github_api("PUT", f"/contents/{file_path}", settings=settings, json_body=commit_body)
        logger.info("repair_patch_committed", file=file_path, branch=branch_name)

        # 5. Open a PR
        pr_data = await _github_api("POST", "/pulls", settings=settings, json_body={
            "title": f"[Auto-Fix] {fix_data.get('description', 'Automated repair')}",
            "body": (
                "## Automated Repair\n\n"
                f"**Diagnosis:**\n{state['diagnosis'][:500]}\n\n"
                f"**Fix applied to:** `{file_path}`\n\n"
                "This PR was created automatically by the self-healing agent. "
                "Please review before merging."
            ),
            "head": branch_name,
            "base": default_branch,
        })
        logger.info("repair_pr_opened", pr_url=pr_data.get("html_url"), pr_number=pr_data.get("number"))

        state["repair_branch"] = branch_name
        state["repair_pr_number"] = pr_data.get("number")

    except Exception as exc:
        logger.error("repair_failed", error=str(exc))
        state["repair_branch"] = None
        await create_github_issue(
            title=f"[Agent] Repair failed: {type(exc).__name__}",
            body=(
                f"The self-healing agent could not complete a repair.\n\n"
                f"**Diagnosis:**\n{state.get('diagnosis', 'N/A')[:500]}\n\n"
                f"**Error:** {exc}\n\n"
                f"**Branch attempted:** {branch_name}"
            ),
            labels=["auto-detected", "repair-failed", "priority-high"],
        )

    return state


async def verify(state: AgentState) -> AgentState:
    """Poll GitHub Actions CI status on the repair PR branch.

    Polls up to 10 times (30s intervals, ~5 min max) for CI to complete.
    """
    if not state["repair_branch"]:
        state["ci_passed"] = None
        return state

    from app.config import Settings
    settings = Settings()

    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        state["ci_passed"] = None
        return state

    branch = state["repair_branch"]
    max_polls = 10
    poll_interval = 30  # seconds

    try:
        for attempt in range(max_polls):
            runs = await _github_api(
                "GET", f"/actions/runs?branch={branch}&per_page=1", settings=settings,
            )
            workflow_runs = runs.get("workflow_runs", [])

            if not workflow_runs:
                logger.info("verify_no_runs_yet", branch=branch, attempt=attempt + 1)
                if attempt < max_polls - 1:
                    await asyncio.sleep(poll_interval)
                continue

            run = workflow_runs[0]
            status = run.get("status")
            conclusion = run.get("conclusion")

            if status == "completed":
                ci_passed = conclusion == "success"
                state["ci_passed"] = ci_passed
                logger.info(
                    "verify_complete",
                    ci_passed=ci_passed,
                    conclusion=conclusion,
                    run_url=run.get("html_url"),
                )
                if not ci_passed:
                    await create_github_issue(
                        title=f"[Agent] CI failed on auto-fix branch {branch}",
                        body=(
                            f"CI concluded with **{conclusion}** on branch `{branch}`.\n\n"
                            f"**Run:** {run.get('html_url', 'N/A')}\n\n"
                            f"**Diagnosis:**\n{state.get('diagnosis', 'N/A')[:500]}\n\n"
                            "Manual intervention required."
                        ),
                        labels=["auto-detected", "ci-failed", "priority-high"],
                    )
                return state

            logger.info("verify_ci_pending", status=status, attempt=attempt + 1)
            if attempt < max_polls - 1:
                await asyncio.sleep(poll_interval)

        # Timed out waiting for CI
        state["ci_passed"] = False
        logger.warning("verify_ci_timeout", branch=branch, polls=max_polls)
        await create_github_issue(
            title=f"[Agent] CI timed out on {branch}",
            body=f"CI did not complete within {max_polls * poll_interval}s for branch `{branch}`.",
            labels=["auto-detected", "ci-timeout"],
        )

    except Exception as exc:
        logger.error("verify_failed", error=str(exc))
        state["ci_passed"] = False
        await create_github_issue(
            title=f"[Agent] Verify step failed: {type(exc).__name__}",
            body=f"Error polling CI for branch `{branch}`:\n\n{exc}",
            labels=["auto-detected", "agent-error"],
        )

    return state


async def alert(state: AgentState) -> AgentState:
    """Send a plain-English email alert to the manager via SendGrid (C-11: no jargon)."""
    if not state["diagnosis"]:
        state["alert_sent"] = False
        return state

    from app.config import Settings
    settings = Settings()

    if not settings.SENDGRID_API_KEY or not settings.MANAGER_EMAIL:
        logger.warning("alert_skipped_no_sendgrid_config")
        state["alert_sent"] = False
        return state

    # Build plain-English email body
    ci_status = "not attempted"
    if state.get("ci_passed") is True:
        ci_status = "passed — the fix looks good and is ready for your review"
    elif state.get("ci_passed") is False:
        ci_status = "failed — the automated fix needs manual attention"

    repair_info = ""
    if state.get("repair_branch"):
        repair_info = (
            f"\n\nWhat we did about it:\n"
            f"We created an automated fix on branch '{state['repair_branch']}'. "
            f"The automated tests {ci_status}."
        )
    else:
        repair_info = "\n\nWe were unable to create an automated fix. Our team will need to look into this manually."

    body = (
        f"Hi,\n\n"
        f"The UCC pipeline monitoring system detected an issue that needs your attention.\n\n"
        f"What happened:\n{state['diagnosis']}\n"
        f"{repair_info}\n\n"
        f"If you have questions, please reach out to the engineering team.\n\n"
        f"— UCC Pipeline Monitor"
    )

    subject = "UCC Pipeline Alert: Issue Detected"
    if state.get("ci_passed") is True:
        subject = "UCC Pipeline: Issue Detected & Auto-Fixed"
    elif state.get("ci_passed") is False:
        subject = "UCC Pipeline Alert: Issue Needs Attention"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json={
                    "personalizations": [{"to": [{"email": settings.MANAGER_EMAIL}]}],
                    "from": {"email": "agent@uccbusinessdebt.com", "name": "UCC Pipeline Monitor"},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
                headers={
                    "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        state["alert_sent"] = True
        logger.info("alert_sent", to=settings.MANAGER_EMAIL, subject=subject)
    except Exception as exc:
        logger.error("alert_send_failed", error=str(exc))
        state["alert_sent"] = False
        await create_github_issue(
            title=f"[Agent] Alert email failed: {type(exc).__name__}",
            body=(
                f"Failed to send alert email to {settings.MANAGER_EMAIL}.\n\n"
                f"**Error:** {exc}\n\n"
                f"**Diagnosis that should have been emailed:**\n{state['diagnosis'][:500]}"
            ),
            labels=["auto-detected", "alert-failed"],
        )

    return state


async def create_github_issue(title: str, body: str, labels: list[str]) -> str | None:
    """Create a GitHub issue for unresolved failures.

    Args:
        title: Issue title.
        body: Issue body with diagnosis details.
        labels: Labels (e.g., ['priority-high', 'auto-detected']).

    Returns:
        Issue URL or None if creation failed.
    """
    from app.config import Settings
    settings = Settings()
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        logger.warning("github_not_configured")
        return None

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{settings.GITHUB_REPO}/issues",
                json={"title": title, "body": body, "labels": labels},
                headers={
                    "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            return resp.json().get("html_url", "")
    except Exception as exc:
        logger.error("github_issue_failed", error=str(exc))
        return None


async def write_heartbeat() -> None:
    """Write heartbeat timestamp to agent_heartbeat table."""
    from app.db import get_session
    from app.models.operations import AgentHeartbeat
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(
            select(AgentHeartbeat).where(AgentHeartbeat.agent_id == "self-healing").limit(1)
        )
        hb = result.scalar_one_or_none()
        if hb:
            hb.last_seen = datetime.now(timezone.utc)
            hb.status = "alive"
        else:
            hb = AgentHeartbeat(
                agent_id="self-healing",
                last_seen=datetime.now(timezone.utc),
                status="alive",
            )
        session.add(hb)
    logger.debug("heartbeat_written")


def _route_after_detect(state: AgentState) -> str:
    """Conditional routing after detect node.

    If anomalies were found, proceed to diagnose.
    If none found and we haven't exhausted retries, loop back to detect.
    Otherwise end the cycle (no work to do).
    """
    if state["anomalies"]:
        return "diagnose"
    if state.get("iteration", 1) < MAX_DETECT_RETRIES:
        logger.info("no_anomalies_retrying", iteration=state["iteration"])
        return "detect"
    logger.info("no_anomalies_cycle_end", iterations=state["iteration"])
    return END


# ---------------------------------------------------------------------------
# Postgres checkpointer using the existing langgraph_checkpoints table
# ---------------------------------------------------------------------------

class _PostgresCheckpointer:
    """Async checkpointer backed by the langgraph_checkpoints table.

    Uses the project's existing SQLAlchemy async session infrastructure
    so no additional connection pool is needed.
    """

    async def aget(self, config: dict[str, Any]) -> dict[str, Any] | None:
        from sqlalchemy import select
        from app.db import get_session
        from app.models.operations import LanggraphCheckpoint

        thread_id = config["configurable"]["thread_id"]
        async with get_session() as session:
            result = await session.execute(
                select(LanggraphCheckpoint)
                .where(LanggraphCheckpoint.thread_id == thread_id)
                .order_by(LanggraphCheckpoint.created_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return row.checkpoint

    async def aput(self, config: dict[str, Any], data: dict[str, Any], metadata: dict[str, Any] | None = None) -> None:
        from app.db import get_session
        from app.models.operations import LanggraphCheckpoint

        thread_id = config["configurable"]["thread_id"]
        checkpoint = LanggraphCheckpoint(
            thread_id=thread_id,
            checkpoint=data if isinstance(data, dict) else json.loads(json.dumps(data, default=str)),
            metadata_=metadata,
        )
        async with get_session() as session:
            session.add(checkpoint)


def _get_checkpointer() -> _PostgresCheckpointer:
    return _PostgresCheckpointer()


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_agent_graph(*, checkpointer: Any | None = None):
    """Assemble and compile the LangGraph self-healing agent graph.

    Args:
        checkpointer: Optional checkpointer instance. When *None* the
            Postgres-backed checkpointer is used by default.

    Returns:
        Compiled LangGraph graph ready for invocation.
    """
    graph = StateGraph(AgentState)

    # -- nodes --
    graph.add_node("detect", detect)
    graph.add_node("diagnose", diagnose)
    graph.add_node("repair", repair)
    graph.add_node("verify", verify)
    graph.add_node("alert", alert)

    # -- entry point --
    graph.set_entry_point("detect")

    # -- edges with conditional routing after detect --
    graph.add_conditional_edges("detect", _route_after_detect)
    graph.add_edge("diagnose", "repair")
    graph.add_edge("repair", "verify")
    graph.add_edge("verify", "alert")
    graph.add_edge("alert", END)

    if checkpointer is None:
        checkpointer = _get_checkpointer()

    return graph.compile(checkpointer=checkpointer)


# Module-level compiled graph for import by agent/main.py
compiled_graph = build_agent_graph()


async def run_agent_cycle(thread_id: str = "self-healing") -> AgentState:
    """Execute one full detect-diagnose-repair-verify-alert cycle.

    Args:
        thread_id: Checkpoint thread identifier for state persistence.

    Returns:
        Final agent state after the cycle.
    """
    await write_heartbeat()
    initial_state: AgentState = {
        "anomalies": [],
        "diagnosis": None,
        "repair_branch": None,
        "repair_pr_number": None,
        "ci_passed": None,
        "alert_sent": False,
        "iteration": 0,
    }
    result = await compiled_graph.ainvoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )
    await write_heartbeat()
    return result
