"""Dashboard HTTP routes — served from the pipeline service."""

import csv
import io

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dashboard.queries import get_dashboard_stats, get_scraper_status, get_recent_alerts
from app.logging import get_logger

logger = get_logger("dashboard")

router = APIRouter(prefix="/dashboard")
templates = Jinja2Templates(directory="app/dashboard/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard view — pipeline health overview."""
    stats = await get_dashboard_stats()
    return templates.TemplateResponse(request, "dashboard.html", context=stats)


@router.get("/scrapers", response_class=HTMLResponse)
async def scraper_status(request: Request):
    """Scraper status by state — HTMX partial."""
    scrapers = await get_scraper_status()
    return templates.TemplateResponse(request, "partials/scrapers.html", context={"scrapers": scrapers})


@router.get("/leads", response_class=HTMLResponse)
async def lead_metrics(request: Request):
    """Lead counts by stage — HTMX partial."""
    stats = await get_dashboard_stats()
    return templates.TemplateResponse(request, "partials/leads.html", context=stats)


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_view(request: Request):
    """Recent pipeline alerts — HTMX partial."""
    alerts = await get_recent_alerts()
    return templates.TemplateResponse(request, "partials/alerts.html", context={"alerts": alerts})


@router.post("/upload-tiers")
async def upload_tier_csv(file: UploadFile = File(...)):
    """Upload CSV for manual rep tier assignment (C-11).

    Expects CSV with columns: name, phone, tier.
    """
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode()))
    rows = list(reader)
    logger.info("tier_upload", rows=len(rows))
    return {"status": "uploaded", "rows_processed": len(rows)}
