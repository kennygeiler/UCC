"""California SOS UCC filing scraper.

The CA SOS portal (bizfileonline.sos.ca.gov) is behind an Imperva Incapsula
WAF and renders search results via JavaScript. This scraper uses Playwright
to bypass the WAF challenge and render the JS-driven page.

California also offers an official UCC XML API at calicodev.sos.ca.gov
which is the recommended long-term approach (requires a free API key).
"""

from app.scrapers.playwright_base import PlaywrightBaseScraper
from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts


class CaliforniaScraper(PlaywrightBaseScraper):
    """Scraper for California Secretary of State UCC filings.

    Uses Playwright to handle the Incapsula WAF and JS rendering.
    Falls back to HTML table parsing once the page is fully rendered.
    """

    wait_for_selector = "table"
    page_timeout = 45_000

    @property
    def state_code(self) -> str:
        """Return CA state code."""
        return "CA"

    @property
    def tier(self) -> int:
        """Return tier 1 priority."""
        return 1

    @property
    def base_url(self) -> str:
        """Return California SOS UCC search URL."""
        return "https://bizfileonline.sos.ca.gov/search/ucc"

    @property
    def column_map(self) -> dict[str, int]:
        """Map UCCFiling fields to table column indices."""
        return {
            "filing_number": 0,
            "filing_date": 1,
            "debtor_name": 2,
            "secured_party": 3,
            "collateral_description": 4,
        }

    def build_search_url(self) -> str:
        """Build search URL for recent California filings."""
        return f"{self.base_url}?type=recent"

    def parse_response(self, html: str) -> list[dict]:
        """Parse California SOS HTML into filing dicts.

        Args:
            html: Rendered HTML from the California SOS portal.

        Returns:
            List of filing dicts matching UCCFiling columns.
        """
        rows = parse_html_table(html)
        return rows_to_filing_dicts(rows, self.state_code, self.column_map)
