"""Tests for all 10 Tier 1 state scrapers with mocked HTTP and sample HTML."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.states.california import CaliforniaScraper
from app.scrapers.states.florida import FloridaScraper
from app.scrapers.states.georgia import GeorgiaScraper
from app.scrapers.states.illinois import IllinoisScraper
from app.scrapers.states.maryland import MarylandScraper
from app.scrapers.states.new_jersey import NewJerseyScraper
from app.scrapers.states.new_york import NewYorkScraper
from app.scrapers.states.ohio import OhioScraper
from app.scrapers.states.pennsylvania import PennsylvaniaScraper
from app.scrapers.states.texas import TexasScraper


def _make_sample_html(filing_num: str, debtor: str, secured: str) -> str:
    """Build sample HTML table matching standard column layouts.

    Args:
        filing_num: Filing number value.
        debtor: Debtor name.
        secured: Secured party name.

    Returns:
        HTML string with a single data row.
    """
    return f"""<table>
<tr><th>Filing</th><th>Date</th><th>Debtor</th><th>Secured</th><th>Collateral</th></tr>
<tr><td>{filing_num}</td><td>03/15/2024</td><td>{debtor}</td><td>{secured}</td><td>All assets</td></tr>
</table>"""


def _make_alt_html(filing_num: str, debtor: str, secured: str) -> str:
    """Build sample HTML for scrapers with debtor-first column layout.

    Args:
        filing_num: Filing number value.
        debtor: Debtor name.
        secured: Secured party name.

    Returns:
        HTML string with debtor in column 1.
    """
    return f"""<table>
