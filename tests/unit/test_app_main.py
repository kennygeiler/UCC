"""Tests for the pipeline service entry point."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    """Health returns 200 with status and database fields when DB is up."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=None)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_engine = MagicMock()
    mock_engine.connect = MagicMock(return_value=mock_ctx)

    with patch("app.main.get_engine", return_value=mock_engine):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
