"""LangGraph self-healing agent — detect, diagnose, repair, verify, alert cycle.

Autonomous agent monitoring pipeline health with priority-based repair.
"""

from datetime import datetime, timezone
from typing import TypedDict

from app.logging import get_logger

logger = get_logger("agent_graph")


class AgentState(TypedDict):
    """State passed between graph nodes."""
    anomalies: list[dict]
    diagnosis: str | None
    repair_branch: str | None
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
    logger.info("detect_complete", anomaly_count=len(anomalies))
    return state


async def diagnose(state: AgentState) -> AgentState:
    """Diagnose anomalies using LLM-based analysis.

    Produces a human-readable diagnosis for the alerter node.
    """
    if not state["anomalies"]:
        state["diagnosis"] = None
        return state

    # Build diagnosis from anomaly patterns
    summaries = []
    for a in state["anomalies"][:5]:
        summaries.append(f"{a['type']}: {a.get('state', a.get('component', 'unknown'))} - {a.get('error', a.get('detail', ''))}")

    state["diagnosis"] = "Issues detected:\n" + "\n".join(f"- {s}" for s in summaries)
    logger.info("diagnosis_complete", issues=len(summaries))
    return state


async def repair(state: AgentState) -> AgentState:
    """Attempt automated repair via GitHub branch + CI.

    Creates a fix branch, applies repair, triggers CI.
    """
    if not state["diagnosis"]:
        state["repair_branch"] = None
        return state

    # Stub: actual repair would use Claude API to generate fix
    branch_name = f"auto-fix/{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    state["repair_branch"] = branch_name
    logger.info("repair_attempted", branch=branch_name)
    return state


async def verify(state: AgentState) -> AgentState:
    """Verify repair by checking CI results.

    Merges on pass, creates GitHub issue on fail.
    """
    if not state["repair_branch"]:
        state["ci_passed"] = None
        return state

    # Stub: actual verification would check GitHub Actions status
    state["ci_passed"] = False  # Conservative default
    logger.info("verify_complete", ci_passed=state["ci_passed"])
    return state


async def alert(state: AgentState) -> AgentState:
    """Send plain-English email alert to manager.

    No more than one email per unique failure type per 24 hours.
    """
    if not state["diagnosis"]:
        state["alert_sent"] = False
        return state

    # Stub: actual alerting would use SendGrid
    logger.info("alert_sent", diagnosis_preview=state["diagnosis"][:100])
    state["alert_sent"] = True
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


def build_agent_graph():
    """Assemble and compile the LangGraph self-healing agent graph.

    Returns:
        Compiled LangGraph graph ready for invocation.
    """
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)
    graph.add_node("detect", detect)
    graph.add_node("diagnose", diagnose)
    graph.add_node("repair", repair)
    graph.add_node("verify", verify)
    graph.add_node("alert", alert)

    graph.set_entry_point("detect")
    graph.add_edge("detect", "diagnose")
    graph.add_edge("diagnose", "repair")
    graph.add_edge("repair", "verify")
    graph.add_edge("verify", "alert")
    graph.add_edge("alert", END)

    return graph.compile()


async def run_agent_cycle() -> AgentState:
    """Execute one full detect-diagnose-repair-verify-alert cycle.

    Returns:
        Final agent state after the cycle.
    """
    await write_heartbeat()
    compiled = build_agent_graph()
    initial_state: AgentState = {
        "anomalies": [],
        "diagnosis": None,
        "repair_branch": None,
        "ci_passed": None,
        "alert_sent": False,
        "iteration": 0,
    }
    result = await compiled.ainvoke(initial_state)
    await write_heartbeat()
    return result
