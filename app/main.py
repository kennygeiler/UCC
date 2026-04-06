"""Pipeline service entry point.

FastAPI application for the UCC Lead Generation Platform pipeline service.
Initializes Sentry, structured logging, and database lifecycle management.
"""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings
from app.db import dispose_engine, get_engine
from app.logging import configure_logging

settings = Settings()

sentry_sdk.init(dsn=settings.SENTRY_DSN, send_default_pii=False)

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
    """Return service health status (200; use JSON `status` for degraded DB)."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "unreachable"}
