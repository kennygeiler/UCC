"""Heartbeat watchdog service entry point.

Independent deadman switch that monitors the self-healing agent.
ZERO imports from app/ or agent/ packages per constraint C-07.
"""

import asyncio
import os

import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Initialize Sentry — read DSN directly from environment (no app.config import)
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))


async def _watchdog_loop():
    """Run the watchdog monitoring loop."""
    from watchdog.monitor import run_watchdog_loop
    await run_watchdog_loop()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start watchdog loop on startup, cancel on shutdown."""
    task = asyncio.create_task(_watchdog_loop())
    yield
    task.cancel()


app = FastAPI(title="UCC Watchdog", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "ok"}
