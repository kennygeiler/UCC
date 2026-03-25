"""Self-healing agent service entry point.

FastAPI application that runs the LangGraph self-healing agent on a schedule.
Heartbeat written every cycle. Health check at /health.
"""

import asyncio
import os

import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.logging import configure_logging

# Initialize Sentry before app creation
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))

# Configure structured logging
configure_logging()

AGENT_INTERVAL_SECONDS = 300  # 5 minutes between cycles


async def _agent_loop():
    """Run the self-healing agent on a recurring schedule."""
    from agent.graph import run_agent_cycle, write_heartbeat
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
    """Start agent loop on startup, cancel on shutdown."""
    task = asyncio.create_task(_agent_loop())
    yield
    task.cancel()


app = FastAPI(title="UCC Agent", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "ok"}
