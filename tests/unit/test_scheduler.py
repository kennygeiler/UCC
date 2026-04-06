"""Unit tests for APScheduler scrape job registration."""

import pytest
from apscheduler.triggers.interval import IntervalTrigger

from app.scrapers.registry import SCRAPER_REGISTRY, schedulable_state_codes
from app.scrapers.scheduler import create_scheduler, run_scraper


def test_create_scheduler_job_count_matches_schedulable_states():
    """One interval job per tier 1–3 state; Tier 4 registry stubs are excluded."""
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    expected = len(schedulable_state_codes())
    assert len(jobs) == expected
    for code in schedulable_state_codes():
        assert any(j.id == f"scrape_{code}" for j in jobs)
    for j in jobs:
        assert isinstance(j.trigger, IntervalTrigger)


def test_tier4_states_have_no_scheduler_jobs():
    """DC and NYC appear in the registry but not as APScheduler job ids."""
    scheduler = create_scheduler()
    job_ids = {j.id for j in scheduler.get_jobs()}
    tier4 = [c for c, i in SCRAPER_REGISTRY.items() if i["tier"] == 4]
    assert tier4
    for code in tier4:
        assert f"scrape_{code}" not in job_ids


@pytest.mark.asyncio
async def test_run_scraper_handles_unknown_state():
    """run_scraper returns quietly when state code is missing."""
    from app.scrapers.rate_limiter import RateLimiter

    await run_scraper("XX", RateLimiter())
