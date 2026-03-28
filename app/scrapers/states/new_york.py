"""New York SOS UCC filing scraper.

The old NY UCC system (appext20.dos.ny.gov) was decommissioned in March 2025.
The replacement is Cenuity Online at ucc-efiling.dos.ny.gov, a server-rendered
ASP.NET MVC app protected by reCAPTCHA Enterprise and CSRF tokens.

This scraper uses Playwright to handle the JS challenges and render results.
"""

from app.scrapers.playwright_base import PlaywrightBaseScraper
from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts


class NewYorkScraper(PlaywrightBaseScraper):
    """Scraper for New York Secretary of State UCC filings.

    Uses Playwright to navigate the Cenuity Online portal which requires
    JavaScript for reCAPTCHA Enterprise and CSRF token handling.
    """

    wait_for_selector = "table"
    page_timeout = 45_000

    @property
    def state_code(self) -> str:
        """Return NY state code."""
        return "NY"

    @property
    def tier(self) -> int:
        """Return tier 1 priority."""
        return 1

    @property
    def base_url(self) -> str:
        """Return New York SOS UCC search URL (Cenuity Online)."""
        return "https://ucc-efiling.dos.ny.gov/OnlineUCCSearch/PublicOnlineUccSearch"

    @property
    def column_map(self) -> dict[str, int]:
        """Map UCCFiling fields to table column indices."""
        return {
            "filing_number": 0,
            "debtor_name": 1,
            "secured_party": 2,
            "filing_date": 3,
            "collateral_description": 4,
        }

    def build_search_url(self) -> str:
        """Build search URL for New York UCC search portal."""
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        """Parse New York SOS HTML into filing dicts.

        Args:
            html: Rendered HTML from the New York SOS portal.

        Returns:
            List of filing dicts matching UCCFiling columns.
        """
        rows = parse_html_table(html)
        return rows_to_filing_dicts(rows, self.state_code, self.column_map)
