"""California scraper post-scrape pipeline (mocked, no Playwright)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scrapers.states.california import CaliforniaScraper


@pytest.mark.asyncio
async def test_ca_scrape_runs_post_pipeline():
    sample_filings = [
        {
            "filing_number": "CA-TEST-001",
            "state": "CA",
            "debtor_name": "ACME LLC",
            "secured_party": "WELLS FARGO",
            "filing_date": None,
            "collateral_description": None,
        }
    ]

    scraper = CaliforniaScraper(run_consolidation=True)
    run = AsyncMock()
    run.id = 1

    with patch.object(
        scraper,
        "_persist",
        AsyncMock(return_value=1),
    ):
        with patch.object(
            scraper,
            "_finish_run",
            AsyncMock(),
        ):
            with patch(
                "app.scrapers.base_enriched.run_post_scrape_pipeline",
                AsyncMock(return_value={"state": "CA", "filings_classified": 1}),
            ) as mock_pipeline:
                count = await scraper._finish_scrape_run(run, sample_filings)

    assert count == 1
    mock_pipeline.assert_awaited_once_with(state="CA")
