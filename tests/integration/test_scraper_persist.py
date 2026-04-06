"""Integration: BaseScraper scrape cycle writes filings and scraper_runs (SCRAPE-02)."""

import uuid

import pytest
from sqlalchemy import delete, select, text

from app.db import get_engine, get_session
from app.models.filing import UCCFiling
from app.models.operations import ScraperRun
from app.scrapers.base import BaseScraper
from app.scrapers.rate_limiter import RateLimiter

pytestmark = pytest.mark.integration


@pytest.fixture
async def require_postgres():
    """Skip tests when no migrated Postgres is available (local dev / CI only)."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


_SAMPLE_HTML = """<table>
<tr><th>Filing</th><th>Date</th><th>Debtor</th><th>Secured</th><th>Collateral</th></tr>
<tr><td>{fn}</td><td>03/15/2024</td><td>Test Debtor LLC</td><td>Test Bank</td><td>All assets</td></tr>
</table>"""


class _PersistTestScraper(BaseScraper):
    """Deterministic scraper for DB integration — no live HTTP."""

    def __init__(self, filing_number: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._filing_number = filing_number

    @property
    def state_code(self) -> str:
        return "ZZ"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return "https://example.test/ucc"

    @property
    def column_map(self) -> dict[str, int]:
        return {"filing_number": 0, "debtor_name": 2, "secured_party": 3}

    def build_search_url(self) -> str:
        return "https://example.test/search"

    def parse_response(self, html: str) -> list[dict]:
        fn = self._filing_number
        return [
            {
                "filing_number": fn,
                "state": self.state_code,
                "debtor_name": "Test Debtor LLC",
                "secured_party": "Test Bank",
                "filing_date": None,
                "collateral_description": "Equipment",
            }
        ]

    async def _fetch(self) -> str:
        return _SAMPLE_HTML.format(fn=self._filing_number)


class _FailingScraper(_PersistTestScraper):
    """Forces a failure after the run row is created."""

    def parse_response(self, html: str) -> list[dict]:
        raise RuntimeError("forced failure for integration test")


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_scrape_inserts_filing_and_completed_run():
    """Happy path: ucc_filings + scraper_runs completed."""
    fn = f"ZZ-INT-{uuid.uuid4().hex[:12]}"
    scraper = _PersistTestScraper(fn, rate_limiter=RateLimiter(base_delay=0.0, jitter_pct=0.0))
    count = await scraper.scrape()
    assert count == 1

    async with get_session() as session:
        r = await session.execute(
            select(ScraperRun).where(ScraperRun.state == "ZZ").order_by(ScraperRun.id.desc())
        )
        run = r.scalars().first()
        assert run is not None
        assert run.status == "completed"
        assert run.records_found == 1

        f = await session.execute(select(UCCFiling).where(UCCFiling.filing_number == fn))
        filing = f.scalars().first()
        assert filing is not None
        assert filing.debtor_name == "Test Debtor LLC"

    async with get_session() as session:
        await session.execute(delete(UCCFiling).where(UCCFiling.filing_number == fn))
        await session.execute(delete(ScraperRun).where(ScraperRun.state == "ZZ"))


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_scrape_failure_records_failed_run():
    """Failure path: scraper_runs status failed with bounded error_detail."""
    scraper = _FailingScraper(
        f"ZZ-FAIL-{uuid.uuid4().hex[:8]}",
        rate_limiter=RateLimiter(base_delay=0.0, jitter_pct=0.0),
    )
    with pytest.raises(RuntimeError, match="forced failure"):
        await scraper.scrape()

    async with get_session() as session:
        r = await session.execute(
            select(ScraperRun).where(ScraperRun.state == "ZZ").order_by(ScraperRun.id.desc())
        )
        run = r.scalars().first()
        assert run is not None
        assert run.status == "failed"
        assert run.error_detail is not None
        assert len(run.error_detail) <= 500

    async with get_session() as session:
        await session.execute(delete(ScraperRun).where(ScraperRun.state == "ZZ"))
