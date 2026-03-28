"""California SOS UCC filing scraper.

The CA SOS portal (bizfileonline.sos.ca.gov) is behind an Imperva Incapsula
WAF and exposes a JSON API at /api/Records/uccsearch.  This scraper uses
Playwright to pass the WAF challenge, then calls the API directly via
fetch() inside the browser context.

The API requires a search term (minimum ~2 chars), so we run searches
for several common secured-party names to get broad coverage of recent
filings within a rolling date window.
"""

from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_date
from app.logging import get_logger

logger = get_logger("ca_scraper")

# Common secured-party names that appear frequently in CA UCC filings.
# Searching by these covers a large portion of daily filings.
_SEARCH_TERMS = [
    "WELLS FARGO",
    "JPMORGAN",
    "BANK OF AMERICA",
    "US BANK",
    "CATERPILLAR",
    "JOHN DEERE",
    "DE LAGE LANDEN",
    "CIT BANK",
    "TOYOTA",
    "CAPITAL ONE",
]

# How many days back from today to search.
_LOOKBACK_DAYS = 3


class CaliforniaScraper(BaseScraper):
    """Scraper for California Secretary of State UCC filings.

    Uses Playwright to pass the Incapsula WAF, then calls the SOS
    JSON API to retrieve recent Financing Statement filings.
    """

    @property
    def state_code(self) -> str:
        return "CA"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return "https://bizfileonline.sos.ca.gov/search/ucc"

    @property
    def column_map(self) -> dict[str, int]:
        # Not used — we parse JSON directly — but required by ABC.
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        # Not used — we parse JSON directly — but required by ABC.
        return []

    async def _fetch(self) -> str:
        """Bypass WAF and query the JSON API for recent filings.

        Returns an empty string; results are collected via _fetch_filings
        which is called from the overridden scrape() method.
        """
        # _fetch is not used directly; scrape() is overridden.
        return ""

    async def scrape(self) -> int:
        """Execute a full scrape: pass WAF, query API, deduplicate, persist."""
        run = await self._start_run()
        try:
            filings = await self._fetch_filings()
            count = await self._persist(filings)
            await self._finish_run(run, count)
            return count
        except Exception as exc:
            await self._fail_run(run, exc)
            raise

    async def _fetch_filings(self) -> list[dict]:
        """Pass WAF and call the JSON API for each search term."""
        await self.rate_limiter.wait(self.state_code, tier=self.tier)

        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=_LOOKBACK_DAYS)
        start_str = start_date.strftime("%m/%d/%Y")
        end_str = today.strftime("%m/%d/%Y")

        seen_filing_numbers: set[str] = set()
        all_filings: list[dict] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{ get: () => undefined });"
            )

            # Navigate to the search page to obtain WAF cookies.
            await page.goto(
                self.base_url,
                wait_until="networkidle",
                timeout=60_000,
            )
            # Wait for WAF challenge to resolve (page grows from ~900 bytes).
            for _ in range(15):
                html = await page.content()
                if len(html) > 5_000:
                    break
                await page.wait_for_timeout(2_000)

            logger.info("waf_passed", state=self.state_code, html_len=len(html))

            for term in _SEARCH_TERMS:
                try:
                    rows = await self._api_search(
                        page, term, start_str, end_str
                    )
                    for row in rows:
                        fn = row.get("filing_number", "")
                        if fn and fn not in seen_filing_numbers:
                            seen_filing_numbers.add(fn)
                            all_filings.append(row)
                    logger.info(
                        "search_batch",
                        term=term,
                        raw=len(rows),
                        unique_so_far=len(all_filings),
                    )
                except Exception as exc:
                    logger.warning(
                        "search_term_failed", term=term, error=str(exc)
                    )

            await browser.close()

        self.rate_limiter.record_success(self.state_code)
        logger.info(
            "ca_fetch_complete",
            total_filings=len(all_filings),
            date_range=f"{start_str}-{end_str}",
        )
        return all_filings

    async def _api_search(
        self,
        page,
        search_value: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Call the CA SOS JSON API via fetch() inside the browser context."""
        payload = {
            "SEARCH_VALUE": search_value,
            "STATUS": "ALL",
            "RECORD_TYPE_ID": "2170",  # Financing Statement
            "FILING_DATE": {"start": start_date, "end": end_date},
            "LAPSE_DATE": {"start": None, "end": None},
        }

        result = await page.evaluate(
            """async (payload) => {
                const resp = await fetch('/api/Records/uccsearch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload),
                });
                if (!resp.ok) return {error: resp.status};
                return await resp.json();
            }""",
            payload,
        )

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(f"API returned status {result['error']}")

        rows_dict = result.get("rows", {})
        filings: list[dict] = []
        for row_data in rows_dict.values():
            filing = self._row_to_filing(row_data)
            if filing:
                filings.append(filing)
        return filings

    def _row_to_filing(self, row: dict) -> dict | None:
        """Convert a single API row dict into a UCCFiling-compatible dict."""
        record_num = row.get("RECORD_NUM", "").strip()
        if not record_num:
            return None

        titles = row.get("TITLE", [])
        debtor = titles[0] if titles else "Unknown"
        # Strip city/state suffix if present (e.g. "ACME LLC - FRESNO, CA")
        if " - " in debtor:
            debtor = debtor.rsplit(" - ", 1)[0].strip()

        parties = row.get("SEC_PARTY", [])
        secured = parties[0] if parties else None
        if secured and " - " in secured:
            secured = secured.rsplit(" - ", 1)[0].strip()

        filing_date_str = row.get("FILING_DATE", "")
        filing_date = parse_date(filing_date_str) if filing_date_str else None

        return {
            "filing_number": record_num,
            "state": self.state_code,
            "debtor_name": debtor or "Unknown",
            "secured_party": secured,
            "filing_date": filing_date,
            "collateral_description": None,
        }
