"""Tests for account-level MCA leads queries and routes."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.dashboard import queries as dq
from app.main import app


class AccountRow:
    id = 42
    display_name = "Beta Corp LLC"
    state = "FL"
    mca_funder_count = 2
    consolidation_score = 70.0
    consolidation_tier = "priority"
    days_since_last_filing = 15


@pytest.mark.asyncio
async def test_search_leads_returns_mca_funder_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    class RCount:
        def scalar_one(self):
            return 1

    class RData:
        def scalars(self):
            return self

        def all(self):
            return [AccountRow()]

    class Sess:
        execute = AsyncMock(side_effect=[RCount(), RData()])

    @asynccontextmanager
    async def fake_get_session():
        yield Sess()

    monkeypatch.setattr(dq, "get_session", fake_get_session)

    result = await dq.search_leads(state="FL", limit=10, offset=0)
    lead = result["leads"][0]
    assert lead["debtor_name"] == "Beta Corp LLC"
    assert lead["mca_funder_count"] == 2
    assert lead["consolidation_tier"] == "priority"
    assert lead["detail_url"] == "/dashboard/leads/accounts/42/detail"


@pytest.mark.asyncio
async def test_count_mca_lead_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    class RCount:
        def scalar_one(self):
            return 169

    class Sess:
        execute = AsyncMock(return_value=RCount())

    @asynccontextmanager
    async def fake_get_session():
        yield Sess()

    monkeypatch.setattr(dq, "get_session", fake_get_session)
    assert await dq.count_mca_lead_accounts(state="FL") == 169


@pytest.mark.asyncio
async def test_leads_browse_renders_mca_account_columns() -> None:
    fake = {
        "leads": [
            {
                "id": 42,
                "debtor_name": "Beta Corp LLC",
                "state": "FL",
                "mca_funder_count": 2,
                "consolidation_score": 70.0,
                "consolidation_tier": "priority",
                "days_since_last_filing": 15,
                "account_url": "/dashboard/accounts/42",
                "detail_url": "/dashboard/leads/accounts/42/detail",
                "filings_url": "/dashboard/filings?state=FL",
            }
        ],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }
    ctx = {
        **fake,
        "filters": {"state": "FL"},
        "tier_chips": dq.CONSOLIDATION_TIERS,
        "active_tier": "",
        "pagination": {
            "prev_page": None,
            "next_page": None,
            "prev_table": None,
            "next_table": None,
            "showing_from": 1,
            "showing_to": 1,
        },
    }

    with patch("app.dashboard.routes._leads_context", AsyncMock(return_value=ctx)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/leads?state=FL")

    assert response.status_code == 200
    body = response.text
    assert "MCA Leads" in body
    assert "Beta Corp LLC" in body
    assert "MCA funders" in body


@pytest.mark.asyncio
async def test_mca_lead_detail_partial() -> None:
    fake = {
        "id": 42,
        "debtor_name": "Beta Corp LLC",
        "state": "FL",
        "mca_funder_count": 1,
        "consolidation_score": 50.0,
        "consolidation_tier": "work",
        "days_since_last_filing": 10,
        "account_url": "/dashboard/accounts/42",
        "detail_url": "/dashboard/leads/accounts/42/detail",
        "filings_url": "/dashboard/filings?state=FL",
        "mca_funders": [
            {
                "secured_party": "Test Funder Capital LLC",
                "lender_class": "mca_funder",
                "is_mca": True,
                "filing_number": "FL-1",
                "filing_date": "2025-01-01",
            }
        ],
    }

    with patch("app.dashboard.routes.get_mca_lead_detail", AsyncMock(return_value=fake)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/leads/accounts/42/detail")

    assert response.status_code == 200
    assert "Test Funder Capital LLC" in response.text
    assert "MCA funders on filings" in response.text
