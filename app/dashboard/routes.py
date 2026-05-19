"""Dashboard HTTP routes — served from the pipeline service."""

import csv
import io
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app.dashboard.mca_lenders import router as mca_lenders_router
from app.export.csv_export import build_mca_accounts_csv, mca_export_filename
from app.dashboard.queries import (
    CONSOLIDATION_TIERS,
    get_account_detail,
    get_dashboard_stats,
    get_mca_lead_detail,
    get_recent_alerts,
    get_recent_scraper_runs,
    get_scraper_status,
    get_state_filing_lead_stats,
    search_accounts,
    search_filings,
    search_leads,
)
from app.logging import get_logger

logger = get_logger("dashboard")

router = APIRouter(prefix="/dashboard")
router.include_router(mca_lenders_router)
templates = Jinja2Templates(directory="app/dashboard/templates")

LEAD_TIER_CHIPS = CONSOLIDATION_TIERS

_fl_scrape_status: dict = {
    "running": False,
    "last_result": None,
    "last_error": None,
}


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard view — pipeline health overview."""
    stats = await get_dashboard_stats()
    recent_runs = await get_recent_scraper_runs(limit=8)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            **stats,
            "recent_scraper_runs": recent_runs,
            "fl_scrape": dict(_fl_scrape_status),
        },
    )


async def _run_fl_scrape_job() -> None:
    """Background FL scrape + consolidation pipeline."""
    from app.scrapers.states.florida import FloridaScraper

    _fl_scrape_status["running"] = True
    _fl_scrape_status["last_error"] = None
    try:
        scraper = FloridaScraper()
        count = await scraper.scrape()
        _fl_scrape_status["last_result"] = {
            "inserted": count,
            "status": "completed",
        }
    except Exception as exc:
        logger.error("fl_scrape_failed", error=str(exc))
        _fl_scrape_status["last_error"] = str(exc)[:500]
        _fl_scrape_status["last_result"] = {"status": "failed"}
    finally:
        _fl_scrape_status["running"] = False


@router.post("/scrapers/FL/run")
async def run_fl_scraper(request: Request, background_tasks: BackgroundTasks):
    """Manually trigger Florida scrape (no scheduler)."""
    if _fl_scrape_status.get("running"):
        msg = '<p class="text-amber-600">FL scrape already running.</p>'
        if request.headers.get("HX-Request"):
            return HTMLResponse(msg, status_code=409)
        return JSONResponse({"status": "already_running"}, status_code=409)
    background_tasks.add_task(_run_fl_scrape_job)
    msg = '<p class="text-blue-600">FL scrape started — refresh in a few minutes.</p>'
    if request.headers.get("HX-Request"):
        return HTMLResponse(msg)
    return JSONResponse({"status": "started"})


@router.get("/scrapers/FL/status")
async def fl_scraper_status():
    """JSON status for HTMX polling after manual FL run."""
    return JSONResponse(dict(_fl_scrape_status))


@router.get("/scrapers", response_class=HTMLResponse)
async def scraper_status(request: Request):
    """Scraper status by state — HTMX partial."""
    scrapers = await get_scraper_status()
    return templates.TemplateResponse(request, "partials/scrapers.html", context={"scrapers": scrapers})


@router.get("/scraper-runs", response_class=HTMLResponse)
async def recent_scraper_runs_partial(request: Request):
    """Recent scraper runs — HTMX partial."""
    runs = await get_recent_scraper_runs(limit=10)
    return templates.TemplateResponse(
        request,
        "partials/scraper_runs.html",
        context={"recent_scraper_runs": runs},
    )


@router.get("/state-coverage", response_class=HTMLResponse)
async def state_coverage_partial(request: Request):
    """Filings vs leads per state — HTMX partial."""
    state_coverage = await get_state_filing_lead_stats()
    return templates.TemplateResponse(
        request,
        "partials/state_coverage.html",
        context={"state_coverage": state_coverage},
    )


def _browse_filters(request: Request) -> dict:
    return dict(request.query_params)


def _pagination(
    page_path: str,
    table_path: str,
    filters: dict,
    *,
    limit: int,
    offset: int,
    total: int,
) -> dict:
    params = {k: v for k, v in filters.items() if v and k != "offset"}
    params["limit"] = str(limit)

    def _url(base: str, off: int) -> str:
        return f"{base}?{urlencode({**params, 'offset': str(max(0, off))})}"

    prev_off = offset - limit
    next_off = offset + limit
    return {
        "prev_page": _url(page_path, prev_off) if offset > 0 else None,
        "next_page": _url(page_path, next_off) if next_off < total else None,
        "prev_table": _url(table_path, prev_off) if offset > 0 else None,
        "next_table": _url(table_path, next_off) if next_off < total else None,
        "showing_from": offset + 1 if total else 0,
        "showing_to": min(offset + limit, total),
    }


async def _filings_context(request: Request) -> dict:
    filters = _browse_filters(request)
    limit = int(filters.get("limit", 50))
    offset = int(filters.get("offset", 0))
    data = await search_filings(
        state=filters.get("state"),
        debtor_name=filters.get("debtor_name"),
        secured_party=filters.get("secured_party"),
        limit=limit,
        offset=offset,
    )
    return {
        **data,
        "filters": filters,
        "pagination": _pagination(
            "/dashboard/filings",
            "/dashboard/filings/table",
            filters,
            limit=limit,
            offset=offset,
            total=data["total"],
        ),
    }


def _leads_export_filters(request: Request) -> dict:
    """Query params for MCA leads CSV export (mirrors browse filters)."""
    filters = _browse_filters(request)
    tier_filter = filters.get("tier", "") or filters.get("mca_tier", "") or filters.get("consolidation_tier", "")
    since_last = filters.get("since_last_run", "").lower() in ("1", "true", "yes")
    return {
        "state": filters.get("state") or "FL",
        "debtor_name": filters.get("debtor_name") or None,
        "tier": tier_filter or None,
        "consolidation_tier": tier_filter or None,
        "since_last_run": since_last,
    }


def _leads_export_url(filters: dict) -> str:
    params: dict[str, str] = {}
    if filters.get("state"):
        params["state"] = str(filters["state"])
    if filters.get("tier"):
        params["tier"] = str(filters["tier"])
    if filters.get("debtor_name"):
        params["debtor_name"] = str(filters["debtor_name"])
    if filters.get("since_last_run"):
        params["since_last_run"] = "1"
    qs = urlencode(params)
    return f"/dashboard/leads/export.csv?{qs}" if qs else "/dashboard/leads/export.csv"


async def _leads_context(request: Request) -> dict:
    filters = _browse_filters(request)
    limit = int(filters.get("limit", 50))
    offset = int(filters.get("offset", 0))
    tier_filter = filters.get("tier", "") or filters.get("mca_tier", "")

    data = await search_leads(
        state=filters.get("state"),
        debtor_name=filters.get("debtor_name"),
        tier=tier_filter or None,
        limit=limit,
        offset=offset,
    )
    export_filters = _leads_export_filters(request)
    return {
        **data,
        "filters": filters,
        "export_csv_url": _leads_export_url(export_filters),
        "tier_chips": LEAD_TIER_CHIPS,
        "active_tier": tier_filter,
        "pagination": _pagination(
            "/dashboard/leads",
            "/dashboard/leads/table",
            filters,
            limit=limit,
            offset=offset,
            total=data["total"],
        ),
    }


@router.get("/filings", response_class=HTMLResponse)
async def filings_browse(request: Request):
    return templates.TemplateResponse(request, "filings.html", context=await _filings_context(request))


@router.get("/filings/table", response_class=HTMLResponse)
async def filings_table_partial(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/filings_table.html",
        context=await _filings_context(request),
    )


@router.get("/leads", response_class=HTMLResponse)
async def leads_browse(request: Request):
    return templates.TemplateResponse(request, "leads_browse.html", context=await _leads_context(request))


@router.get("/leads/table", response_class=HTMLResponse)
async def leads_table_partial(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/leads_table.html",
        context=await _leads_context(request),
    )


@router.get("/leads/export.csv")
async def leads_export_csv(request: Request):
    """Download MCA funder accounts as CSV (same filters as browse)."""
    filt = _leads_export_filters(request)
    body = await build_mca_accounts_csv(
        state=filt["state"],
        debtor_name=filt["debtor_name"],
        tier=filt["tier"],
        consolidation_tier=filt["consolidation_tier"],
        since_last_run=filt["since_last_run"],
    )
    filename = mca_export_filename(state=filt["state"] or "FL", on_date=datetime.now(timezone.utc).date())
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads/accounts/{account_id}/detail", response_class=HTMLResponse)
async def mca_lead_detail_partial(request: Request, account_id: int):
    """HTMX partial — MCA funder account detail drawer."""
    detail = await get_mca_lead_detail(account_id)
    if detail is None:
        return HTMLResponse(
            "<p class='text-sm text-red-600'>MCA lead account not found.</p>",
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "partials/mca_lead_detail.html",
        context={"lead": detail},
    )


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_view(request: Request):
    alerts = await get_recent_alerts()
    return templates.TemplateResponse(request, "partials/alerts.html", context={"alerts": alerts})


async def _accounts_context(request: Request) -> dict:
    filters = _browse_filters(request)
    limit = int(filters.get("limit", 50))
    offset = int(filters.get("offset", 0))
    since_last = filters.get("since_last_run", "").lower() in ("1", "true", "yes")
    data = await search_accounts(
        state=filters.get("state", "FL"),
        tier=filters.get("tier"),
        since_last_run=since_last,
        limit=limit,
        offset=offset,
    )
    return {
        **data,
        "filters": filters,
        "tier_chips": CONSOLIDATION_TIERS,
        "active_tier": filters.get("tier", ""),
        "pagination": _pagination(
            "/dashboard/accounts",
            "/dashboard/accounts/table",
            filters,
            limit=limit,
            offset=offset,
            total=data["total"],
        ),
    }


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_browse(request: Request):
    return templates.TemplateResponse(
        request, "accounts_browse.html", context=await _accounts_context(request)
    )


@router.get("/accounts/table", response_class=HTMLResponse)
async def accounts_table_partial(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/accounts_table.html",
        context=await _accounts_context(request),
    )


@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail(request: Request, account_id: int):
    detail = await get_account_detail(account_id)
    if detail is None:
        return HTMLResponse("<p class='text-sm text-red-600'>Account not found.</p>", status_code=404)
    return templates.TemplateResponse(
        request,
        "account_detail.html",
        context={"account": detail},
    )


@router.post("/upload-tiers")
async def upload_tier_csv(file: UploadFile = File(...)):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode()))
    rows = list(reader)
    logger.info("tier_upload", rows=len(rows))
    return {"status": "uploaded", "rows_processed": len(rows)}
