"""Tests for dashboard aggregation queries."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.dashboard import queries as dq


@pytest.mark.asyncio
async def test_get_state_filing_lead_stats_unions_states(monkeypatch: pytest.MonkeyPatch) -> None:
    """States from filings, leads, and scraper runs all appear with correct counts."""

    class R1:
        def all(self):
            return [("CA", 100), ("NY", 5)]

    class R2:
        def all(self):
            return [("CA", 2)]

    class R3:
        def all(self):
            return [("TX",)]

    exec_mock = AsyncMock(side_effect=[R1(), R2(), R3()])

    class Sess:
        execute = exec_mock

    @asynccontextmanager
    async def fake_get_session():
        yield Sess()

    monkeypatch.setattr(dq, "get_session", fake_get_session)
    monkeypatch.setattr(
        "app.scrapers.registry.get_tier1_state_codes",
        lambda: [],
    )

    rows = await dq.get_state_filing_lead_stats()
    by_state = {r["state"]: r for r in rows}

    assert set(by_state) == {"CA", "NY", "TX"}
    assert by_state["CA"]["filings"] == 100 and by_state["CA"]["leads"] == 2
    assert by_state["CA"]["scraper_run"] is False
    assert by_state["NY"]["filings"] == 5 and by_state["NY"]["leads"] == 0
    assert by_state["NY"]["scraper_run"] is False
    assert by_state["TX"]["filings"] == 0 and by_state["TX"]["leads"] == 0
    assert by_state["TX"]["scraper_run"] is True
