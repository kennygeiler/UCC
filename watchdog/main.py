"""Heartbeat watchdog service entry point.

Independent deadman switch that monitors the self-healing agent.
ZERO imports from app/ or agent/ packages per constraint C-07.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from watchdog.logging_config import configure_logging

configure_logging()

sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""), send_default_pii=False)

_monitor_started = False


async def _watchdog_loop():
    """Run the watchdog monitoring loop."""
    from watchdog.monitor import run_watchdog_loop

    await run_watchdog_loop()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start watchdog loop on startup, cancel on shutdown."""
    global _monitor_started
    task = asyncio.create_task(_watchdog_loop())
    _monitor_started = True
    yield
    task.cancel()


app = FastAPI(title="UCC Watchdog", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Return service health status."""
    return {
        "status": "ok",
        "monitor": "active" if _monitor_started else "stopped",
    }
