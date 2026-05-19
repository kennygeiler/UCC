"""Unit tests for consolidation classifier, scorer, rollup helpers."""

from datetime import datetime, timedelta, timezone

import pytest

from app.consolidation.classifier import (
    classify_secured_party,
    classify_secured_party_name,
)
from app.consolidation.scorer import assign_consolidation_tier, score_account_from_filings
from app.scrapers.states.florida import FloridaScraper, parse_index_profiles


def test_classify_mca_and_bank():
    assert classify_secured_party_name("OnDeck Capital LLC") == "mca_funder"
    assert classify_secured_party_name("JPMorgan Chase Bank NA") == "bank"
    assert classify_secured_party_name("CT Corporation System") == "registered_agent"


def test_classify_secured_party_prefers_mca():
    sp = "CT Corporation System; Yellowstone Capital LLC"
    assert classify_secured_party(sp) == "mca_funder"


def test_score_account_priority_tier():
    now = datetime.now(timezone.utc)
    filings = [
        {
            "lender_class": "mca_funder",
            "filing_date": now - timedelta(days=10),
            "collateral_description": "all assets",
            "is_mca": True,
            "secured_party": "OnDeck",
            "mca_match_type": "exact",
            "mca_match_confidence": 0.95,
        },
        {
            "lender_class": "mca_funder",
            "filing_date": now - timedelta(days=20),
            "collateral_description": None,
            "is_mca": True,
            "secured_party": "Pearl Capital",
            "mca_match_type": "exact",
            "mca_match_confidence": 0.95,
        },
        {
            "lender_class": "mca_funder",
            "filing_date": now - timedelta(days=5),
            "collateral_description": None,
            "is_mca": True,
            "secured_party": "Kapitus",
            "mca_match_type": "exact",
            "mca_match_confidence": 0.95,
        },
    ]
    result = score_account_from_filings(filings, now=now)
    assert result["consolidation_score"] >= 70
    assert result["consolidation_tier"] == assign_consolidation_tier(result["consolidation_score"])
    assert result["mca_funder_count"] >= 3
    assert "mca_stack" in result["score_components"]


def test_score_single_recent_mca_gets_work_tier():
    """One MCA funder with filing within 60 days should reach at least work tier."""
    now = datetime.now(timezone.utc)
    filings = [
        {
            "lender_class": "mca_funder",
            "filing_date": now - timedelta(days=15),
            "collateral_description": None,
            "is_mca": True,
            "secured_party": "OnDeck Capital LLC",
            "mca_match_type": "exact",
            "mca_match_confidence": 0.95,
        },
    ]
    result = score_account_from_filings(filings, now=now)
    assert result["consolidation_tier"] in ("work", "priority")
    assert result["consolidation_score"] >= 50


def test_score_dual_mca_priority_tier():
    """Two MCA funders should bump to priority even with moderate penalties."""
    now = datetime.now(timezone.utc)
    filings = [
        {
            "lender_class": "mca_funder",
            "filing_date": now - timedelta(days=120),
            "collateral_description": None,
            "is_mca": True,
            "secured_party": "OnDeck",
            "mca_match_type": "exact",
            "mca_match_confidence": 0.95,
        },
        {
            "lender_class": "mca_funder",
            "filing_date": now - timedelta(days=130),
            "collateral_description": None,
            "is_mca": True,
            "secured_party": "Pearl Capital",
            "mca_match_type": "exact",
            "mca_match_confidence": 0.95,
        },
        {
            "lender_class": "government",
            "filing_date": now - timedelta(days=5),
            "collateral_description": None,
            "is_mca": False,
            "secured_party": "SBA",
            "mca_match_type": None,
            "mca_match_confidence": None,
        },
    ]
    result = score_account_from_filings(filings, now=now)
    assert result["consolidation_tier"] == "priority"
    assert result["mca_funder_count"] >= 2


def test_parse_index_profiles():
    raw = "OrganizationDebtorName|FiledCompactDebtorNameList,IndividualDebtorName:FiledCompactDebtorNameList"
    profiles = parse_index_profiles(raw)
    assert len(profiles) == 2
    assert profiles[0] == ("OrganizationDebtorName", "FiledCompactDebtorNameList")


@pytest.mark.asyncio
async def test_fetch_filings_multi_index_dedupes(monkeypatch):
    """Three index profiles each return same ucc — only one filing kept."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from app.scrapers.rate_limiter import RateLimiter
    scraper = FloridaScraper(
        rate_limiter=RateLimiter(base_delay=0.0, jitter_pct=0.0),
        index_profiles=[
            ("OrganizationDebtorName", "FiledCompactDebtorNameList"),
            ("OrganizationDebtorName", "FiledActualDebtorNameList"),
        ],
        page_cap_per_run=1,
        max_pages=1,
    )

    body = _search_payload([("ACME LLC", "900")], next_row=None)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=MagicMock(
        status_code=200,
        content=body.encode(),
        raise_for_status=MagicMock(),
    ))

    async def noop_checkpoint(*_a, **_k):
        return 0

    async def noop_save(*_a, **_k):
        pass

    with patch("app.scrapers.states.florida.httpx.AsyncClient", return_value=mock_client), \
         patch("app.scrapers.states.florida.get_checkpoint", noop_checkpoint), \
         patch("app.scrapers.states.florida.save_checkpoint", noop_save):
        filings = await scraper._fetch_filings()

    assert len(filings) == 1
    assert filings[0]["filing_number"] == "900"


def _search_payload(rows, next_row):
    import json
    return json.dumps({
        "status": "OK",
        "payload": {
            "debtors": [
                {"name": n, "uccNumber": u} for n, u in rows
            ],
            "nextRowNumber": next_row,
        },
    })
