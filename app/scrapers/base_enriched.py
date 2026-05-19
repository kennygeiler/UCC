"""Shared scrape helpers: upsert persist and post-scrape consolidation."""

from __future__ import annotations

from sqlalchemy import select

from app.consolidation.pipeline import run_post_scrape_pipeline
from app.db import get_session
from app.logging import get_logger
from app.models.filing import UCCFiling
from app.scrapers.base import BaseScraper
from app.scrapers.playwright_base import PlaywrightBaseScraper

logger = get_logger("scraper")


class UpsertPersistMixin:
    """Upsert filings: insert new rows; enrich null secured_party / dates on existing."""

    async def _persist(self, filings: list[dict]) -> int:  # type: ignore[override]
        inserted = 0
        updated = 0
        async with get_session() as session:
            for filing_data in filings:
                stmt = select(UCCFiling).where(
                    UCCFiling.filing_number == filing_data["filing_number"],
                    UCCFiling.state == self.state_code,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing is None:
                    session.add(UCCFiling(**filing_data))
                    inserted += 1
                    continue
                row_updated = False
                if existing.secured_party is None and filing_data.get("secured_party"):
                    existing.secured_party = filing_data["secured_party"]
                    row_updated = True
                if existing.filing_date is None and filing_data.get("filing_date"):
                    existing.filing_date = filing_data["filing_date"]
                    row_updated = True
                if (
                    existing.collateral_description is None
                    and filing_data.get("collateral_description")
                ):
                    existing.collateral_description = filing_data["collateral_description"]
                    row_updated = True
                if row_updated:
                    updated += 1
        logger.info(
            "persist_complete",
            state=self.state_code,
            inserted=inserted,
            updated=updated,
        )
        return inserted


class PostScrapePipelineMixin:
    """Run classify → rollup → rescore → MCA pipeline after a successful scrape."""

    run_consolidation: bool = True

    async def _run_post_scrape_pipeline(self) -> dict | None:
        if not self.run_consolidation:
            return None
        return await run_post_scrape_pipeline(state=self.state_code)


class EnrichedScraperMixin(PostScrapePipelineMixin, UpsertPersistMixin):
    """Upsert persist + post-scrape pipeline helpers."""

    async def _finish_scrape_run(self, run, filings: list[dict]) -> int:
        """Persist filings, finish run, optional post-scrape pipeline."""
        count = await self._persist(filings)
        await self._finish_run(run, count)
        await self._run_post_scrape_pipeline()
        return count


class PlaywrightPostScrapeScraper(EnrichedScraperMixin, PlaywrightBaseScraper):
    """Playwright base scrapers with upsert + post-scrape pipeline."""


class PostScrapeScraper(EnrichedScraperMixin, BaseScraper):
    """HTTP/custom scrapers with upsert + post-scrape pipeline."""
