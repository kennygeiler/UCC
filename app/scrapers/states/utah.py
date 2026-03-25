"""Utah SOS UCC filing scraper."""

from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts


class UtahScraper(BaseScraper):
    """Scraper for Utah Secretary of State UCC filings."""

    @property
    def state_code(self) -> str:
        """Return UT state code."""
        return "UT"

    @property
    def tier(self) -> int:
        """Return tier 3 priority."""
        return 3

    @property
    def base_url(self) -> str:
        """Return Utah SOS UCC search URL."""
        return "https://secure.utah.gov/bes/ucc/index.html"

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
        """Build search URL for recent Utah filings."""
        return f"{self.base_url}?type=recent"

    def parse_response(self, html: str) -> list[dict]:
        """Parse Utah SOS HTML into filing dicts."""
        rows = parse_html_table(html)
        return rows_to_filing_dicts(rows, self.state_code, self.column_map)
