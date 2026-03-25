"""Enrichment pipeline — orchestrates waterfall enrichment for scored leads.

Feeds scored leads through the enrichment waterfall, caches results,
manages retry queue for failures.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import get_session
from app.enrichment.cache import get_cached, store_cached
from app.enrichment.circuit_breaker import is_any_breaker_open
from app.enrichment.sources import enrich_apollo, enrich_pdl, enrich_opencorporates
from app.enrichment.waterfall import WaterfallExecutor, WaterfallExhaustedError
from app.logging import get_logger
from app.models.lead import Lead
from app.models.job import EnrichmentRetryQueue
from app.models.operations import PipelineEvent

logger = get_logger("enrichment_pipeline")


def build_enrichment_waterfall() -> WaterfallExecutor:
    """Build the enrichment waterfall with configured sources."""
    return WaterfallExecutor([
        ("pdl", enrich_pdl),
        ("apollo", enrich_apollo),
        ("opencorporates", enrich_opencorporates),
    ])


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
        True if enrichment succeeded.
    """
    cache_key = f"{lead.debtor_name}|{lead.state}"
    cached = await get_cached("enrichment", cache_key)
    if cached:
        await _apply_enrichment(lead, cached)
        return True

    try:
        source, result = await waterfall.execute(
            business_name=lead.debtor_name, state=lead.state
        )
        await store_cached(source, cache_key, result)
        await _apply_enrichment(lead, result)
        return True
    except WaterfallExhaustedError:
        await _queue_retry(lead)
        return False


async def _apply_enrichment(lead: Lead, data: dict) -> None:
    """Apply enrichment data to a lead record.

    Args:
        lead: Lead to update.
        data: Enrichment data dict.
    """
    async with get_session() as session:
        lead.phone = data.get("phone")
        lead.email = data.get("email")
        lead.owner_name = data.get("owner_name")
        lead.estimated_revenue = data.get("revenue")
        lead.enrichment_status = "complete"
        session.add(lead)
    logger.info("lead_enriched", lead_id=lead.id, debtor=lead.debtor_name)


async def _queue_retry(lead: Lead) -> None:
    """Queue a failed enrichment for retry.

    Args:
        lead: Lead that failed enrichment.
    """
    async with get_session() as session:
        retry = EnrichmentRetryQueue(
            lead_id=lead.id,
            source="waterfall",
            attempt_count=1,
            next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(retry)
        lead.enrichment_status = "retry_queued"
        session.add(lead)
    logger.warning("enrichment_retry_queued", lead_id=lead.id)


async def check_pipeline_halt() -> bool:
    """Check if pipeline should halt due to circuit breaker failures.

    Returns:
        True if pipeline should halt.
    """
    if is_any_breaker_open():
        async with get_session() as session:
            event = PipelineEvent(
                event_type="HALT",
                component="enrichment",
                detail="Circuit breaker open — enrichment pipeline halted",
            )
            session.add(event)
        logger.error("pipeline_halt", component="enrichment")
        return True
    return False


async def run_enrichment_pipeline(batch_size: int = 50) -> int:
    """Process a batch of pending leads through enrichment.

    Args:
        batch_size: Max leads to process.

    Returns:
        Number of leads successfully enriched.
    """
    if await check_pipeline_halt():
        return 0

    leads = await get_pending_leads(batch_size)
    waterfall = build_enrichment_waterfall()
    enriched = 0

    for lead in leads:
        if await enrich_lead(lead, waterfall):
            enriched += 1

    logger.info("enrichment_run_complete", processed=len(leads), enriched=enriched)
    return enriched
