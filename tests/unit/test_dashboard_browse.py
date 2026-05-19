"""Tests for dashboard filings and leads browse pages."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dashboard import queries as dq
from app.main import app


@pytest.mark.asyncio
async def test_dashboard_home_links_to_browse_pages() -> None:
    fake = {
        "total_leads": 0,
        "enriched_leads": 0,
        "cleared_leads": 0,
        "exported_leads": 0,
        "blocked_leads": 0,
        "state_coverage": [],
        "recent_scraper_runs": [],
    }

    with patch("app.dashboard.routes.get_dashboard_stats", AsyncMock(return_value=fake)):
        with patch(
            "app.dashboard.routes.get_recent_scraper_runs",
            AsyncMock(return_value=[]),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/dashboard/")

    assert response.status_code == 200
    body = response.text
    assert 'href="/dashboard/filings"' in body
    assert 'href="/dashboard/leads"' in body


@pytest.mark.asyncio
async def test_filings_browse_renders_table() -> None:
    fake = {
        "filings": [
            {
                "id": 1,
                "filing_number": "FL-001",
                "state": "FL",
                "debtor_name": "Acme LLC",
                "secured_party": "Lender Inc",
                "filing_date": "2025-01-01",
                "scraped_at": "2025-01-02",
                "is_mca": True,
                "lead_id": 9,
                "lead_tier": "warm",
                "lead_url": "/dashboard/leads?state=FL",
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }

    with patch("app.dashboard.routes.search_filings", AsyncMock(return_value=fake)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/filings?state=FL")

    assert response.status_code == 200
    body = response.text
    assert "UCC Filings" in body
    assert "Acme LLC" in body
    assert "Lead #9" in body


@pytest.mark.asyncio
async def test_search_filings_applies_ilike_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    class Row:
        id = 1
        filing_number = "X"
        state = "FL"
        debtor_name = "Test Co"
        secured_party = "Bank"
        filing_date = None
        scraped_at = None
        is_mca = None

    class RCount:
        def scalar_one(self):
            return 1

    class RData:
        def all(self):
            return [(Row(), None)]

    class Sess:
        execute = AsyncMock(side_effect=[RCount(), RData()])

    @asynccontextmanager
    async def fake_get_session():
        yield Sess()

    monkeypatch.setattr(dq, "get_session", fake_get_session)

    result = await dq.search_filings(
        state="fl",
        debtor_name="test",
        secured_party="bank",
        limit=10,
        offset=0,
    )

    assert result["total"] == 1
    assert result["filings"][0]["state"] == "FL"
    assert Sess.execute.await_count == 2
