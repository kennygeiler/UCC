"""New Jersey SOS UCC filing scraper.

NJ Treasury portal (ASP.NET WebForms). Uses :mod:`app.scrapers.playwright_tier1`
for MCA search terms, shared pagination, and checkpoints.
"""

from __future__ import annotations

from urllib.parse import urljoin

from app.logging import get_logger
from app.scrapers.parsers import parse_date
from app.scrapers.playwright_tier1.base import PlaywrightTier1Scraper
from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint
from app.scrapers.playwright_tier1.detail_fetch import parse_detail_fields_from_text
from app.scrapers.playwright_tier1.pagination import aspnet_grid_next_page
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings

logger = get_logger("nj_scraper")

_GRID_SELECTOR = "[id*=orgResultsGridView]"

# Extract each result row's cell text plus the first in-row link (the lien detail
# link). secured_party is not in the results grid — only on the detail page.
_GRID_ROWS_JS = """() => {
    const grid = document.querySelector('[id*=orgResultsGridView]');
    if (!grid) return [];
    const result = [];
    grid.querySelectorAll('tr').forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 6) return;
        const link = row.querySelector('a[href]');
        result.push({
            cells: Array.from(cells).map(c => c.innerText.trim()),
            detail_href: link ? (link.getAttribute('href') || '') : '',
        });
    });
    return result;
}"""


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

        profile = self._legacy_search_profile()
        completed = await get_page_checkpoint(self.state_code, profile, org_name)
        for _ in range(completed):
            if not await aspnet_grid_next_page(page, _GRID_SELECTOR):
                break

        all_rows: list[dict] = []
        max_pages = self._effective_max_pages()
        page_index = completed

        while page_index < max_pages:
            page_index += 1
            all_rows.extend(await self._parse_grid(page))
            await save_page_checkpoint(self.state_code, profile, org_name, page_index)
            if page_index >= max_pages:
                break
            if not await aspnet_grid_next_page(page, _GRID_SELECTOR):
                break

        return all_rows

    async def _parse_grid(self, page) -> list[dict]:
        rows_data = await page.evaluate(_GRID_ROWS_JS)
        filings: list[dict] = []
        enriched = 0
        for row in rows_data:
            filing = self._row_to_filing(row.get("cells", []))
            if not filing:
                continue
            href = row.get("detail_href", "")
            if self.scrape_settings.fetch_detail and href:
                if await self._fetch_row_detail(page, filing, href):
                    enriched += 1
            filings.append(filing)
        if filings and self.scrape_settings.fetch_detail:
            logger.info(
                "nj_detail_enriched",
                page_rows=len(filings),
                with_secured_party=enriched,
            )
        return filings

    async def _fetch_row_detail(self, page, filing: dict, href: str) -> bool:
        """Open a filing's detail page in a new tab and fill in secured_party.

        Best-effort: returns True when a secured party was found. Any failure
        leaves the grid-derived filing untouched (``secured_party`` stays None),
        so detail fetch never breaks the base scrape or the grid's pagination
        state (the detail page is a separate tab; the grid ``page`` is left as-is).
        """
        if href.lower().startswith("javascript:"):
            return False
        url = href if href.lower().startswith("http") else urljoin(self.base_url, href)
        detail_page = await page.context.new_page()
        try:
            await detail_page.goto(url, wait_until="networkidle", timeout=30_000)
            body = await detail_page.evaluate("() => document.body.innerText || ''")
            parsed = parse_detail_fields_from_text(body)
            if parsed.get("secured_party"):
                filing["secured_party"] = parsed["secured_party"]
            if filing.get("filing_date") is None and parsed.get("filing_date"):
                filing["filing_date"] = parsed["filing_date"]
            return bool(parsed.get("secured_party"))
        except Exception as exc:
            logger.warning("nj_detail_fetch_failed", url=url[:200], error=str(exc)[:200])
            return False
        finally:
            await detail_page.close()

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
