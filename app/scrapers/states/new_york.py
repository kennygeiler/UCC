"""New York SOS UCC filing scraper.

Cenuity Online Lien Search at ucc-efiling.dos.ny.gov (public via home → Lien Search).

Portal recon (May 2026 — verify after portal upgrades):
  - Entry: home → ``a:has-text("Lien Search")`` → MVC search form ``frm_UCCSearch``.
  - Party radios: ``#rdbDebtor`` (debtor) / ``#rdbSecuredParty`` (secured party);
    VM hook: ``uccSearchVM.RadioButtonClick('DebtorName'|'SecuredPartyName')``.
  - Org type: ``#rdbOrg`` + ``DebtorTypeClick('Organization')``.
  - Match logic: ``#ddlSearchLogic`` — ``SW`` (starts with), ``BW`` (begins with).
  - Org name: ``#UCCSearch_UCCSerach_txtOrgName`` (portal typo preserved).
  - Results grid: ``#xhtml_grid``; pager footer ``Page N / M``.
  - Detail: first-column lien link → detail table with Secured Party / Filing Date rows.
  - No statewide empty-text index (unlike FL REST); volume requires many profile|term sweeps.

Uses :mod:`app.scrapers.playwright_tier1` for multi-profile search, prefix queue,
pagination, checkpoints, and optional detail enrichment.
"""

from __future__ import annotations

from app.logging import get_logger
from app.scrapers.parsers import parse_date
from app.scrapers.playwright_tier1.base import PlaywrightTier1Scraper
from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint
from app.scrapers.playwright_tier1.detail_fetch import fetch_secured_party_from_detail
from app.scrapers.playwright_tier1.pagination import (
    read_pager_info,
    xhtml_grid_goto_last_page,
    xhtml_grid_goto_page,
    xhtml_grid_next_page,
    xhtml_grid_prev_page,
)
from app.scrapers.playwright_tier1.settings import PageOrder
from app.scrapers.playwright_tier1.prefix_queue import (
    get_prefix_offset,
    save_prefix_offset,
    slice_prefix_terms,
)
from app.scrapers.playwright_tier1.profiles import (
    NY_SEARCH_PROFILES,
    PartySearchMode,
    SearchProfileSpec,
    TermSource,
)
from app.scrapers.playwright_tier1.search_terms import build_search_term_list
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings

logger = get_logger("ny_scraper")

_GRID = "#xhtml_grid"
_COL_LIEN_NUMBER = 0
_COL_DEBTOR_NAME = 3
_COL_SECURED_PARTY = 7
_COL_FILING_DATE = 6

_EXTRACT_GRID_JS = """() => {
    const table = document.querySelector('#xhtml_grid');
    if (!table) return { headers: [], rows: [] };
    const headers = [];
    const headerRow = table.querySelector('thead tr');
    if (headerRow) {
        headerRow.querySelectorAll('th, td').forEach(cell => {
            headers.push((cell.innerText || '').trim().toLowerCase());
        });
    }
    const rows = [];
    table.querySelectorAll('tbody tr').forEach(tr => {
        const cells = [];
        tr.querySelectorAll('td').forEach(td => cells.push(td.textContent.trim()));
        rows.push(cells);
    });
    return { headers, rows };
}"""

_HAS_GRID_JS = "() => !!document.querySelector('#xhtml_grid tbody tr')"

_SUBMIT_SEARCH_JS = """(args) => {
    const { partyMode, searchLogic, term } = args;
    const secured = partyMode === 'secured';
    const debtorRadio = document.getElementById('rdbDebtor');
    const securedRadio = document.getElementById('rdbSecuredParty')
        || document.getElementById('rdbSecured');
    if (secured && securedRadio) {
        securedRadio.checked = true;
        if (typeof uccSearchVM !== 'undefined') {
            uccSearchVM.RadioButtonClick('SecuredPartyName');
        }
    } else if (debtorRadio) {
        debtorRadio.checked = true;
        if (typeof uccSearchVM !== 'undefined') {
            uccSearchVM.RadioButtonClick('DebtorName');
        }
    }
    const orgRadio = document.getElementById('rdbOrg');
    if (orgRadio) orgRadio.checked = true;
    if (typeof DebtorTypeClick === 'function') {
        DebtorTypeClick('Organization');
    }
    const logic = document.getElementById('ddlSearchLogic');
    if (logic) logic.value = searchLogic;
    const nameInput = document.getElementById('UCCSearch_UCCSerach_txtOrgName');
    if (nameInput) nameInput.value = term;
}"""


