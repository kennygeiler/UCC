"""Tests for MCA lender alias CRUD routes."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_mca_lenders_page_loads() -> None:
    fake = {
        "aliases": [
            {
                "id": 1,
                "alias_name": "Yellowstone Capital",
                "canonical_lender_name": "Yellowstone Capital",
                "lender_class": "mca_funder",
                "consolidation_weight": None,
                "confidence": 1.0,
                "source": "seed",
            }
        ],
        "total": 1,
        "limit": 100,
        "offset": 0,
        "filters": {},
        "pagination": {
            "prev_table": None,
            "next_table": None,
            "showing_from": 1,
            "showing_to": 1,
        },
        "reclassify": {"running": False, "last_result": None, "last_error": None},
    }

    with patch(
        "app.dashboard.mca_lenders._aliases_context",
        AsyncMock(return_value=fake),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/mca-lenders")

    assert response.status_code == 200
    assert "MCA Lenders" in response.text
    assert "Yellowstone Capital" in response.text
    assert "Reclassify FL filings" in response.text


@pytest.mark.asyncio
async def test_mca_lender_create_calls_upsert() -> None:
    with patch("app.dashboard.mca_lenders.upsert_mca_alias", AsyncMock()) as upsert:
        with patch(
            "app.dashboard.mca_lenders._aliases_context",
            AsyncMock(return_value={"aliases": [], "total": 0, "limit": 100, "offset": 0, "filters": {}, "pagination": {}, "reclassify": {}},
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/dashboard/mca-lenders",
                    data={
                        "alias_name": "New Test Funder LLC",
                        "canonical_lender_name": "New Test Funder",
                        "lender_class": "mca_funder",
                    },
                )

    assert response.status_code == 200
    upsert.assert_awaited_once()
