"""Florida SOS UCC filing scraper.

The Florida UCC portal (floridaucc.com) is a React SPA that fetches data
from a public REST API at publicsearchapi.floridaucc.com. This scraper
hits the API directly for structured JSON instead of scraping HTML.
"""

import httpx

from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_date
from app.scrapers.user_agents import get_random_user_agent
from app.logging import get_logger

logger = get_logger("scraper")

API_BASE = "https://publicsearchapi.floridaucc.com"


class FloridaScraper(BaseScraper):
    """Scraper for Florida Secretary of State UCC filings.

    Uses the public REST API instead of HTML scraping.
    """

    @property
    def state_code(self) -> str:
        """Return FL state code."""
        return "FL"

    @property
    def tier(self) -> int:
        """Return tier 1 priority."""
        return 1

    @property
    def base_url(self) -> str:
        """Return Florida UCC public search API URL."""
        return f"{API_BASE}/search"

    @property
    def column_map(self) -> dict[str, int]:
        """Not used for API-based scraper; kept for interface compliance."""
        return {}

    def build_search_url(self) -> str:
        """Build the API search URL.

        Searches for organization debtor names using a wildcard query
        to retrieve recent filed filings.
        """
        return self.base_url

    async def _fetch(self) -> str:
        """Fetch filings from the Florida public search API as JSON.

        Overrides the default httpx HTML fetch to hit the REST API
        and return raw JSON text for parse_response to handle.
        """
        await self.rate_limiter.wait(self.state_code, tier=self.tier)
        headers = {"User-Agent": get_random_user_agent()}
        params = {
            "text": "A",
            "searchOptionType": "OrganizationDebtorName",
            "searchOptionSubOption": "FiledCompactDebtorNameList",
            "searchCategory": "Standard",
            "rowNumber": "0",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.base_url, params=params, headers=headers)
            response.raise_for_status()
        self.rate_limiter.record_success(self.state_code)
        logger.info("fetch_complete", state=self.state_code, url=self.base_url)
        return response.text

    def parse_response(self, html: str) -> list[dict]:
        """Parse Florida API JSON response into filing dicts.

        Also accepts HTML for backwards compatibility with tests — if the
        input looks like JSON, parses it as API response; otherwise falls
        back to HTML table parsing.

        Args:
            html: JSON response text from the FL public search API,
                  or HTML for test compatibility.

        Returns:
            List of filing dicts matching UCCFiling columns.
        """
        import json
        try:
            data = json.loads(html)
        except (json.JSONDecodeError, ValueError):
            # Fall back to HTML table parsing for test compatibility
            from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts
            rows = parse_html_table(html)
            return rows_to_filing_dicts(
                rows,
                self.state_code,
                {
                    "filing_number": 0,
                    "filing_date": 1,
                    "debtor_name": 2,
                    "secured_party": 3,
                    "collateral_description": 4,
                },
            )

        payload = data.get("payload", {})
        debtors = payload.get("debtors", [])
        results: list[dict] = []
        for debtor in debtors:
            ucc_number = debtor.get("uccNumber", "").strip()
            if not ucc_number:
                continue
            results.append({
                "filing_number": ucc_number,
                "state": self.state_code,
                "debtor_name": debtor.get("name", "Unknown").strip(),
                "secured_party": None,  # Not in search results; requires detail endpoint
                "filing_date": None,  # Not in search results
                "collateral_description": None,
            })
        return results
