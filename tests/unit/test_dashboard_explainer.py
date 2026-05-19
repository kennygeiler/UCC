"""Dashboard includes peer explainer modal."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_dashboard_home_includes_how_pipeline_works_modal() -> None:
    """Landing dashboard exposes explainer dialog for demos."""
    fake = {
        "total_leads": 0,
        "enriched_leads": 0,
        "cleared_leads": 0,
        "exported_leads": 0,
        "blocked_leads": 0,
        "state_coverage": [],
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
    assert "How this pipeline works" in body
    assert 'id="pipeline-explainer"' in body
    assert "consolidation_score" in body
    assert "reset_fl_data.py" in body
    assert "/dashboard/accounts" in body
