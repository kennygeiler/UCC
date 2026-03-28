"""New Jersey SOS UCC filing scraper.

The NJ Treasury portal (njportal.com) uses ASP.NET WebForms with ViewState,
so simple HTTP requests won't work.  This scraper uses Playwright to:
1. Navigate to the non-certified search page.
2. Select "Organization" search type + "Status Report" output.
3. Search for common secured-party names to get broad filing coverage.
4. Parse the results GridView and paginate through all pages.
"""

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_date
from app.logging import get_logger

logger = get_logger("nj_scraper")

# Common debtor/secured-party org names for broad coverage of NJ filings.
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


class NewJerseyScraper(BaseScraper):
    """Scraper for New Jersey Secretary of State UCC filings.

    Uses Playwright to interact with the ASP.NET WebForms portal
    and parse results from the non-certified search.
    """

    @property
    def state_code(self) -> str:
        return "NJ"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return "https://www.njportal.com/ucc/search/noncertifiedsearch.aspx"

    @property
    def column_map(self) -> dict[str, int]:
        # Not used — we parse the GridView directly — but required by ABC.
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        # Not used — we parse the GridView directly — but required by ABC.
        return []

    async def scrape(self) -> int:
        """Execute a full scrape: search portal, parse results, persist."""
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
        """Use Playwright to search the NJ portal for each search term."""
        await self.rate_limiter.wait(self.state_code, tier=self.tier)

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

            for term in _SEARCH_TERMS:
                try:
                    rows = await self._search_org(page, term)
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
            "nj_fetch_complete",
            total_filings=len(all_filings),
        )
        return all_filings

    async def _search_org(self, page, org_name: str) -> list[dict]:
        """Run a single organization search and collect all pages of results."""
        # Navigate to the search page fresh for each term
        await page.goto(self.base_url, wait_until="networkidle", timeout=30_000)

        # Step 1: Select Organization search type + Status Report output
        await page.click(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_radioSwitchOrgPerson_1"
        )
        await page.click(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_radioOutputList_0"
        )
        await page.click(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_"
            "StartNavigationTemplateContainerID_btnContinue"
        )
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(500)

        # Step 2: Fill organization name and submit
        await page.fill(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_txtOrganizationName",
            org_name,
        )
        await page.click(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_"
            "StepNavigationTemplateContainerID_btnContinue"
        )
        # Wait for the results grid or "no results" message to appear
        await page.wait_for_load_state("networkidle", timeout=60_000)
        # Extra wait for ASP.NET postback rendering
        await page.wait_for_timeout(1_000)

        # Collect results from all pages
        all_rows: list[dict] = []
        while True:
            page_rows = await self._parse_grid(page)
            all_rows.extend(page_rows)

            if not await self._go_to_next_page(page):
                break

        return all_rows

    async def _parse_grid(self, page) -> list[dict]:
        """Parse the orgResultsGridView on the current page."""
        # Use page.evaluate to extract all data in one JS call,
        # avoiding stale element handle issues across navigations.
        rows_data = await page.evaluate("""() => {
            const grid = document.querySelector('[id*=orgResultsGridView]');
            if (!grid) return [];
            const rows = grid.querySelectorAll('tr');
            const result = [];
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length < 6) continue;
                const texts = Array.from(cells).map(c => c.innerText.trim());
                result.push(texts);
            }
            return result;
        }""")

        filings: list[dict] = []
        for cell_texts in rows_data:
            filing = self._row_to_filing(cell_texts)
            if filing:
                filings.append(filing)
        return filings

    def _row_to_filing(self, cells: list[str]) -> dict | None:
        """Convert a grid row (list of cell texts) into a filing dict.

        Grid columns (0-indexed):
          0: checkbox (empty)
          1: Organization (debtor name)
          2: City
          3: Filing Number
          4: Filing Status
          5: Filing Date (formatted, e.g. "01/07/2026")
          6: Filing Date (raw timestamp - ignored)
          7: Page Count
        """
        if len(cells) < 6:
            return None

        filing_number = cells[3].strip()
        if not filing_number or not any(c.isdigit() for c in filing_number):
            return None

        debtor_name = cells[1].strip() or "Unknown"
        filing_date_str = cells[5].strip()
        filing_date = parse_date(filing_date_str) if filing_date_str else None

        return {
            "filing_number": filing_number,
            "state": self.state_code,
            "debtor_name": debtor_name,
            "secured_party": None,  # Not shown in search results
            "filing_date": filing_date,
            "collateral_description": None,
        }

    async def _go_to_next_page(self, page) -> bool:
        """Navigate to the next page of results via JS postback.

        Returns True if we navigated to a next page, False if no more pages.
        """
        next_page_num = await page.evaluate("""() => {
            const cells = document.querySelectorAll(
                '[id*=orgResultsGridView] tr:last-child td'
            );
            for (const cell of cells) {
                const text = cell.innerText;
                if (text.includes('Page')) {
                    const match = text.match(/Page\\s+(\\d+)\\/(\\d+)/);
                    if (match) {
                        const current = parseInt(match[1]);
                        const total = parseInt(match[2]);
                        if (current < total) return current + 1;
                    }
                }
            }
            return 0;
        }""")

        if not next_page_num:
            return False

        # Trigger the ASP.NET postback directly via JS to avoid click issues
        grid_id = await page.evaluate("""() => {
            const grid = document.querySelector('[id*=orgResultsGridView]');
            return grid ? grid.id.replace(/_/g, '$') : '';
        }""")

        if not grid_id:
            return False

        await page.evaluate(
            f"__doPostBack('{grid_id}', 'Page${next_page_num}')"
        )
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(1_000)
        return True
