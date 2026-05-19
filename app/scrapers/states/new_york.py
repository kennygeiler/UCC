"""New York SOS UCC filing scraper.

The NY UCC system at ucc-efiling.dos.ny.gov provides a public Lien Search
portal (no login required). It is a server-rendered ASP.NET MVC app.

This scraper uses Playwright to:
1. Navigate to the Lien Search page.
2. For each common debtor-organization name, fill the search form and submit.
3. Parse the results table (#xhtml_grid) from the returned HTML.

No JSON API is available — results come back as full HTML pages.

**Playwright consolidation:** Not using ``PlaywrightBaseScraper`` — repeated
form submit + grid parsing per search term; California-style session helper
does not cover this flow yet.
"""

from playwright.async_api import async_playwright

from app.scrapers.base_enriched import PostScrapeScraper
from app.scrapers.parsers import parse_date
from app.logging import get_logger

logger = get_logger("ny_scraper")

# Common debtor organization names for broad coverage of recent filings.
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

# Table column indices for the #xhtml_grid results table:
# 0: Lien Number, 1: Serial Number, 2: Lien Subtype, 3: Debtor Name,
# 4: Debtor Address, 5: Debtor Type, 6: Filing Date/Time,
# 7: Lapse Date/Time, 8: Lien Status
_COL_LIEN_NUMBER = 0
_COL_DEBTOR_NAME = 3
_COL_FILING_DATE = 6
_COL_LIEN_STATUS = 8


class NewYorkScraper(PostScrapeScraper):
    """Scraper for New York Secretary of State UCC filings.

    Uses Playwright to interact with the Cenuity Online Lien Search portal.
    Secured party is not on the results grid — enrichment would need detail pages.
    """

    def __init__(self, rate_limiter=None, *, run_consolidation: bool = True) -> None:
        super().__init__(rate_limiter=rate_limiter)
        self.run_consolidation = run_consolidation

    @property
    def state_code(self) -> str:
        return "NY"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return "https://ucc-efiling.dos.ny.gov"

    @property
    def column_map(self) -> dict[str, int]:
        # Not used — we parse the table directly — but required by ABC.
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        # Not used — we parse via Playwright evaluate — but required by ABC.
        return []

    async def _fetch(self) -> str:
        # Not used directly; scrape() is overridden.
        return ""

    async def scrape(self) -> int:
        """Execute a full scrape: navigate portal, search, parse, persist."""
        run = await self._start_run()
        try:
            filings = await self._fetch_filings()
            return await self._finish_scrape_run(run, filings)
        except Exception as exc:
            await self._fail_run(run, exc)
            raise

    async def _fetch_filings(self) -> list[dict]:
        """Navigate the Lien Search portal and collect filings."""
        await self.rate_limiter.wait(self.state_code, tier=self.tier)

        seen: set[str] = set()
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

            for term in _SEARCH_TERMS:
                try:
                    rows = await self._search_term(page, term)
                    for row in rows:
                        fn = row.get("filing_number", "")
                        if fn and fn not in seen:
                            seen.add(fn)
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
            "ny_fetch_complete",
            total_filings=len(all_filings),
        )
        return all_filings

    async def _search_term(self, page, term: str) -> list[dict]:
        """Navigate to Lien Search, fill the form, submit, and parse results."""
        # Navigate to homepage then click Lien Search link (direct URL
        # redirects to login page).
        await page.goto(
            self.base_url,
            wait_until="networkidle",
            timeout=60_000,
        )
        await page.click('a:has-text("Lien Search")')
        await page.wait_for_load_state("networkidle", timeout=30_000)

        # Set up the form: Debtor Name > Organization > Starts With
        # Use page.evaluate to set form state and submit in one go to avoid
        # race conditions with navigation.
        await page.evaluate(
            """(term) => {
                // Select Debtor Name radio
                document.getElementById('rdbDebtor').checked = true;
                uccSearchVM.RadioButtonClick('DebtorName');

                // Select Organization radio
                document.getElementById('rdbOrg').checked = true;
                DebtorTypeClick('Organization');

                // Set search logic to "Starts with"
                document.getElementById('ddlSearchLogic').value = 'SW';

                // Fill organization name
                document.getElementById(
                    'UCCSearch_UCCSerach_txtOrgName'
                ).value = term;
            }""",
            term,
        )
        await page.wait_for_timeout(300)

        # Submit the form and wait for navigation to complete
        async with page.expect_navigation(
            wait_until="networkidle", timeout=45_000
        ):
            await page.evaluate(
                """() => {
                    uccSearchVM.SearchButtonClick(
                        document.getElementById('frm_UCCSearch')
                    );
                }"""
            )

        # Check if the results table appeared
        has_table = await page.evaluate(
            "() => !!document.querySelector('#xhtml_grid tbody tr')"
        )
        if not has_table:
            return []

        # Extract all rows from the results table
        rows_data = await page.evaluate(
            """() => {
                const table = document.querySelector('#xhtml_grid');
                const rows = [];
                table.querySelectorAll('tbody tr').forEach(tr => {
                    const cells = [];
                    tr.querySelectorAll('td').forEach(
                        td => cells.push(td.textContent.trim())
                    );
                    rows.push(cells);
                });
                return rows;
            }"""
        )

        filings = []
        for cells in rows_data:
            filing = self._row_to_filing(cells)
            if filing:
                filings.append(filing)
        return filings

    def _row_to_filing(self, cells: list[str]) -> dict | None:
        """Convert a table row into a UCCFiling-compatible dict."""
        if len(cells) <= _COL_FILING_DATE:
            return None

        lien_number = cells[_COL_LIEN_NUMBER].strip()
        if not lien_number or not any(c.isdigit() for c in lien_number):
            return None

        debtor = cells[_COL_DEBTOR_NAME].strip() or "Unknown"

        # Filing date comes as "M/D/YYYY H:MM:SS AM/PM" — extract date part
        date_str = cells[_COL_FILING_DATE].strip()
        if " " in date_str:
            date_str = date_str.split(" ")[0]
        filing_date = parse_date(date_str) if date_str else None

        return {
            "filing_number": lien_number,
            "state": self.state_code,
            "debtor_name": debtor,
            "secured_party": None,
            "filing_date": filing_date,
            "collateral_description": None,
        }
