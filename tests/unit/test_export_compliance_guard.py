"""Export adapters must refuse non-cleared leads (COMPLY-05)."""

import pytest

from app.compliance.exceptions import ComplianceNotClearedError
from app.export.csv_fallback import CSVFallbackAdapter
from app.export.ghl_adapter import GHLAdapter


@pytest.mark.asyncio
async def test_ghl_upsert_raises_when_not_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    """GHL upsert does not run when compliance_status is not cleared."""
    monkeypatch.setenv("GHL_API_KEY", "k")
    monkeypatch.setenv("GHL_LOCATION_ID", "loc")
    from app.db import _get_settings

    _get_settings.cache_clear()
    adapter = GHLAdapter()
    lead_data = {
        "phone": "1",
        "email": "a@b.c",
        "debtor_name": "Co",
        "owner_name": "A B",
        "compliance_status": "blocked:internal_dnc",
    }
    with pytest.raises(ComplianceNotClearedError):
        await adapter.upsert_lead(lead_data)


@pytest.mark.asyncio
async def test_csv_upsert_raises_when_not_cleared(tmp_path) -> None:
    """CSV export does not write when compliance_status is not cleared."""
    adapter = CSVFallbackAdapter(output_dir=str(tmp_path))
    lead_data = {
        "phone": "1",
        "compliance_status": "pending",
    }
    with pytest.raises(ComplianceNotClearedError):
        await adapter.upsert_lead(lead_data)


@pytest.mark.asyncio
async def test_ghl_upsert_accepts_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cleared lead passes guard; HTTP is mocked."""
    monkeypatch.setenv("GHL_API_KEY", "k")
    monkeypatch.setenv("GHL_LOCATION_ID", "loc")
    from app.db import _get_settings

    _get_settings.cache_clear()

    import httpx

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"contact": {"id": "c1"}}

    async def fake_post(self, *_a, **_k):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    adapter = GHLAdapter()
    lead_data = {
        "phone": "1",
        "email": "a@b.c",
        "debtor_name": "Co",
        "owner_name": "A B",
        "compliance_status": "cleared",
    }
    cid = await adapter.upsert_lead(lead_data)
    assert cid == "c1"
