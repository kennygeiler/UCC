"""Tests for all 10 Tier 1 state scrapers with mocked HTTP and sample HTML."""

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


# Map each scraper to the correct HTML generator based on its column_map layout
SCRAPERS_STANDARD = [
    (CaliforniaScraper, "CA", "CA-2024-001"),
    (FloridaScraper, "FL", "FL-2024-001"),
    (NewJerseyScraper, "NJ", "NJ-2024-001"),
    (IllinoisScraper, "IL", "IL-2024-001"),
    (OhioScraper, "OH", "OH-2024-001"),
]

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


@pytest.mark.parametrize(
    "scraper_cls,state,filing_num",
    SCRAPERS_STANDARD + SCRAPERS_ALT,
)
def test_scraper_build_search_url(scraper_cls, state, filing_num):
    """Every scraper build_search_url should return a URL string."""
    scraper = scraper_cls()
    url = scraper.build_search_url()
    assert isinstance(url, str)
    assert url.startswith("https://")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scraper_cls,state,filing_num",
    SCRAPERS_STANDARD[:1],  # Test fetch with one scraper to keep tests fast
)
async def test_scraper_fetch_mocked(scraper_cls, state, filing_num):
    """Scraper _fetch should use httpx with rate limiting."""
    from app.scrapers.rate_limiter import RateLimiter

    rl = RateLimiter(base_delay=0.0, jitter_pct=0.0)
    scraper = scraper_cls(rate_limiter=rl)
    html = _make_sample_html(filing_num, "Corp", "Bank")

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
        assert filing_num in result
