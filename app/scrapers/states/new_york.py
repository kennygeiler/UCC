"""New York SOS UCC filing scraper.

Cenuity Online Lien Search at ucc-efiling.dos.ny.gov (public, no login via home link).

Uses :mod:`app.scrapers.playwright_tier1` for MCA search terms, pagination, checkpoints,
and optional detail enrichment for ``secured_party``.
"""

from __future__ import annotations

from app.logging import get_logger
from app.scrapers.parsers import parse_date
from app.scrapers.playwright_tier1.base import PlaywrightTier1Scraper
from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint
from app.scrapers.playwright_tier1.detail_fetch import fetch_secured_party_from_detail
from app.scrapers.playwright_tier1.pagination import xhtml_grid_next_page
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings

logger = get_logger("ny_scraper")

_GRID = "#xhtml_grid"
_COL_LIEN_NUMBER = 0
_COL_DEBTOR_NAME = 3
_COL_FILING_DATE = 6

_EXTRACT_GRID_JS = """() => {
    const table = document.querySelector('#xhtml_grid');
    if (!table) return [];
    const rows = [];
    table.querySelectorAll('tbody tr').forEach(tr => {
        const cells = [];
        tr.querySelectorAll('td').forEach(td => cells.push(td.textContent.trim()));
        rows.push(cells);
    });
    return rows;
}"""

_HAS_GRID_JS = "() => !!document.querySelector('#xhtml_grid tbody tr')"


class NewYorkScraper(PlaywrightTier1Scraper):
    """NY UCC lien search — broad MCA terms, pagination, optional detail fetch."""

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
        return "NY"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return "https://ucc-efiling.dos.ny.gov"

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
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{ get: () => undefined });"
            )

            for term in terms:
                try:
                    rows = await self._search_term_paginated(page, term)
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
        logger.info("ny_fetch_complete", total_filings=len(all_filings))
        return all_filings

    async def _search_term_paginated(self, page, term: str) -> list[dict]:
        """Search one org term; paginate; optional detail enrichment."""
        await self._submit_lien_search(page, term)
        if not await page.evaluate(_HAS_GRID_JS):
            return []

        completed_pages = await get_page_checkpoint(self.state_code, term)
        max_pages = self._effective_max_pages()
        all_rows: list[dict] = []

        for _ in range(completed_pages):
            if not await xhtml_grid_next_page(page):
                break

        page_index = completed_pages
        while page_index < max_pages:
            page_index += 1

            grid_rows = await page.evaluate(_EXTRACT_GRID_JS)
            for row_idx, cells in enumerate(grid_rows):
                filing = self._row_to_filing(cells)
                if not filing:
                    continue
                if (
                    self.scrape_settings.fetch_detail
                    and not filing.get("secured_party")
                ):
                    enriched = await self._enrich_row_detail(page, row_idx)
                    if enriched.get("secured_party"):
                        filing["secured_party"] = enriched["secured_party"]
                    if enriched.get("filing_date") and not filing.get("filing_date"):
                        filing["filing_date"] = enriched["filing_date"]
                all_rows.append(filing)

            await save_page_checkpoint(self.state_code, term, page_index)

            if page_index >= max_pages:
                break
            if not await xhtml_grid_next_page(page):
                break
            if not await page.evaluate(_HAS_GRID_JS):
                break

        return all_rows

    async def _enrich_row_detail(self, page, row_index: int) -> dict:
        """Open lien detail for one grid row (0-based data row index)."""
        selector = f"#xhtml_grid tbody tr:nth-child({row_index + 1}) td:first-child a"
        return await fetch_secured_party_from_detail(page, lien_selector=selector)

    async def _submit_lien_search(self, page, term: str) -> None:
        await page.goto(self.base_url, wait_until="networkidle", timeout=60_000)
        await page.click('a:has-text("Lien Search")')
        await page.wait_for_load_state("networkidle", timeout=30_000)

        await page.evaluate(
            """(term) => {
                document.getElementById('rdbDebtor').checked = true;
                if (typeof uccSearchVM !== 'undefined') {
                    uccSearchVM.RadioButtonClick('DebtorName');
                }
                document.getElementById('rdbOrg').checked = true;
                if (typeof DebtorTypeClick === 'function') {
                    DebtorTypeClick('Organization');
                }
                document.getElementById('ddlSearchLogic').value = 'SW';
                document.getElementById('UCCSearch_UCCSerach_txtOrgName').value = term;
            }""",
            term,
        )
        await page.wait_for_timeout(300)

        async with page.expect_navigation(wait_until="networkidle", timeout=45_000):
            await page.evaluate(
                """() => {
                    uccSearchVM.SearchButtonClick(
                        document.getElementById('frm_UCCSearch')
                    );
                }"""
            )

    def _row_to_filing(self, cells: list[str]) -> dict | None:
        if len(cells) <= _COL_FILING_DATE:
            return None
        lien_number = cells[_COL_LIEN_NUMBER].strip()
        if not lien_number or not any(c.isdigit() for c in lien_number):
            return None
        debtor = cells[_COL_DEBTOR_NAME].strip() or "Unknown"
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
