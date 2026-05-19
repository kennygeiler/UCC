"""Unit tests for MCA funder account CSV export."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.export import csv_export as ce
from app.main import app
class _Filing:
    def __init__(
        self,
        *,
        secured_party: str,
        lender_class: str | None = "mca_funder",
        is_mca: bool | None = True,
    ) -> None:
        self.secured_party = secured_party
        self.lender_class = lender_class
        self.is_mca = is_mca


class _Account:
    id = 7
    display_name = 'Acme "Widgets" LLC'
    state = "FL"
    debtor_name_normalized = "acme widgets llc"
    consolidation_tier = "priority"
    consolidation_score = 88.5
    mca_funder_count = 2
    material_ucc_count = 3
    days_since_last_filing = 12
    last_event_at = datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_aggregate_mca_funders_and_top_parties() -> None:
    filings = [
        _Filing(secured_party="Beta Capital LLC"),
        _Filing(secured_party="Beta Capital LLC"),
        _Filing(secured_party="Alpha Funding Inc", lender_class="bank", is_mca=False),
        _Filing(secured_party="Gamma MCA LLC"),
    ]
    stats = ce.aggregate_filings_for_export(filings)  # type: ignore[arg-type]
    assert stats["mca_funders"] == "Beta Capital LLC; Gamma MCA LLC"
    assert stats["filing_count"] == 4
    assert stats["top_secured_parties"] == "Alpha Funding Inc; Beta Capital LLC; Gamma MCA LLC"


def test_rows_to_csv_escapes_quotes_and_commas() -> None:
    row = ce.account_to_csv_row(
        _Account(),  # type: ignore[arg-type]
        {"mca_funders": "Funder A", "filing_count": 1, "top_secured_parties": ""},
    )
    row["display_name"] = 'Say "hello", world'
    text = ce.rows_to_csv_text([row])
    lines = text.strip().splitlines()
    assert lines[0] == ",".join(ce.MCA_EXPORT_COLUMNS)
    assert 'Say ""hello"", world' in lines[1]
    assert "phone" in lines[0]
    assert lines[1].endswith(",,,,") or ",,,," in lines[1]


@pytest.mark.asyncio
async def test_export_rows_filters_by_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    async def fake_rows(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(ce, "export_mca_accounts_csv_rows", fake_rows)
    await ce.build_mca_accounts_csv(state="FL", tier="priority")
    assert captured["tier"] == "priority"
    assert captured["state"] == "FL"


@pytest.mark.asyncio
async def test_export_mca_accounts_csv_rows_applies_tier_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    class RData:
        def scalars(self):
            return self

        def all(self):
            return []

    class Sess:
        execute = AsyncMock(return_value=RData())

    @asynccontextmanager
    async def fake_get_session():
        yield Sess()

    monkeypatch.setattr(ce, "get_session", fake_get_session)

    await ce.export_mca_accounts_csv_rows(state="FL", tier="work")
    stmt = Sess.execute.call_args[0][0]
    compiled = str(stmt).lower()
    assert "consolidation_tier" in compiled or "work" in compiled


@pytest.mark.asyncio
async def test_leads_export_csv_route_headers() -> None:
    sample_csv = (
        "account_id,display_name,state\n"
        "1,Test Co,FL\n"
    )
    with patch("app.dashboard.routes.build_mca_accounts_csv", AsyncMock(return_value=sample_csv)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/leads/export.csv?state=FL&tier=priority")

    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "account_id" in response.text
    assert "attachment" in response.headers.get("content-disposition", "")
    assert "ucc-mca-leads-FL" in response.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_leads_browse_shows_export_button() -> None:
    ctx = {
        "leads": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
        "filters": {"state": "FL"},
        "export_csv_url": "/dashboard/leads/export.csv?state=FL",
        "active_tier": "",
        "pagination": {
            "prev_page": None,
            "next_page": None,
            "prev_table": None,
            "next_table": None,
            "showing_from": 0,
            "showing_to": 0,
        },
    }
    from app.dashboard.queries import CONSOLIDATION_TIERS

    ctx["tier_chips"] = CONSOLIDATION_TIERS

    with patch("app.dashboard.routes._leads_context", AsyncMock(return_value=ctx)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/leads?state=FL")

    assert response.status_code == 200
    assert "Export CSV" in response.text
    assert "/dashboard/leads/export.csv" in response.text
