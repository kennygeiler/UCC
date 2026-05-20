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

from datetime import datetime, timedelta, timezone

from app.logging import get_logger
from app.scrapers.parsers import parse_date
from app.scrapers.playwright_tier1.base import PlaywrightTier1Scraper
from app.scrapers.playwright_tier1.checkpoints import get_page_checkpoint, save_page_checkpoint
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
    SearchProfileSpec,
)
from app.scrapers.playwright_tier1.settings import PlaywrightScrapeSettings

logger = get_logger("ny_scraper")

_GRID = "#xhtml_grid"
_COL_LIEN_NUMBER = 0
_COL_DEBTOR_NAME = 3
_COL_FILING_DATE = 6

_EXTRACT_GRID_JS = """() => {
    const table = document.querySelector('#xhtml_grid');
    if (!table) return { headers: [], rows: [], lien_ids: [] };
    const headers = [];
    const headerRow = table.querySelector('thead tr');
    if (headerRow) {
        headerRow.querySelectorAll('th, td').forEach(cell => {
            headers.push((cell.innerText || '').trim().toLowerCase());
        });
    }
    const rows = [];
    const lienIds = [];
    table.querySelectorAll('tbody tr').forEach(tr => {
        const cells = [];
        tr.querySelectorAll('td').forEach(td => cells.push(td.textContent.trim()));
        rows.push(cells);
        const hidden = tr.querySelector('input[type=hidden]');
        let lid = hidden ? (hidden.value || '') : '';
        if (!lid) {
            const a = tr.querySelector('td a[onclick]');
            const m = a && (a.getAttribute('onclick') || '').match(/\\((\\d+)\\)/);
            if (m) lid = m[1];
        }
        lienIds.push(lid);
    });
    return { headers, rows, lien_ids: lienIds };
}"""

_HAS_GRID_JS = "() => !!document.querySelector('#xhtml_grid tbody tr')"

# Reach a lien detail page by replicating NavigateLienInfo's form POST. Run in a
# separate tab so the results grid (and pagination) on the main page survive.
_DETAIL_POST_JS = """(args) => {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/OnlineUCCSearch/OnlineLienInformation';
    for (const [name, value] of [['lienId', args.lienId], ['source', args.source]]) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = String(value);
        form.appendChild(input);
    }
    document.body.appendChild(form);
    form.submit();
}"""

# Detail page = stacked section tables; return each as rows of cell text.
_DETAIL_TABLES_JS = """() => [...document.querySelectorAll('table')].map(
    table => [...table.querySelectorAll('tr')].map(
        tr => [...tr.querySelectorAll('th, td')].map(c => (c.innerText || '').trim())
    )
)"""


def _parse_ny_lien_detail(tables: list[list[list[str]]]) -> dict:
    """Extract secured party and filing date from OnlineLienInformation tables.

    Each section renders as its own table: a header row then data rows. The
    secured-party table's header contains "Secured Party Name"; the lien-info
    table's header contains "Date Filed". Returns the first secured party found.
    """
    secured_party: str | None = None
    filing_date = None
    for table in tables:
        if not table:
            continue
        header = [c.strip().lower() for c in table[0]]
        if secured_party is None and any("secured party name" in h for h in header):
            for data_row in table[1:]:
                if data_row and data_row[0].strip():
                    secured_party = data_row[0].strip()
                    break
        if filing_date is None and "date filed" in header:
            idx = header.index("date filed")
            for data_row in table[1:]:
                if idx < len(data_row) and data_row[idx].strip():
                    filing_date = parse_date(data_row[idx].strip().split()[0])
                    if filing_date:
                        break
    return {"secured_party": secured_party, "filing_date": filing_date}

