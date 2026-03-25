"""Maryland SOS UCC filing scraper."""

from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts


class MarylandScraper(BaseScraper):
    """Scraper for Maryland Secretary of State UCC filings."""

    @property
    def state_code(self) -> str:
        """Return MD state code."""
        return "MD"

    @property
    def tier(self) -> int:
        """Return tier 1 priority."""
        return 1

    @property
    def base_url(self) -> str:
        """Return Maryland SOS UCC search URL."""
        return "https://egov.maryland.gov/ucc/search"

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
        """Build search URL for recent Maryland filings."""
        return f"{self.base_url}?type=recent"

    def parse_response(self, html: str) -> list[dict]:
        """Parse Maryland SOS HTML into filing dicts.

        Args:
            html: Raw HTML from the Maryland SOS portal.

        Returns:
            List of filing dicts matching UCCFiling columns.
        """
        rows = parse_html_table(html)
        return rows_to_filing_dicts(rows, self.state_code, self.column_map)
