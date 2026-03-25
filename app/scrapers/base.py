"""Abstract base scraper with ScraperRun lifecycle management."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.filing import UCCFiling
from app.models.operations import ScraperRun
from app.scrapers.rate_limiter import RateLimiter
from app.scrapers.user_agents import get_random_user_agent

logger = get_logger("scraper")


class BaseScraper(ABC):
    """Abstract base class for all state UCC scrapers.

    Subclasses must implement state_code, tier, base_url, column_map,
    parse_response, and build_search_url.
    """

    def __init__(self, rate_limiter: RateLimiter | None = None) -> None:
        """Initialize with an optional shared rate limiter.

        Args:
            rate_limiter: Shared RateLimiter instance; creates one if None.
        """
        self.rate_limiter = rate_limiter or RateLimiter()

    @property
    @abstractmethod
    def state_code(self) -> str:
        """Two-letter state code (e.g. 'CA')."""

    @property
    @abstractmethod
    def tier(self) -> int:
        """Priority tier for this state (1, 2, or 3)."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for the state SOS UCC search portal."""

    @property
    @abstractmethod
    def column_map(self) -> dict[str, int]:
        """Maps UCCFiling field names to HTML table column indices."""

    @abstractmethod
    def build_search_url(self) -> str:
        """Build the full search URL for fetching recent filings."""

    @abstractmethod
    def parse_response(self, html: str) -> list[dict]:
        """Parse HTML response into filing dicts matching UCCFiling columns."""

    async def scrape(self) -> int:
        """Execute a full scrape cycle: fetch, parse, deduplicate, persist.

        Returns:
            Number of new records inserted.
        """
        run = await self._start_run()
        try:
            html = await self._fetch()
            filings = self.parse_response(html)
            count = await self._persist(filings)
            await self._finish_run(run, count)
            return count
        except Exception as exc:
            await self._fail_run(run, exc)
            raise

    async def _fetch(self) -> str:
        """Fetch HTML from the state portal with rate limiting and UA rotation."""
        await self.rate_limiter.wait(self.state_code)
        url = self.build_search_url()
        headers = {"User-Agent": get_random_user_agent()}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        self.rate_limiter.record_success(self.state_code)
        logger.info("fetch_complete", state=self.state_code, url=url)
        return response.text

    async def _persist(self, filings: list[dict]) -> int:
        """Deduplicate and insert new filings into the database.

        Args:
            filings: List of filing dicts to persist.

        Returns:
            Number of new records inserted.
        """
        inserted = 0
        async with get_session() as session:
            for filing_data in filings:
                exists = await self._filing_exists(
                    session, filing_data["filing_number"]
                )
                if not exists:
                    session.add(UCCFiling(**filing_data))
                    inserted += 1
        logger.info("persist_complete", state=self.state_code, inserted=inserted)
        return inserted

    async def _filing_exists(self, session, filing_number: str) -> bool:
        """Check if a filing already exists for this state.

        Args:
            session: Active database session.
            filing_number: Filing number to check.

        Returns:
            True if a matching record exists.
        """
        stmt = select(UCCFiling.id).where(
            UCCFiling.filing_number == filing_number,
            UCCFiling.state == self.state_code,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _start_run(self) -> ScraperRun:
        """Create a ScraperRun record at the start of a scrape."""
        async with get_session() as session:
            run = ScraperRun(
                state=self.state_code,
                started_at=datetime.now(timezone.utc),
                status="running",
            )
            session.add(run)
            await session.flush()
            run_id = run.id
        logger.info("scrape_started", state=self.state_code, run_id=run_id)
        return run

    async def _finish_run(self, run: ScraperRun, count: int) -> None:
        """Mark a ScraperRun as completed.

        Args:
            run: The ScraperRun to update.
            count: Number of records found.
        """
        async with get_session() as session:
            run.finished_at = datetime.now(timezone.utc)
            run.records_found = count
            run.status = "completed"
            session.add(run)
        logger.info("scrape_completed", state=self.state_code, records=count)

    async def _fail_run(self, run: ScraperRun, exc: Exception) -> None:
        """Mark a ScraperRun as failed.

        Args:
            run: The ScraperRun to update.
            exc: The exception that caused the failure.
        """
        self.rate_limiter.record_error(self.state_code)
        async with get_session() as session:
            run.finished_at = datetime.now(timezone.utc)
            run.status = "failed"
            run.error_detail = str(exc)[:500]
            session.add(run)
        logger.error("scrape_failed", state=self.state_code, error=str(exc))
