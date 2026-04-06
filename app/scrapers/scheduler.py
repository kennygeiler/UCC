"""APScheduler job definitions for cadenced UCC scraping.

Tier 1: daily, Tier 2: every 36 hours, Tier 3: every 48 hours.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import Settings
from app.logging import get_logger
from app.scrapers.rate_limiter import RateLimiter
from app.scrapers.registry import SCRAPER_REGISTRY, schedulable_state_codes

logger = get_logger("scheduler")


async def run_scraper(state_code: str, rate_limiter: RateLimiter) -> None:
    """Execute a single state scraper run.

    Args:
        state_code: Two-letter state code to scrape.
        rate_limiter: Shared rate limiter instance.
    """
    entry = SCRAPER_REGISTRY.get(state_code)
    if not entry:
        logger.warning("unknown_state", state=state_code)
        return
    scraper = entry["class"](rate_limiter=rate_limiter)
    try:
        count = await scraper.scrape()
        logger.info("scheduled_scrape_done", state=state_code, records=count)
    except Exception as exc:
        logger.error("scheduled_scrape_failed", state=state_code, error=str(exc))


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler with tiered scrape jobs.

    Returns:
        Configured AsyncIOScheduler (not yet started).
    """
    scheduler = AsyncIOScheduler()
    rate_limiter = RateLimiter()

    tier_intervals = {1: 24, 2: 36, 3: 48}

    for state_code in schedulable_state_codes():
        info = SCRAPER_REGISTRY[state_code]
        hours = tier_intervals.get(info["tier"], 48)
        scheduler.add_job(
            run_scraper,
            trigger=IntervalTrigger(hours=hours),
            args=[state_code, rate_limiter],
            id=f"scrape_{state_code}",
            name=f"Scrape {state_code} (Tier {info['tier']})",
            replace_existing=True,
        )

    settings = Settings()
    if settings.MCA_ALIAS_UPDATE_ENABLED:
        from app.mca.alias_updater import run_alias_update_job

        scheduler.add_job(
            run_alias_update_job,
            trigger=IntervalTrigger(hours=settings.MCA_ALIAS_UPDATE_INTERVAL_HOURS),
            id="mca_alias_update",
            name="MCA alias auto-update",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    n_scrape = len(schedulable_state_codes())
    n_total = n_scrape + (1 if settings.MCA_ALIAS_UPDATE_ENABLED else 0)
    logger.info(
        "scheduler_configured",
        scrape_jobs=n_scrape,
        total_jobs=n_total,
        mca_alias_job=settings.MCA_ALIAS_UPDATE_ENABLED,
        tier4_excluded=True,
    )
    return scheduler
