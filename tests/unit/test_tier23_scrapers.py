"""Tier 2 / Tier 3 scraper parse and URL tests (fixtures only, no live SOS)."""

from app.scrapers.states.colorado import ColoradoScraper
from app.scrapers.states.delaware import DelawareScraper
from app.scrapers.states.michigan import MichiganScraper
from app.scrapers.states.nevada import NevadaScraper

_CO_MI_HTML = """<table>
<tr><th>Filing</th><th>Date</th><th>Debtor</th><th>Secured</th><th>Collateral</th></tr>
<tr><td>2024-0001234567</td><td>03/15/2024</td><td>Acme LLC</td><td>Wells Fargo</td><td>Equipment</td></tr>
</table>"""

_DE_NV_HTML = """<table>
<tr><th>Filing</th><th>Date</th><th>Debtor</th><th>Secured</th><th>Collateral</th></tr>
<tr><td>DE-999888</td><td>01/10/2024</td><td>Brick LLC</td><td>Chase</td><td>Inventory</td></tr>
</table>"""


def test_colorado_parse_and_url():
    """CO Tier 2: parse_response maps columns; URL uses SOS host and recent type."""
    s = ColoradoScraper()
    url = s.build_search_url()
    assert url.startswith("https://")
    assert "sos.state.co.us" in url
    assert "recent" in url or "UCCSearchCriteria" in url
    rows = s.parse_response(_CO_MI_HTML)
    assert len(rows) == 1
    assert rows[0]["state"] == "CO"
    assert "2024" in rows[0]["filing_number"]


def test_michigan_parse_and_url():
    """MI Tier 2: parse_response maps columns; URL uses LARA search host."""
    s = MichiganScraper()
    url = s.build_search_url()
    assert url.startswith("https://")
    assert "lara.state.mi.us" in url
    rows = s.parse_response(_CO_MI_HTML)
    assert len(rows) == 1
    assert rows[0]["state"] == "MI"


def test_delaware_parse_and_url():
    """DE Tier 3: parse_response maps columns; URL points at DE corp search."""
    s = DelawareScraper()
    url = s.build_search_url()
    assert url.startswith("https://")
    assert "delaware.gov" in url
    rows = s.parse_response(_DE_NV_HTML)
    assert len(rows) == 1
    assert rows[0]["state"] == "DE"
    assert rows[0]["filing_number"] == "DE-999888"


def test_nevada_parse_and_url():
    """NV Tier 3: parse_response maps columns; URL points at Nevada SOS."""
    s = NevadaScraper()
    url = s.build_search_url()
    assert url.startswith("https://")
    assert "nv.gov" in url
    rows = s.parse_response(_DE_NV_HTML)
    assert len(rows) == 1
    assert rows[0]["state"] == "NV"