<tr><th>Filing</th><th>Debtor</th><th>Secured</th><th>Date</th><th>Collateral</th></tr>
<tr><td>{filing_num}</td><td>{debtor}</td><td>{secured}</td><td>03/15/2024</td><td>Equipment</td></tr>
</table>"""


def _make_fl_api_json(ucc_number: str, debtor: str) -> str:
    """Build sample Florida API JSON response.

    Args:
        ucc_number: UCC filing number.
        debtor: Debtor name.

    Returns:
        JSON string mimicking the FL public search API.
    """
    return json.dumps({
        "status": "OK",
        "notOk": False,
        "payload": {
            "debtors": [
                {
                    "rowNumber": 1,
                    "name": debtor,
                    "uccNumber": ucc_number,
                    "address": "123 Main St",
                    "city": "MIAMI",
                    "zipCode": "33142",
                    "state": "FL",
                    "status": "Filed",
                }
            ],
            "nextRowNumber": 21,
            "previousRowNumber": None,
            "totalExactMatches": None,
        },
    })


# Scrapers that use standard HTML table layout (filing_date in col 1)
SCRAPERS_STANDARD = [
    (CaliforniaScraper, "CA", "CA-2024-001"),
    (NewJerseyScraper, "NJ", "NJ-2024-001"),
    (IllinoisScraper, "IL", "IL-2024-001"),
    (OhioScraper, "OH", "OH-2024-001"),
]

# Scrapers that use alt HTML table layout (debtor_name in col 1)
SCRAPERS_ALT = [
    (TexasScraper, "TX", "TX-2024-001"),
    (NewYorkScraper, "NY", "NY-2024-001"),
    (GeorgiaScraper, "GA", "GA-2024-001"),
    (PennsylvaniaScraper, "PA", "PA-2024-001"),
    (MarylandScraper, "MD", "MD-2024-001"),
]


@pytest.mark.parametrize("scraper_cls,state,filing_num", SCRAPERS_STANDARD)
def test_standard_scraper_properties(scraper_cls, state, filing_num):
    """Standard-layout scrapers should have correct state code and tier."""
    scraper = scraper_cls()
    assert scraper.state_code == state
    assert scraper.tier == 1
    assert scraper.base_url.startswith("https://")


@pytest.mark.parametrize("scraper_cls,state,filing_num", SCRAPERS_ALT)
def test_alt_scraper_properties(scraper_cls, state, filing_num):
    """Alt-layout scrapers should have correct state code and tier."""
    scraper = scraper_cls()
    assert scraper.state_code == state
    assert scraper.tier == 1
    assert scraper.base_url.startswith("https://")


def test_florida_scraper_properties():
    """Florida scraper should have correct state code and tier."""
    scraper = FloridaScraper()
    assert scraper.state_code == "FL"
    assert scraper.tier == 1
    assert scraper.base_url.startswith("https://")


@pytest.mark.parametrize("scraper_cls,state,filing_num", SCRAPERS_STANDARD)
def test_standard_scraper_parse(scraper_cls, state, filing_num):
    """Standard-layout scrapers should parse sample HTML correctly."""
    scraper = scraper_cls()
    html = _make_sample_html(filing_num, "Test Corp", "Lender LLC")
    filings = scraper.parse_response(html)
    assert len(filings) == 1
    assert filings[0]["filing_number"] == filing_num
    assert filings[0]["state"] == state
    assert filings[0]["debtor_name"] == "Test Corp"
    assert filings[0]["secured_party"] == "Lender LLC"


@pytest.mark.parametrize("scraper_cls,state,filing_num", SCRAPERS_ALT)
def test_alt_scraper_parse(scraper_cls, state, filing_num):
    """Alt-layout scrapers should parse sample HTML correctly."""
    scraper = scraper_cls()
    html = _make_alt_html(filing_num, "Acme Inc", "Bank of X")
    filings = scraper.parse_response(html)
    assert len(filings) == 1
    assert filings[0]["filing_number"] == filing_num
    assert filings[0]["state"] == state
    assert filings[0]["debtor_name"] == "Acme Inc"
    assert filings[0]["secured_party"] == "Bank of X"


def test_florida_scraper_parse_json():
    """Florida scraper should parse API JSON response correctly."""
    scraper = FloridaScraper()
    json_str = _make_fl_api_json("FL-2024-001", "Test Corp")
    filings = scraper.parse_response(json_str)
    assert len(filings) == 1
    assert filings[0]["filing_number"] == "FL-2024-001"
    assert filings[0]["state"] == "FL"
    assert filings[0]["debtor_name"] == "Test Corp"


def test_florida_scraper_parse_html_fallback():
    """Florida scraper should fall back to HTML parsing for test compat."""
    scraper = FloridaScraper()
    html = _make_sample_html("FL-2024-001", "Test Corp", "Lender LLC")
    filings = scraper.parse_response(html)
    assert len(filings) == 1
    assert filings[0]["filing_number"] == "FL-2024-001"
    assert filings[0]["state"] == "FL"


@pytest.mark.parametrize("scraper_cls,state,filing_num", SCRAPERS_STANDARD)
def test_standard_scraper_empty_html(scraper_cls, state, filing_num):
    """Standard scrapers should return empty list for empty HTML."""
    scraper = scraper_cls()
    filings = scraper.parse_response("<html><body></body></html>")
    assert filings == []


@pytest.mark.parametrize("scraper_cls,state,filing_num", SCRAPERS_ALT)
def test_alt_scraper_empty_html(scraper_cls, state, filing_num):
    """Alt scrapers should return empty list for empty HTML."""
    scraper = scraper_cls()
    filings = scraper.parse_response("<html><body></body></html>")
    assert filings == []


def test_florida_scraper_empty_json():
    """Florida scraper should return empty list for empty API response."""
    scraper = FloridaScraper()
    empty_json = json.dumps({"status": "OK", "payload": {"debtors": []}})
    filings = scraper.parse_response(empty_json)
    assert filings == []


@pytest.mark.parametrize(
    "scraper_cls,state,filing_num",
    SCRAPERS_STANDARD + SCRAPERS_ALT + [(FloridaScraper, "FL", "FL-2024-001")],
)
def test_scraper_build_search_url(scraper_cls, state, filing_num):
    """Every scraper build_search_url should return a URL string."""
    scraper = scraper_cls()
    url = scraper.build_search_url()
    assert isinstance(url, str)
    assert url.startswith("https://")


@pytest.mark.asyncio
async def test_scraper_fetch_mocked_httpx():
    """BaseScraper _fetch should use httpx with rate limiting (non-Playwright scrapers)."""
    from app.scrapers.rate_limiter import RateLimiter
    from app.scrapers.states.new_jersey import NewJerseyScraper

    rl = RateLimiter(base_delay=0.0, jitter_pct=0.0)
    scraper = NewJerseyScraper(rate_limiter=rl)
    html = _make_sample_html("NJ-2024-001", "Corp", "Bank")

    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch("app.scrapers.base.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await scraper._fetch()
        assert "NJ-2024-001" in result


@pytest.mark.asyncio
async def test_florida_fetch_mocked():
    """Florida scraper _fetch should hit the public search API."""
    from app.scrapers.rate_limiter import RateLimiter

    rl = RateLimiter(base_delay=0.0, jitter_pct=0.0)
    scraper = FloridaScraper(rate_limiter=rl)
    api_json = _make_fl_api_json("FL-2024-099", "API Corp")

    mock_response = MagicMock()
    mock_response.text = api_json
    mock_response.raise_for_status = MagicMock()

    with patch("app.scrapers.states.florida.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await scraper._fetch()
        assert "FL-2024-099" in result
