"""Pipeline service entry point.

FastAPI application for the UCC Lead Generation Platform pipeline service.
Initializes Sentry, structured logging, and database lifecycle management.
"""

from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.config import Settings
from app.db import dispose_engine, get_engine
from app.logging import configure_logging
from app.scrapers.scheduler import create_scheduler

settings = Settings()

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, send_default_pii=False)

configure_logging()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage application lifecycle — scheduler, DB engine disposal on shutdown."""
    scheduler = None
    if settings.SCRAPER_SCHEDULER_ENABLED:
        scheduler = create_scheduler()
        scheduler.start()
        application.state.scheduler = scheduler
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=True)
        await dispose_engine()


app = FastAPI(title="UCC Pipeline", lifespan=lifespan)

# Mount dashboard and webhook routes
from app.dashboard.routes import router as dashboard_router
from app.export.webhook import router as webhook_router

app.include_router(dashboard_router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    """Root URL — browsers default here; send them to the manager dashboard."""
    return RedirectResponse(url="/dashboard/", status_code=307)


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
