"""Pipeline service entry point.

FastAPI application for the UCC Lead Generation Platform pipeline service.
Initializes Sentry, structured logging, and database lifecycle management.
"""

import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from app.db import dispose_engine
from app.logging import configure_logging

# Initialize Sentry before app creation
sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN", ""))

# Configure structured logging
configure_logging()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application lifecycle — dispose DB engine on shutdown."""
    yield
    await dispose_engine()


app = FastAPI(title="UCC Pipeline", lifespan=lifespan)

# Mount dashboard and webhook routes
from app.dashboard.routes import router as dashboard_router
from app.export.webhook import router as webhook_router

app.include_router(dashboard_router)
app.include_router(webhook_router)


@app.get("/health")
async def health_check():
    """Return service health status."""
    return {"status": "ok"}
