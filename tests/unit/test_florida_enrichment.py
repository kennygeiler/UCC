"""Tests for FloridaScraper enrichment, pagination, and JSON robustness.

These complement the existing ``test_state_scrapers.py`` tests and focus on
the Florida-specific scrape() override added for MCA lead identification:

* ``_fetch_secured_party`` with present / empty / 404 / control-char responses
* Paged scrape that walks until ``nextRowNumber`` is None
* ``_enrich_filings`` populates ``secured_party`` on returned filings
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.scrapers.rate_limiter import RateLimiter
from app.scrapers.states.florida import FloridaScraper, _safe_json_loads


# ── helpers ─────────────────────────────────────────────────────────────


def _make_response(
    *,
    status_code: int = 200,
    body: str | bytes | None = None,
) -> MagicMock:
    """Build a minimal mock ``httpx.Response``."""
    resp = MagicMock()
    resp.status_code = status_code
    if isinstance(body, str):
        resp.content = body.encode("utf-8")
        resp.text = body
    elif isinstance(body, bytes):
        resp.content = body
        resp.text = body.decode("utf-8", errors="replace")
    else:
        resp.content = b""
        resp.text = ""
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "bad", request=MagicMock(), response=resp
        )
    return resp


def _detail_payload(*sec_names: str) -> str:
    """Build a JSON ``deb-sec-names`` response shaped like the real API."""
    return json.dumps(
        {
            "status": "OK",
            "notOk": False,
            "messages": [],
            "payload": {
                "ucc1Number": "202600000000",
                "debNames": [{"name": "EXAMPLE LLC"}],
                "secNames": [{"name": n} for n in sec_names],
            },
        }
    )


def _search_payload(rows: list[tuple[str, str]], next_row: int | None) -> str:
    """Build a JSON ``/search`` response with the given (name, uccNumber) rows."""
    return json.dumps(
        {
            "status": "OK",
            "notOk": False,
            "messages": [],
            "payload": {
                "debtors": [
                    {
                        "rowNumber": i + 1,
                        "name": name,
                        "uccNumber": ucc,
                        "address": "1 MAIN ST",
                        "city": "MIAMI",
                        "zipCode": "33101",
                        "state": "FL",
                        "status": "Filed",
                    }
                    for i, (name, ucc) in enumerate(rows)
                ],
                "nextRowNumber": next_row,
                "previousRowNumber": None,
                "totalExactMatches": None,
            },
        }
    )


def _no_delay_limiter() -> RateLimiter:
    return RateLimiter(base_delay=0.0, jitter_pct=0.0)


# ── _safe_json_loads ────────────────────────────────────────────────────


def test_safe_json_loads_parses_clean_json():
    assert _safe_json_loads('{"a": 1}') == {"a": 1}


def test_safe_json_loads_tolerates_control_chars():
    body = '{"a": "bad\x00\x07name"}'.encode("utf-8")
    out = _safe_json_loads(body)
    assert isinstance(out, dict)
    assert "a" in out


def test_safe_json_loads_returns_none_on_garbage():
    assert _safe_json_loads(b"not json at all <html>") is None


# ── _fetch_secured_party ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_secured_party_returns_joined_names():
    scraper = FloridaScraper(rate_limiter=_no_delay_limiter())
    body = _detail_payload("YELLOWSTONE CAPITAL", "PEARL CAPITAL")
    client = MagicMock()
    client.get = AsyncMock(return_value=_make_response(body=body))
    sp = await scraper._fetch_secured_party(client, "202600000000")
    assert sp == "YELLOWSTONE CAPITAL; PEARL CAPITAL"


@pytest.mark.asyncio
async def test_fetch_secured_party_returns_none_when_empty():
    scraper = FloridaScraper(rate_limiter=_no_delay_limiter())
    client = MagicMock()
    client.get = AsyncMock(return_value=_make_response(body=_detail_payload()))
    sp = await scraper._fetch_secured_party(client, "202600000000")
    assert sp is None


@pytest.mark.asyncio
async def test_fetch_secured_party_returns_none_on_404():
    scraper = FloridaScraper(rate_limiter=_no_delay_limiter())
    client = MagicMock()
    client.get = AsyncMock(return_value=_make_response(status_code=404))
    sp = await scraper._fetch_secured_party(client, "999")
    assert sp is None


@pytest.mark.asyncio
async def test_fetch_secured_party_handles_control_chars():
    scraper = FloridaScraper(rate_limiter=_no_delay_limiter())
    # Inject a NUL inside a name; the existing strict=False path should still parse.
    raw = (
        b'{"status":"OK","notOk":false,"messages":[],'
        b'"payload":{"secNames":[{"name":"BAD\x00LENDER"}]}}'
    )
    client = MagicMock()
    client.get = AsyncMock(return_value=_make_response(body=raw))
    sp = await scraper._fetch_secured_party(client, "1")
    assert sp is not None
    assert "BAD" in sp and "LENDER" in sp


@pytest.mark.asyncio
async def test_fetch_secured_party_handles_network_error():
    scraper = FloridaScraper(rate_limiter=_no_delay_limiter())
    client = MagicMock()
    client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    sp = await scraper._fetch_secured_party(client, "1")
    assert sp is None


# ── _enrich_filings ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_filings_sets_secured_party():
    scraper = FloridaScraper(
        rate_limiter=_no_delay_limiter(),
        enrich_concurrency=2,
    )
    filings = [
        {"filing_number": "F1", "state": "FL", "debtor_name": "X", "secured_party": None,
         "filing_date": None, "collateral_description": None},
        {"filing_number": "F2", "state": "FL", "debtor_name": "Y", "secured_party": None,
         "filing_date": None, "collateral_description": None},
    ]

    detail_map = {
        "F1": _detail_payload("ONDECK CAPITAL"),
        "F2": _detail_payload("KAPITUS"),
    }

    def _route_get(url, *args, **kwargs):
        ucc = url.rsplit("/", 2)[-2]
        return _make_response(body=detail_map.get(ucc, _detail_payload()))

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=_route_get)

    with patch("app.scrapers.states.florida.httpx.AsyncClient", return_value=mock_client):
        out = await scraper._enrich_filings(filings)
    assert out[0]["secured_party"] == "ONDECK CAPITAL"
    assert out[1]["secured_party"] == "KAPITUS"


# ── _fetch_filings — paged loop ────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_filings_paginates_until_next_row_none():
    scraper = FloridaScraper(
        rate_limiter=_no_delay_limiter(),
        index_profiles=[("OrganizationDebtorName", "FiledCompactDebtorNameList")],
        max_pages=5,
        page_cap_per_run=5,
    )

    page0 = _search_payload([("A CORP", "100"), ("B CORP", "101")], next_row=21)
    page1 = _search_payload([("C CORP", "102")], next_row=None)

    calls = {"n": 0}

    def _route_search(url, *args, **kwargs):
        body = page0 if calls["n"] == 0 else page1
        calls["n"] += 1
        return _make_response(body=body)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=_route_search)

    async def noop_checkpoint(*_a, **_k):
        return 0

    async def noop_save(*_a, **_k):
        pass

    with patch("app.scrapers.states.florida.httpx.AsyncClient", return_value=mock_client), \
         patch("app.scrapers.states.florida.get_checkpoint", noop_checkpoint), \
         patch("app.scrapers.states.florida.save_checkpoint", noop_save):
        filings = await scraper._fetch_filings()
    assert [f["filing_number"] for f in filings] == ["100", "101", "102"]
    assert calls["n"] == 2  # second page returned next_row=None → stop


@pytest.mark.asyncio
async def test_fetch_filings_respects_max_pages_cap():
    scraper = FloridaScraper(
        rate_limiter=_no_delay_limiter(),
        index_profiles=[("OrganizationDebtorName", "FiledCompactDebtorNameList")],
        max_pages=2,
        page_cap_per_run=2,
    )

    payloads = [
        _search_payload([("A", "1")], next_row=21),
        _search_payload([("B", "2")], next_row=41),
        # If we ever got to page 3 we'd see this, but max_pages=2 prevents it.
        _search_payload([("C", "3")], next_row=None),
    ]
    idx = {"n": 0}

    def _route_search(url, *args, **kwargs):
        body = payloads[idx["n"]]
        idx["n"] += 1
        return _make_response(body=body)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=_route_search)

    async def noop_checkpoint(*_a, **_k):
        return 0

    async def noop_save(*_a, **_k):
        pass

    with patch("app.scrapers.states.florida.httpx.AsyncClient", return_value=mock_client), \
         patch("app.scrapers.states.florida.get_checkpoint", noop_checkpoint), \
         patch("app.scrapers.states.florida.save_checkpoint", noop_save):
        filings = await scraper._fetch_filings()
    assert [f["filing_number"] for f in filings] == ["1", "2"]
    assert idx["n"] == 2  # stopped after page_cap_per_run


@pytest.mark.asyncio
async def test_fetch_filings_walks_multiple_index_profiles_and_dedupes():
    scraper = FloridaScraper(
        rate_limiter=_no_delay_limiter(),
        index_profiles=[
            ("OrganizationDebtorName", "FiledCompactDebtorNameList"),
            ("OrganizationDebtorName", "FiledActualDebtorNameList"),
        ],
        max_pages=1,
        page_cap_per_run=1,
    )

    pages = [
        _search_payload([("X", "100"), ("Y", "101")], next_row=None),
        _search_payload([("Y", "101"), ("Z", "102")], next_row=None),
    ]
    idx = {"n": 0}

    def _route_search(url, *args, **kwargs):
        body = pages[idx["n"]]
        idx["n"] += 1
        return _make_response(body=body)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=_route_search)

    async def noop_checkpoint(*_a, **_k):
        return 0

    async def noop_save(*_a, **_k):
        pass

    with patch("app.scrapers.states.florida.httpx.AsyncClient", return_value=mock_client), \
         patch("app.scrapers.states.florida.get_checkpoint", noop_checkpoint), \
         patch("app.scrapers.states.florida.save_checkpoint", noop_save):
        filings = await scraper._fetch_filings()
    assert [f["filing_number"] for f in filings] == ["100", "101", "102"]


# ── Constructor: env / defaults ────────────────────────────────────────


def test_constructor_overrides_take_precedence(monkeypatch):
    monkeypatch.setenv("FL_SCRAPE_MAX_PAGES", "99")
    scraper = FloridaScraper(
        max_pages=3,
        index_profiles=[("OrganizationDebtorName", "FiledCompactDebtorNameList")],
        enrich_concurrency=7,
    )
    assert scraper.max_pages == 3
    assert scraper.index_profiles[0][0] == "OrganizationDebtorName"
    assert scraper.enrich_concurrency == 7


@pytest.mark.asyncio
async def test_exact_terms_pass_dedupes_with_standard(monkeypatch):
    """Exact MCA term pass uses searchCategory=Exact and dedupes filing numbers."""
    from unittest.mock import patch

    scraper = FloridaScraper(
        rate_limiter=_no_delay_limiter(),
        index_profiles=[("OrganizationDebtorName", "FiledCompactDebtorNameList")],
        exact_terms=["OnDeck"],
        page_cap_per_run=1,
        max_pages=1,
    )

    standard_body = _search_payload([("ACME LLC", "900")], next_row=None)
    exact_body = _search_payload([("ACME LLC", "900"), ("OTHER LLC", "901")], next_row=None)
    calls: list[str] = []

    def _route(url, *args, **kwargs):
        params = kwargs.get("params") or {}
        category = params.get("searchCategory", "")
        text = params.get("text", "")
        calls.append(f"{category}:{text}")
        body = exact_body if category == "Exact" else standard_body
        return _make_response(body=body)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=_route)

    async def noop_checkpoint(*_a, **_k):
        return 0

    async def noop_save(*_a, **_k):
        pass

    with patch("app.scrapers.states.florida.httpx.AsyncClient", return_value=mock_client), \
         patch("app.scrapers.states.florida.get_checkpoint", noop_checkpoint), \
         patch("app.scrapers.states.florida.save_checkpoint", noop_save):
        filings = await scraper._fetch_filings()

    assert len(filings) == 2
    assert any(c.startswith("Exact:") for c in calls)
    assert filings[0]["filing_number"] == "900"


def test_constructor_parses_env_index_profiles(monkeypatch):
    monkeypatch.setenv(
        "FL_SCRAPE_INDEX_PROFILES",
        "OrganizationDebtorName|FiledCompactDebtorNameList, IndividualDebtorName|FiledCompactDebtorNameList",
    )
    scraper = FloridaScraper()
    assert len(scraper.index_profiles) == 2
