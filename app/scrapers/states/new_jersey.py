"""New Jersey SOS UCC filing scraper.

NJ Treasury portal (ASP.NET WebForms). Uses :mod:`app.scrapers.playwright_tier1`
for MCA search terms, shared pagination, and checkpoints.
"""

from __future__ import annotations

from app.logging import get_logger
from app.scrapers.parsers import parse_date
from app.scrapers.playwright_tier1.base import PlaywrightTier1Scraper
from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint
from app.scrapers.playwright_tier1.pagination import aspnet_grid_next_page
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings

logger = get_logger("nj_scraper")

_GRID_SELECTOR = "[id*=orgResultsGridView]"


class NewJerseyScraper(PlaywrightTier1Scraper):
    """Scraper for New Jersey Secretary of State UCC filings."""

    def __init__(
        self,
        rate_limiter=None,
        *,
        run_consolidation: bool = True,
        scrape_settings: PlaywrightScrapeSettings | None = None,
    ) -> None:
        super().__init__(
            rate_limiter=rate_limiter,
            run_consolidation=run_consolidation,
            scrape_settings=scrape_settings,
        )

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
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    def parse_response(self, html: str) -> list[dict]:
        return []

    async def _fetch_filings_playwright(self) -> list[dict]:
        await self.rate_limiter.wait(self.state_code, tier=self.tier)
        terms = await self._load_search_terms()
        seen: set[str] = set()
        all_filings: list[dict] = []

        async with self.playwright_chromium_session(
            launch_args=["--disable-blink-features=AutomationControlled"],
        ) as page:
            for term in terms:
                try:
                    rows = await self._search_org(page, term)
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
                    logger.warning("search_term_failed", term=term, error=str(exc))

        self.rate_limiter.record_success(self.state_code)
        logger.info("nj_fetch_complete", total_filings=len(all_filings))
        return all_filings

    async def _search_org(self, page, org_name: str) -> list[dict]:
        await page.goto(self.base_url, wait_until="networkidle", timeout=30_000)
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

        await page.fill(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_txtOrganizationName",
            org_name,
        )
        await page.click(
            "#ctl00_mainContent_DebtorSearch1_Wizard1_"
            "StepNavigationTemplateContainerID_btnContinue"
        )
        await page.wait_for_load_state("networkidle", timeout=60_000)
        await page.wait_for_timeout(1_000)

        completed = await get_page_checkpoint(self.state_code, org_name)
        for _ in range(completed):
            if not await aspnet_grid_next_page(page, _GRID_SELECTOR):
                break

        all_rows: list[dict] = []
        max_pages = self._effective_max_pages()
        page_index = completed

        while page_index < max_pages:
            page_index += 1
            all_rows.extend(await self._parse_grid(page))
            await save_page_checkpoint(self.state_code, org_name, page_index)
            if page_index >= max_pages:
                break
            if not await aspnet_grid_next_page(page, _GRID_SELECTOR):
                break

        return all_rows

    async def _parse_grid(self, page) -> list[dict]:
        rows_data = await page.evaluate("""() => {
            const grid = document.querySelector('[id*=orgResultsGridView]');
            if (!grid) return [];
            const result = [];
            grid.querySelectorAll('tr').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length < 6) return;
                result.push(Array.from(cells).map(c => c.innerText.trim()));
            });
            return result;
        }""")
        filings: list[dict] = []
        for cell_texts in rows_data:
            filing = self._row_to_filing(cell_texts)
            if filing:
                filings.append(filing)
        return filings

    def _row_to_filing(self, cells: list[str]) -> dict | None:
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
            "secured_party": None,
            "filing_date": filing_date,
            "collateral_description": None,
        }
