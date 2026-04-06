"""Enrichment pipeline — orchestrates waterfall enrichment for scored leads.

Feeds scored leads through the enrichment waterfall, caches results,
manages retry queue for failures.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.db import get_session
from app.enrichment.backoff import next_backoff_seconds
from app.enrichment.cache import (
    ENRICHMENT_CACHE_SOURCE,
    enrichment_cache_key,
    get_cached,
    store_cached,
)
from app.enrichment.circuit_breaker import BREAKERS, is_any_breaker_open
from app.enrichment.normalize import enrichment_meets_bar, normalize_vendor_response
from app.enrichment.rate_tracker import get_rate_tracker
from app.enrichment.sources import enrich_apollo, enrich_pdl, enrich_opencorporates
from app.enrichment.waterfall import WaterfallExecutor, WaterfallExhaustedError
from app.logging import get_logger
from app.models.job import EnrichmentRetryQueue
from app.models.lead import Lead
from app.models.operations import PipelineEvent

logger = get_logger("enrichment_pipeline")

_halt_event_logged: bool = False


def _on_waterfall_attempt(source: str) -> None:
    get_rate_tracker().record_attempt(source)


def _on_waterfall_failure(source: str, exc: Exception) -> None:
    tracker = get_rate_tracker()
    tracker.record_failure(source)
    if tracker.should_trip(source):
        br = BREAKERS.get(source)
        if br:
            br.open()
        tracker.halted = True


def build_enrichment_waterfall() -> WaterfallExecutor:
    """Build the enrichment waterfall with configured sources and breakers."""
    return WaterfallExecutor(
        [
            ("pdl", enrich_pdl),
            ("apollo", enrich_apollo),
            ("opencorporates", enrich_opencorporates),
        ],
        breakers=BREAKERS,
        on_attempt=_on_waterfall_attempt,
        on_failure=_on_waterfall_failure,
    )


async def get_pending_leads(batch_size: int = 50) -> list[Lead]:
    """Fetch leads with enrichment_status='pending'.

    Args:
        batch_size: Maximum leads to process per batch.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Lead)
            .where(Lead.enrichment_status == "pending")
            .limit(batch_size)
        )
        return list(result.scalars().all())


async def enrich_lead(lead: Lead, waterfall: WaterfallExecutor) -> bool:
    """Enrich a single lead through the waterfall.

    Args:
        lead: Lead to enrich.
        waterfall: Configured waterfall executor.

    Returns:
        True if enrichment succeeded and completeness bar met (or cache hit that meets bar).
    """
    async with get_session() as session:
        fresh = await session.get(Lead, lead.id)
    if fresh is not None:
        lead = fresh

    cache_key = enrichment_cache_key(lead.debtor_name, lead.state)
    cached = await get_cached(ENRICHMENT_CACHE_SOURCE, cache_key)

    if cached:
        return await _apply_enrichment(lead, cached)

    try:
        source, raw = await waterfall.execute(
            business_name=lead.debtor_name, state=lead.state
        )
        normalized = normalize_vendor_response(source, raw)
        await store_cached(ENRICHMENT_CACHE_SOURCE, cache_key, normalized)
        return await _apply_enrichment(lead, normalized)
    except WaterfallExhaustedError as exc:
        err_msg = str(exc)[:500]
        await _queue_retry(lead, last_error=err_msg)
        return False


async def _apply_enrichment(lead: Lead, data: dict) -> bool:
    """Apply enrichment data to a lead record.

    Sets ``enrichment_status`` to ``complete`` only when :func:`enrichment_meets_bar`
    returns True; otherwise ``incomplete``.

    Args:
        lead: Lead to update.
        data: Canonical enrichment dict.

    Returns:
        True if status is ``complete``.
    """
    complete = enrichment_meets_bar(data)
    status = "complete" if complete else "incomplete"
    async with get_session() as session:
        row = await session.get(Lead, lead.id)
        if row is None:
            return False
        row.phone = data.get("phone")
        row.email = data.get("email")
        row.owner_name = data.get("owner_name")
        row.estimated_revenue = data.get("estimated_revenue")
        row.enrichment_status = status
    logger.info(
        "lead_enriched",
        lead_id=lead.id,
        debtor=lead.debtor_name,
        status=status,
    )
    if complete:
        await _clear_retry_row(lead.id)
    return complete


async def _clear_retry_row(lead_id: int) -> None:
    async with get_session() as session:
        await session.execute(
            delete(EnrichmentRetryQueue).where(EnrichmentRetryQueue.lead_id == lead_id)
        )


async def _queue_retry(lead: Lead, last_error: str = "") -> None:
    """Queue a failed enrichment for retry with exponential backoff."""
    async with get_session() as session:
        result = await session.execute(
            select(EnrichmentRetryQueue).where(EnrichmentRetryQueue.lead_id == lead.id)
        )
        existing = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            n = existing.attempt_count + 1
            existing.attempt_count = n
            existing.source = "waterfall"
            existing.last_error = last_error[:500] if last_error else existing.last_error
            existing.next_retry_at = now + timedelta(seconds=next_backoff_seconds(n))
        else:
            n = 1
            session.add(
                EnrichmentRetryQueue(
                    lead_id=lead.id,
                    source="waterfall",
                    attempt_count=n,
                    last_error=last_error[:500] if last_error else None,
                    next_retry_at=now + timedelta(seconds=next_backoff_seconds(n)),
                )
            )
        row = await session.get(Lead, lead.id)
        if row:
            row.enrichment_status = "retry_queued"
    logger.warning(
        "enrichment_retry_queued",
        lead_id=lead.id,
        component="enrichment",
        status="retry_queued",
        error_type="WaterfallExhausted",
        context=last_error[:200] if last_error else "",
    )


async def check_pipeline_halt() -> bool:
    """Return True if enrichment must stop (circuit open or error-rate HALT)."""
    global _halt_event_logged
    tracker = get_rate_tracker()
    halted = is_any_breaker_open() or tracker.halted
    if not halted:
        return False
    if not _halt_event_logged:
        _halt_event_logged = True
        async with get_session() as session:
            session.add(
                PipelineEvent(
                    event_type="HALT",
                    component="enrichment",
                    detail="Enrichment halted: circuit open or error-rate threshold",
                )
            )
        logger.error(
            "pipeline_halt",
            component="enrichment",
            status="halted",
            error_type="HALT",
            context="enrichment",
        )
    return True


def reset_halt_logging_for_tests() -> None:
    """Reset HALT event dedupe (tests only)."""
    global _halt_event_logged
    _halt_event_logged = False


async def run_enrichment_pipeline(batch_size: int = 50) -> int:
    """Process a batch of pending leads through enrichment.

    Args:
        batch_size: Max leads to process.

    Returns:
        Number of leads marked complete in this batch.
    """
    if await check_pipeline_halt():
        logger.info(
            "enrichment_run_skipped",
            component="enrichment",
            status="halted",
            error_type="HALT",
            context="batch",
        )
        return 0

    leads = await get_pending_leads(batch_size)
    waterfall = build_enrichment_waterfall()
    complete_count = 0

    for lead in leads:
        if await enrich_lead(lead, waterfall):
            complete_count += 1

    logger.info(
        "enrichment_run_complete",
        processed=len(leads),
        enriched_complete=complete_count,
    )
    return complete_count
