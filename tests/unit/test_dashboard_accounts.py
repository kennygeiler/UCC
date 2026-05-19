"""Dashboard routes for FL accounts and scrape trigger."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_dashboard_accounts_and_fl_run_routes() -> None:
    fake_stats = {
        "total_leads": 0,
        "enriched_leads": 0,
        "cleared_leads": 0,
        "exported_leads": 0,
        "blocked_leads": 0,
        "state_coverage": [],
        "recent_scraper_runs": [],
    }
    fake_accounts = {
        "accounts": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
        "since_last_run": False,
        "last_fl_run_at": None,
    }

    with patch("app.dashboard.routes.get_dashboard_stats", AsyncMock(return_value=fake_stats)), \
         patch("app.dashboard.routes.get_recent_scraper_runs", AsyncMock(return_value=[])), \
         patch("app.dashboard.routes.search_accounts", AsyncMock(return_value=fake_accounts)), \
         patch("app.dashboard.routes._run_fl_scrape_job", AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            home = await client.get("/dashboard/")
            assert home.status_code == 200
            assert "Run FL scrape" in home.text

            accounts = await client.get("/dashboard/accounts")
            assert accounts.status_code == 200

            run = await client.post("/dashboard/scrapers/FL/run")
            assert run.status_code == 200

            status = await client.get("/dashboard/scrapers/FL/status")
            assert status.status_code == 200
            assert "running" in status.json()
