"""Self-healing agent service entry point.

Minimal FastAPI stub for the LangGraph-based self-healing agent.
Actual agent logic is implemented in Milestone 8.
"""

import os

import sentry_sdk
from fastapi import FastAPI

from app.logging import configure_logging

# Initialize Sentry before app creation
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))

# Configure structured logging
configure_logging()

app = FastAPI(title="UCC Agent")


@app.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "ok"}