class NewYorkScraper(PlaywrightTier1Scraper):
    """NY UCC lien search — multi-profile sweeps, pagination, optional detail fetch."""

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
        self._run_profile_stats: dict[str, int] = {}

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

    def _active_profiles(self) -> list[SearchProfileSpec]:
        s = self.scrape_settings
        names = list(s.search_profiles) or list(NY_SEARCH_PROFILES)
        if s.profile_filter:
            names = [n for n in names if n == s.profile_filter]
        return [NY_SEARCH_PROFILES[n] for n in names if n in NY_SEARCH_PROFILES]

    async def _load_terms_for_profile(self, profile: SearchProfileSpec) -> list[str]:
        s = self.scrape_settings
        if profile.term_source == TermSource.MCA_ALIASES:
            # Secured-party sweeps use the full MCA alias pool (up to mca_term_limit),
            # not the smaller NY_SCRAPE_MAX_TERMS cap used for debtor prefix batches.
            return await build_search_term_list(
                mca_limit=s.mca_term_limit,
                extra_terms=s.extra_search_terms,
                max_terms=s.mca_term_limit,
            )
        offset = await get_prefix_offset(self.state_code, profile.name)
        batch, next_offset = slice_prefix_terms(
            s.prefix_terms,
            offset=offset,
            max_terms=s.max_terms,
        )
        await save_prefix_offset(self.state_code, profile.name, next_offset)
        extras = [t.strip().upper() for t in s.extra_search_terms if t.strip()]
        seen = set(batch)
        for ex in extras:
            if ex not in seen:
                batch.append(ex)
                seen.add(ex)
        return batch

    async def _fetch_filings_playwright(self) -> list[dict]:
        await self.rate_limiter.wait(self.state_code, tier=self.tier)
        seen: set[str] = set()
        all_filings: list[dict] = []
        pages_used = 0
        page_budget = self.scrape_settings.page_cap_per_run
        self._run_profile_stats = {}

        async with self.playwright_chromium_session(
            launch_args=["--disable-blink-features=AutomationControlled"],
        ) as page:
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{ get: () => undefined });"
            )

            for profile in self._active_profiles():
                terms = await self._load_terms_for_profile(profile)
                profile_count = 0
                for term in terms:
                    if page_budget is not None and pages_used >= page_budget:
                        logger.info(
                            "page_budget_exhausted",
                            pages_used=pages_used,
                            budget=page_budget,
                        )
                        break
                    try:
                        remaining = None
                        if page_budget is not None:
                            remaining = max(0, page_budget - pages_used)
                        before_unique = len(all_filings)
                        rows, pages = await self._search_term_paginated(
                            page, profile, term, pages_remaining=remaining
                        )
                        pages_used += pages
                        inserts = 0
                        for row in rows:
                            fn = row.get("filing_number", "")
                            if fn and fn not in seen:
                                seen.add(fn)
                                all_filings.append(row)
                                profile_count += 1
                                inserts += 1
                        logger.info(
                            "search_batch",
                            profile=profile.name,
                            term=term,
                            pages_fetched=pages,
                            rows_parsed=len(rows),
                            inserts=inserts,
                            unique_so_far=len(all_filings),
                            new_unique=len(all_filings) - before_unique,
                        )
                    except Exception as exc:
                        logger.warning(
                            "search_term_failed",
                            profile=profile.name,
                            term=term,
                            error=str(exc),
                        )
                self._run_profile_stats[profile.name] = profile_count
                if page_budget is not None and pages_used >= page_budget:
                    break

        self.rate_limiter.record_success(self.state_code)
        logger.info(
            "ny_fetch_complete",
            total_filings=len(all_filings),
            pages_used=pages_used,
            profile_stats=self._run_profile_stats,
        )
        return all_filings

    def _page_budget_for_term(self, pages_remaining: int | None) -> int:
        max_pages = self._effective_max_pages()
        if pages_remaining is not None:
            max_pages = min(max_pages, pages_remaining)
        order = self.scrape_settings.page_order
        if order == "recent_only":
            max_pages = min(max_pages, self.scrape_settings.recent_pages)
        return max_pages

    @staticmethod
    def _filing_date_bounds(rows: list[dict]) -> tuple[object | None, object | None]:
        dates = [r["filing_date"] for r in rows if r.get("filing_date")]
        if not dates:
            return None, None
        return min(dates), max(dates)

    async def _scrape_current_grid_page(
        self,
        page,
        *,
        profile: SearchProfileSpec,
        term: str,
    ) -> list[dict]:
        grid = await page.evaluate(_EXTRACT_GRID_JS)
        headers = grid.get("headers") or []
        sp_col = self._secured_party_column(headers)
        page_rows: list[dict] = []
        for row_idx, cells in enumerate(grid.get("rows") or []):
            filing = self._row_to_filing(
                cells,
                profile=profile,
                search_term=term,
                secured_party_col=sp_col,
            )
            if not filing:
                continue
            need_detail = (
                self.scrape_settings.fetch_detail
                and not filing.get("secured_party")
            )
            if need_detail:
                enriched = await self._enrich_row_detail(page, row_idx)
                if enriched.get("secured_party"):
                    filing["secured_party"] = enriched["secured_party"]
                if enriched.get("filing_date") and not filing.get("filing_date"):
                    filing["filing_date"] = enriched["filing_date"]
            page_rows.append(filing)
        return page_rows

    async def _search_term_paginated(
        self,
        page,
        profile: SearchProfileSpec,
        term: str,
        *,
        pages_remaining: int | None = None,
    ) -> tuple[list[dict], int]:
        """Search one profile|term; paginate; return rows and pages consumed."""
        await self._submit_lien_search(page, profile, term)
        if not await page.evaluate(_HAS_GRID_JS):
            return [], 0

        page_current, page_total = await read_pager_info(page, _GRID)
        page_order: PageOrder = self.scrape_settings.page_order
        max_pages = self._page_budget_for_term(pages_remaining)
        completed_pages = await get_page_checkpoint(
            self.state_code, profile.name, term
        )

        logger.info(
            "pager_info",
            profile=profile.name,
            term=term,
            page_current=page_current,
            pager_total=page_total,
            page_order=page_order,
            checkpoint_pages=completed_pages,
            max_pages=max_pages,
        )

        if page_order in ("reverse", "recent_only"):
            rows, pages = await self._search_term_paginated_reverse(
                page,
                profile,
                term,
                page_total=page_total,
                completed_from_end=completed_pages,
                max_pages=max_pages,
            )
        else:
            rows, pages = await self._search_term_paginated_forward(
                page,
                profile,
                term,
                completed_pages=completed_pages,
                max_pages=max_pages,
            )

        date_min, date_max = self._filing_date_bounds(rows)
        logger.info(
            "search_term_paginated",
            profile=profile.name,
            term=term,
            pager_total=page_total,
            page_order=page_order,
            pages_fetched=pages,
            rows_parsed=len(rows),
            filing_date_min=date_min,
            filing_date_max=date_max,
        )
        return rows, pages

    async def _search_term_paginated_forward(
        self,
        page,
        profile: SearchProfileSpec,
        term: str,
        *,
        completed_pages: int,
        max_pages: int,
    ) -> tuple[list[dict], int]:
        """Forward walk: page 1 → N; checkpoint = last completed forward page."""
        all_rows: list[dict] = []
        pages_consumed = 0

        for _ in range(completed_pages):
            if not await xhtml_grid_next_page(page):
                break

        page_index = completed_pages
        while page_index < max_pages:
            page_index += 1
            pages_consumed += 1
            all_rows.extend(
                await self._scrape_current_grid_page(
                    page, profile=profile, term=term
                )
            )
            await save_page_checkpoint(
                self.state_code, profile.name, term, page_index
            )
            if page_index >= max_pages:
                break
            if not await xhtml_grid_next_page(page):
                break
            if not await page.evaluate(_HAS_GRID_JS):
                break

        return all_rows, pages_consumed

    async def _search_term_paginated_reverse(
        self,
        page,
        profile: SearchProfileSpec,
        term: str,
        *,
        page_total: int,
        completed_from_end: int,
        max_pages: int,
    ) -> tuple[list[dict], int]:
        """Reverse walk from last page; checkpoint = pages scraped from end."""
        all_rows: list[dict] = []
        pages_consumed = 0

        if page_total <= 0:
            page_current, page_total = await read_pager_info(page, _GRID)
            if page_total <= 0:
                page_total = max(page_current, 1)

        total = max(page_total, 1)
        if completed_from_end >= max_pages:
            return all_rows, 0

        if completed_from_end > 0:
            resume_page = max(1, total - completed_from_end)
            if resume_page < total:
                await xhtml_grid_goto_page(page, resume_page)
            else:
                await xhtml_grid_goto_last_page(page, _GRID)
        else:
            await xhtml_grid_goto_last_page(page, _GRID)

        pages_from_end = completed_from_end
        while pages_from_end < max_pages:
            pages_from_end += 1
            pages_consumed += 1
            all_rows.extend(
                await self._scrape_current_grid_page(
                    page, profile=profile, term=term
                )
            )
            await save_page_checkpoint(
                self.state_code, profile.name, term, pages_from_end
            )
            if pages_from_end >= max_pages:
                break
            _current, _total = await read_pager_info(page, _GRID)
            if _current <= 1:
                break
            if not await xhtml_grid_prev_page(page):
                break
            if not await page.evaluate(_HAS_GRID_JS):
                break

        return all_rows, pages_consumed

    async def _enrich_row_detail(self, page, row_index: int) -> dict:
        selector = f"#xhtml_grid tbody tr:nth-child({row_index + 1}) td:first-child a"
        return await fetch_secured_party_from_detail(page, lien_selector=selector)

    async def _submit_lien_search(
        self, page, profile: SearchProfileSpec, term: str
    ) -> None:
        await page.goto(self.base_url, wait_until="networkidle", timeout=60_000)
        await page.click('a:has-text("Lien Search")')
        await page.wait_for_load_state("networkidle", timeout=30_000)

        party_mode = (
            "secured"
            if profile.party_mode == PartySearchMode.SECURED
            else "debtor"
        )
        await page.evaluate(
            _SUBMIT_SEARCH_JS,
            {
                "partyMode": party_mode,
                "searchLogic": profile.search_logic,
                "term": term,
            },
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

    def _secured_party_column(self, headers: list[str]) -> int | None:
        for idx, label in enumerate(headers):
            if "secured" in label and "party" in label:
                return idx
        if _COL_SECURED_PARTY < 20:
            return _COL_SECURED_PARTY
        return None

    def _row_to_filing(
        self,
        cells: list[str],
        *,
        profile: SearchProfileSpec,
        search_term: str,
        secured_party_col: int | None,
    ) -> dict | None:
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

        secured_party: str | None = None
        if profile.party_mode == PartySearchMode.SECURED:
            secured_party = search_term.strip().upper() or None
        if secured_party_col is not None and secured_party_col < len(cells):
            grid_sp = cells[secured_party_col].strip()
            if grid_sp:
                secured_party = grid_sp

        return {
            "filing_number": lien_number,
            "state": self.state_code,
            "debtor_name": debtor,
            "secured_party": secured_party,
            "filing_date": filing_date,
            "collateral_description": None,
        }
