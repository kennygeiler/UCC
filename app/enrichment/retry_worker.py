"""Process ``enrichment_retry_queue`` rows when due (ENRICH-04)."""

from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.db import get_session
from app.enrichment.pipeline import build_enrichment_waterfall, check_pipeline_halt, enrich_lead
from app.logging import get_logger
from app.models.job import EnrichmentRetryQueue
from app.models.lead import Lead

logger = get_logger("enrichment_retry_worker")


async def process_enrichment_retries(batch_size: int = 20) -> int:
    """Re-run enrichment for due retry rows (respects HALT).

    Args:
        batch_size: Max rows to claim per run.

    Returns:
        Number of leads that reached ``enrichment_status=complete``.
    """
    if await check_pipeline_halt():
        logger.info(
            "enrichment_retry_batch_skipped",
            component="enrichment",
            status="halted",
            error_type="HALT",
            context="retry",
        )
        return 0

    now = datetime.now(timezone.utc)
    waterfall = build_enrichment_waterfall()
    complete_count = 0

    async with get_session() as session:
        result = await session.execute(
            select(EnrichmentRetryQueue)
            .where(EnrichmentRetryQueue.next_retry_at <= now)
            .order_by(EnrichmentRetryQueue.next_retry_at)
            .limit(batch_size)
        )
        rows = list(result.scalars().all())

    for rq in rows:
        async with get_session() as session:
            lead = await session.get(Lead, rq.lead_id)
            if lead is None:
                await session.execute(
                    delete(EnrichmentRetryQueue).where(EnrichmentRetryQueue.id == rq.id)
                )
                continue
            lead.enrichment_status = "pending"

        try:
            ok = await enrich_lead(lead, waterfall)
        except Exception as exc:
            logger.error(
                "enrichment_retry_lead_failed",
                component="enrichment",
                status="failed",
                error_type=type(exc).__name__,
                context=str(exc)[:200],
            )
            ok = False
        if ok:
            complete_count += 1

        async with get_session() as session:
            row = await session.get(Lead, rq.lead_id)
            if row and row.enrichment_status == "incomplete":
                await session.execute(
                    delete(EnrichmentRetryQueue).where(EnrichmentRetryQueue.id == rq.id)
                )

        logger.info(
            "enrichment_retry_processed",
            component="enrichment",
            status="ok" if ok else "miss",
            error_type="",
            context=f"lead_id={rq.lead_id}",
        )

    return complete_count


async def run_enrichment_retry_job() -> None:
    """APScheduler entrypoint for enrichment retries."""
    try:
        n = await process_enrichment_retries()
        logger.info(
            "enrichment_retry_job_complete",
            component="enrichment",
            status="ok",
            error_type="",
            context=f"complete={n}",
        )
    except Exception as exc:
        logger.error(
            "enrichment_retry_job_failed",
            component="enrichment",
            status="failed",
            error_type=type(exc).__name__,
            context=str(exc)[:500],
        )
