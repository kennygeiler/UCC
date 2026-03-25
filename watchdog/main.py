"""Heartbeat watchdog service entry point.

Independent deadman switch that monitors the self-healing agent.
ZERO imports from app/ or agent/ packages per constraint C-07.
"""

import os

import sentry_sdk
from fastapi import FastAPI

# Initialize Sentry — read DSN directly from environment (no app.config import)
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))

app = FastAPI(title="UCC Watchdog")


@app.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "ok"}