_SUBMIT_SEARCH_JS = """(args) => {
    const { searchLogic, term, filingDateFrom } = args;
    const debtorRadio = document.getElementById('rdbDebtor');
    if (debtorRadio) {
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
    // Scope to active UCC liens — skip lapsed/released liens and federal tax liens.
    const status = document.getElementById('ddlLienStatus');
    if (status) status.value = '1';
    const lienType = document.getElementById('ddlLienType');
    if (lienType) lienType.value = '1';
    // Optional filing-date lower bound (MM/DD/YYYY) to scope to recent filings.
    if (filingDateFrom) {
        const df = document.getElementById('UCCSearch_UCCSerach_txtFilingDateFrom');
        if (df) df.value = filingDateFrom;
    }
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
        rows = grid.get("rows") or []
        lien_ids = grid.get("lien_ids") or []
        sp_col = self._secured_party_column(headers)
        logger.info(
            "ny_grid_layout",
            profile=profile.name,
            term=term,
            headers=headers,
            sample_rows=rows[:3],
        )
        # NavigateLienInfo posts source = the first row's lien id for the whole set.
        source = next((lid for lid in lien_ids if lid), "")
        page_rows: list[dict] = []
        enriched = 0
        for row_idx, cells in enumerate(rows):
            filing = self._row_to_filing(
                cells,
                profile=profile,
                search_term=term,
                secured_party_col=sp_col,
            )
            if not filing:
                continue
            lien_id = lien_ids[row_idx] if row_idx < len(lien_ids) else ""
            need_detail = (
                self.scrape_settings.fetch_detail
                and not filing.get("secured_party")
                and bool(lien_id)
            )
            if need_detail:
                detail = await self._fetch_lien_detail(page, lien_id, source)
                if detail.get("secured_party"):
                    filing["secured_party"] = detail["secured_party"]
                    enriched += 1
                if detail.get("filing_date") and not filing.get("filing_date"):
                    filing["filing_date"] = detail["filing_date"]
            page_rows.append(filing)
        if page_rows and self.scrape_settings.fetch_detail:
            logger.info(
                "ny_detail_enriched",
                profile=profile.name,
                term=term,
                page_rows=len(page_rows),
                with_secured_party=enriched,
            )
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

    async def _fetch_lien_detail(self, page, lien_id: str, source: str) -> dict:
        """Fetch one lien's detail page in a separate tab; parse the secured party.

        NY reaches a lien detail via a form POST (NavigateLienInfo). Running it
        in a new tab keeps the results grid — and pagination — on the main page
        intact. Best-effort: any failure leaves secured_party as None.
        """
        detail_page = await page.context.new_page()
        try:
            await detail_page.goto(
                self.base_url, wait_until="domcontentloaded", timeout=30_000
            )
            await detail_page.evaluate(
                _DETAIL_POST_JS, {"lienId": lien_id, "source": source or lien_id}
            )
            await detail_page.wait_for_load_state("networkidle", timeout=30_000)
            tables = await detail_page.evaluate(_DETAIL_TABLES_JS)
            return _parse_ny_lien_detail(tables)
        except Exception as exc:
            logger.warning(
                "ny_detail_fetch_failed", lien_id=lien_id, error=str(exc)[:200]
            )
            return {"secured_party": None, "filing_date": None}
        finally:
            await detail_page.close()

    def _filing_date_from(self) -> str | None:
        """Filing-date lower bound (MM/DD/YYYY) from NY_SCRAPE_FILING_LOOKBACK_DAYS.

        Returns None when the lookback is 0 (full-history crawl).
        """
        from app.config import Settings

        days = Settings().NY_SCRAPE_FILING_LOOKBACK_DAYS
        if days <= 0:
            return None
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        return cutoff.strftime("%m/%d/%Y")

    async def _submit_lien_search(
        self, page, profile: SearchProfileSpec, term: str
    ) -> None:
        await page.goto(self.base_url, wait_until="networkidle", timeout=60_000)
        await page.click('a:has-text("Lien Search")')
        await page.wait_for_load_state("networkidle", timeout=30_000)

        await page.evaluate(
            _SUBMIT_SEARCH_JS,
            {
                "searchLogic": profile.search_logic,
                "term": term,
                "filingDateFrom": self._filing_date_from(),
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
        """Grid column index for secured party, or None when absent.

        The NY results grid has no secured-party column — secured party comes
        from the lien detail page (debtor profiles) or the search term itself
        (secured-party profiles). Only return an index when a header explicitly
        names it; never guess a column, or a date/status cell gets mis-stored
        as the secured party and the filing fails MCA classification.
        """
        for idx, label in enumerate(headers):
            if "secured" in label and "party" in label:
                return idx
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
