"""MCA lender alias CRUD and reclassification trigger."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select

from app.consolidation.classifier import reset_alias_class_cache
from app.dashboard.queries import list_mca_aliases, upsert_mca_alias
from app.db import get_session
from app.logging import get_logger
from app.models.mca_alias import MCAlias

logger = get_logger("dashboard.mca_lenders")

router = APIRouter(prefix="/mca-lenders")
templates = Jinja2Templates(directory="app/dashboard/templates")

_reclassify_status: dict = {
    "running": False,
    "last_result": None,
    "last_error": None,
}


def _pagination(
    table_path: str,
    filters: dict,
    *,
    limit: int,
    offset: int,
    total: int,
) -> dict:
    params = {k: v for k, v in filters.items() if v and k != "offset"}
    params["limit"] = str(limit)

    def _url(off: int) -> str:
        return f"{table_path}?{urlencode({**params, 'offset': str(max(0, off))})}"

    prev_off = offset - limit
    next_off = offset + limit
    return {
        "prev_table": _url(prev_off) if offset > 0 else None,
        "next_table": _url(next_off) if next_off < total else None,
        "showing_from": offset + 1 if total else 0,
        "showing_to": min(offset + limit, total),
    }


async def _aliases_context(request: Request) -> dict:
    filters = dict(request.query_params)
    limit = int(filters.get("limit", 100))
    offset = int(filters.get("offset", 0))
    data = await list_mca_aliases(
        search=filters.get("q"),
        limit=limit,
        offset=offset,
    )
    return {
        **data,
        "filters": filters,
        "pagination": _pagination(
            "/dashboard/mca-lenders/table",
            filters,
            limit=limit,
            offset=offset,
            total=data["total"],
        ),
        "reclassify": dict(_reclassify_status),
    }


async def _run_reclassify_job(state: str = "FL") -> None:
    from app.mca.refresh import refresh_mca_classification

    _reclassify_status["running"] = True
    _reclassify_status["last_error"] = None
    reset_alias_class_cache()
    try:
        result = await refresh_mca_classification(state)
        _reclassify_status["last_result"] = result
        logger.info("mca_reclassify_complete", **result)
    except Exception as exc:
        logger.error("mca_reclassify_failed", error=str(exc))
        _reclassify_status["last_error"] = str(exc)[:500]
        _reclassify_status["last_result"] = None
    finally:
        _reclassify_status["running"] = False


@router.get("", response_class=HTMLResponse)
async def mca_lenders_browse(request: Request):
    return templates.TemplateResponse(
        request, "mca_lenders.html", context=await _aliases_context(request)
    )


@router.get("/table", response_class=HTMLResponse)
async def mca_lenders_table(request: Request):
    return templates.TemplateResponse(
        request,
        "partials/mca_lenders_table.html",
        context=await _aliases_context(request),
    )


@router.post("", response_class=HTMLResponse)
async def mca_lender_create(
    request: Request,
    alias_name: str = Form(...),
    canonical_lender_name: str = Form(...),
    lender_class: str = Form("mca_funder"),
    consolidation_weight: float | None = Form(None),
    confidence: float = Form(1.0),
):
    await upsert_mca_alias(
        alias_name=alias_name,
        canonical_lender_name=canonical_lender_name,
        lender_class=lender_class or "mca_funder",
        consolidation_weight=consolidation_weight,
        confidence=confidence,
        source="dashboard",
    )
    reset_alias_class_cache()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "partials/mca_lenders_table.html",
            context=await _aliases_context(request),
        )
    return JSONResponse({"status": "created"})


@router.post("/{alias_id}", response_class=HTMLResponse)
async def mca_lender_update(
    request: Request,
    alias_id: int,
    alias_name: str = Form(...),
    canonical_lender_name: str = Form(...),
    lender_class: str = Form("mca_funder"),
    consolidation_weight: float | None = Form(None),
    confidence: float = Form(1.0),
):
    async with get_session() as session:
        row = await session.get(MCAlias, alias_id)
        if row is None:
            return HTMLResponse("<p class='text-red-600 text-sm'>Alias not found.</p>", status_code=404)
        row.alias_name = alias_name.strip()
        row.canonical_lender_name = canonical_lender_name.strip()
        row.lender_class = lender_class or "mca_funder"
        row.consolidation_weight = consolidation_weight
        row.confidence = confidence
    reset_alias_class_cache()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "partials/mca_lenders_table.html",
            context=await _aliases_context(request),
        )
    return JSONResponse({"status": "updated"})


@router.delete("/{alias_id}", response_class=HTMLResponse)
async def mca_lender_delete(request: Request, alias_id: int):
    async with get_session() as session:
        await session.execute(delete(MCAlias).where(MCAlias.id == alias_id))
    reset_alias_class_cache()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request,
            "partials/mca_lenders_table.html",
            context=await _aliases_context(request),
        )
    return JSONResponse({"status": "deleted"})


@router.post("/reclassify")
async def mca_reclassify(
    request: Request,
    background_tasks: BackgroundTasks,
    state: str = Form("FL"),
):
    if _reclassify_status.get("running"):
        msg = '<p class="text-amber-600 text-sm">Reclassification already running.</p>'
        if request.headers.get("HX-Request"):
            return HTMLResponse(msg, status_code=409)
        return JSONResponse({"status": "already_running"}, status_code=409)
    background_tasks.add_task(_run_reclassify_job, state.strip().upper())
    msg = '<p class="text-blue-600 text-sm">Reclassifying filings and refreshing MCA accounts…</p>'
    if request.headers.get("HX-Request"):
        return HTMLResponse(msg)
    return JSONResponse({"status": "started"})


@router.get("/reclassify/status")
async def mca_reclassify_status():
    return JSONResponse(dict(_reclassify_status))
