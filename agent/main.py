"""Self-healing agent service entry point.

FastAPI application that runs the LangGraph self-healing agent on a schedule.
Heartbeat written every cycle. Health check at /health.
"""

import asyncio
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.db import get_engine
from app.logging import configure_logging

settings = Settings()

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, send_default_pii=False)

configure_logging()

AGENT_INTERVAL_SECONDS = 300  # 5 minutes between cycles


async def _agent_loop():
    """Run the self-healing agent on a recurring schedule."""
    from agent.graph import run_agent_cycle, write_heartbeat, compiled_graph  # noqa: F401
    from app.logging import get_logger
    log = get_logger("agent_loop")

    while True:
        try:
            await run_agent_cycle()
            log.info("agent_cycle_complete")
        except Exception as exc:
            log.error("agent_cycle_failed", error=str(exc))
        await asyncio.sleep(AGENT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start agent loop and heartbeat writer on startup, cancel on shutdown."""
    from agent.heartbeat import heartbeat_loop

    agent_task = asyncio.create_task(_agent_loop())
    heartbeat_task = asyncio.create_task(heartbeat_loop())
    yield
    heartbeat_task.cancel()
    agent_task.cancel()


app = FastAPI(title="UCC Agent", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Return service health status (200; use JSON `status` for degraded DB)."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "unreachable"}
