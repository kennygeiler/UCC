"""E2E: reset FL data → quick scrape → verify no duplicate filings."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import func, select, text

from app.db import get_engine, get_session
from app.models.account import BusinessAccount
from app.models.filing import UCCFiling
from app.operations.fl_reset import reset_fl_data
from app.scrapers.states.florida import FloridaScraper

pytestmark = pytest.mark.integration


def _make_response(*, status_code: int = 200, body: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    payload = body or "{}"
    resp.content = payload.encode("utf-8")
    resp.text = payload
    resp.raise_for_status = MagicMock()
    return resp


def _search_payload(rows: list[tuple[str, str]], next_row: int | None) -> str:
    return json.dumps(
        {
            "status": "OK",
            "payload": {
                "debtors": [
                    {"name": name, "uccNumber": ucc, "rowNumber": i + 1}
                    for i, (name, ucc) in enumerate(rows)
                ],
                "nextRowNumber": next_row,
            },
        }
    )


@pytest.fixture
async def require_postgres():
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError as exc:
        pytest.skip(f"Postgres not reachable: {exc}")
    except Exception as exc:
        pytest.skip(f"Postgres unavailable: {exc}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("require_postgres")
async def test_reset_quick_scrape_no_duplicate_filings() -> None:
    """Reset → mocked quick scrape → accounts exist, unique (state, filing_number)."""
    await reset_fl_data(dry_run=False)

    page1 = _search_payload(
        [("ACME LLC", "FL-E2E-001"), ("BETA INC", "FL-E2E-002")],
        next_row=20,
    )
    page2 = _search_payload([("GAMMA LLC", "FL-E2E-003")], next_row=None)

    async def fake_get(url: str, **kwargs):
        params = kwargs.get("params") or {}
        row = int(params.get("rowNumber", "0"))
        if "/Filings/" in url:
            return _make_response(
                body=json.dumps(
                    {
                        "payload": {
                            "secNames": [{"name": "Yellowstone Capital LLC"}],
                            "date": "2026-01-15T00:00:00Z",
                        }
                    }
                )
            )
        if row == 0:
            return _make_response(body=page1)
        return _make_response(body=page2)

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    scraper = FloridaScraper(
        max_pages=2,
        page_cap_per_run=2,
        index_profiles=[("OrganizationDebtorName", "FiledCompactDebtorNameList")],
        fetch_filing_date=False,
        enrich_concurrency=1,
    )

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch(
            "app.consolidation.pipeline.run_mca_pipeline",
            AsyncMock(return_value=0),
        ):
            inserted = await scraper.scrape()

    assert inserted >= 1

    async with get_session() as session:
        filing_count = (
            await session.execute(
                select(func.count()).select_from(UCCFiling).where(UCCFiling.state == "FL")
            )
        ).scalar_one()
        dupes = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM (
                        SELECT state, filing_number
                        FROM ucc_filings WHERE state = 'FL'
                        GROUP BY state, filing_number HAVING COUNT(*) > 1
                    ) d
                    """
                )
            )
        ).scalar_one()
        account_count = (
            await session.execute(
                select(func.count())
                .select_from(BusinessAccount)
                .where(BusinessAccount.state == "FL")
            )
        ).scalar_one()

    assert filing_count >= 2
    assert dupes == 0
    assert account_count >= 1

    await reset_fl_data(dry_run=False)
