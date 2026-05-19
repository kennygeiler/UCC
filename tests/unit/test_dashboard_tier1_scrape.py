"""Dashboard Tier 1 scrape routes."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_run_not_ready_state_returns_400() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/dashboard/scrapers/GA/run")
    assert response.status_code == 400
    assert "not implemented" in response.text.lower() or "not_ready" in response.text.lower()


@pytest.mark.asyncio
async def test_run_ca_returns_started() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/dashboard/scrapers/CA/run")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "started"
    assert body.get("state") == "CA"
