"""Texas SOS UCC filing scraper.

The old Texas UCC system (direct.sos.state.tx.us/ucc) was decommissioned.
The replacement is an Appian-based portal at texas-sos.appiancloud.us which:
  - Requires authenticated login
  - Charges $1.00 per search
  - Is entirely JS-rendered (Appian low-code platform)
  - Has no public API

This scraper uses Playwright to handle the JS-rendered portal. Note that
full functionality requires SOS Portal credentials configured via
TEXAS_SOS_USERNAME / TEXAS_SOS_PASSWORD environment variables.
"""

from app.scrapers.playwright_base import PlaywrightBaseScraper
from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts
from app.logging import get_logger

logger = get_logger("scraper")


class TexasScraper(PlaywrightBaseScraper):
    """Scraper for Texas Secretary of State UCC filings.

    DEGRADED: The TX SOS migrated to a paid, authenticated Appian portal.
    This scraper will attempt to load the portal but requires credentials
    and per-search payment to return results.
    """

    wait_for_selector = "table"
    page_timeout = 45_000

    @property
    def state_code(self) -> str:
        """Return TX state code."""
        return "TX"

    @property
    def tier(self) -> int:
        """Return tier 1 priority."""
        return 1

    @property
    def base_url(self) -> str:
        """Return Texas SOS portal URL."""
        return "https://texas-sos.appiancloud.us/suite/sites/home-page"

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
        """Build search URL for Texas SOS portal."""
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        """Parse Texas SOS HTML into filing dicts.

        Args:
            html: Rendered HTML from the Texas SOS portal.

        Returns:
            List of filing dicts matching UCCFiling columns.
        """
        rows = parse_html_table(html)
        return rows_to_filing_dicts(rows, self.state_code, self.column_map)
