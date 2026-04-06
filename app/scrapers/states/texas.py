"""Texas UCC filing scraper.

Uses the Harris County Clerk UCC search at
www.cclerk.hctx.net/applications/websearch/UCC.aspx as the primary data
source.  Harris County (Houston metro) is the largest county in TX and
has the highest volume of UCC filings.

The page is an ASP.NET WebForms app with AJAX UpdatePanels.  Playwright
handles the JS-rendered search results (ListView with paging).

When the TX SOS UCC Filing Tracker
(webservices.sos.state.tx.us/ucc_filing_tracker/status.aspx) is available,
results from that source are merged in as well.

**Playwright consolidation:** Not using ``PlaywrightBaseScraper`` — Harris
UpdatePanel + SOS tracker merge need bespoke async steps beyond single-URL fetch.
"""

import re

import httpx
from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_date
from app.logging import get_logger

logger = get_logger("tx_scraper")

_HC_URL = "https://www.cclerk.hctx.net/applications/websearch/UCC.aspx"
_SOS_TRACKER_URL = (
    "https://webservices.sos.state.tx.us/ucc_filing_tracker/status.aspx"
)

# Common debtor/secured-party names that appear frequently in UCC filings.
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

# Regex patterns for ASP.NET hidden fields (used for SOS tracker fallback).
_VS_RE = re.compile(r'id="__VIEWSTATE"\s+value="([^"]*)"')
_VSG_RE = re.compile(r'id="__VIEWSTATEGENERATOR"\s+value="([^"]*)"')
_EV_RE = re.compile(r'id="__EVENTVALIDATION"\s+value="([^"]*)"')


class TexasScraper(BaseScraper):
    """Scraper for Texas UCC filings.

    Primary source: Harris County Clerk (Playwright).
    Fallback enrichment: TX SOS UCC Filing Tracker (httpx).
    """

    @property
    def state_code(self) -> str:
        return "TX"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return _HC_URL

    @property
    def column_map(self) -> dict[str, int]:
        return {}

    def build_search_url(self) -> str:
        return _HC_URL

    def parse_response(self, html: str) -> list[dict]:
        return []

    async def scrape(self) -> int:
        """Execute a full scrape: query Harris County, optionally SOS tracker."""
        run = await self._start_run()
        try:
            filings = await self._fetch_harris_county()

            # Try SOS tracker as supplementary source (non-fatal if down).
            try:
                sos_filings = await self._fetch_sos_tracker()
                if sos_filings:
                    seen = {f["filing_number"] for f in filings}
                    for f in sos_filings:
                        if f["filing_number"] not in seen:
                            filings.append(f)
                            seen.add(f["filing_number"])
                    logger.info(
                        "sos_tracker_merged",
                        sos_count=len(sos_filings),
                        total=len(filings),
                    )
            except Exception as exc:
                logger.info("sos_tracker_unavailable", error=str(exc)[:200])

            count = await self._persist(filings)
            await self._finish_run(run, count)
            return count
        except Exception as exc:
            await self._fail_run(run, exc)
            raise

    # ------------------------------------------------------------------
    # Harris County Clerk UCC Search (primary)
    # ------------------------------------------------------------------

    async def _fetch_harris_county(self) -> list[dict]:
        """Search Harris County Clerk UCC database via Playwright."""
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

            await page.goto(
                _HC_URL, wait_until="networkidle", timeout=30_000
            )

            for term in _SEARCH_TERMS:
                try:
                    filings = await self._hc_search(page, term)
                    for f in filings:
                        fn = f.get("filing_number", "")
                        if fn and fn not in seen:
                            seen.add(fn)
                            all_filings.append(f)
                    logger.info(
                        "hc_search_batch",
                        term=term,
                        raw=len(filings),
                        unique_so_far=len(all_filings),
                    )
                except Exception as exc:
                    logger.warning(
                        "hc_search_failed", term=term, error=str(exc)[:200]
                    )

            await browser.close()

        self.rate_limiter.record_success(self.state_code)
        logger.info("hc_fetch_complete", total_filings=len(all_filings))
        return all_filings

    async def _hc_search(self, page, term: str) -> list[dict]:
        """Execute a single debtor-name search on Harris County."""
        # Reload the page to get a clean form (AJAX UpdatePanels break
        # input locators after a search completes).
        await page.goto(_HC_URL, wait_until="networkidle", timeout=30_000)

        debtor_input = page.locator("#ctl00_ContentPlaceHolder1_txtOR")
        search_btn = page.locator("#ctl00_ContentPlaceHolder1_btnSearch")

        await debtor_input.fill(term)
        await search_btn.click()

        # Wait for AJAX update panel to settle.
        await page.wait_for_timeout(5000)

        # Check result count.
        count_el = page.locator("#ctl00_ContentPlaceHolder1_lblCount")
        count_text = await count_el.inner_text()
        match = re.search(r"(\d+)", count_text)
        if not match or int(match.group(1)) == 0:
            return []

        total = int(match.group(1))
        logger.info("hc_results", term=term, total=total)

        return await self._hc_extract_rows(page, min(total, 50))

    async def _hc_extract_rows(self, page, max_rows: int) -> list[dict]:
        """Extract filing rows from the Harris County ListView."""
        filings: list[dict] = []
        for i in range(max_rows):
            prefix = (
                f"#ctl00_ContentPlaceHolder1_ListView1_ctrl{i}"
            )
            file_no_el = page.locator(f"{prefix}_lblFileNo")

            # Stop if element doesn't exist (fewer results than expected).
            if not await file_no_el.count():
                break

            file_no = (await file_no_el.inner_text()).strip()
            if not file_no:
                continue

            file_date_el = page.locator(f"{prefix}_lblFileDate")
            collateral_el = page.locator(f"{prefix}_lblCollateral")

            file_date = ""
            if await file_date_el.count():
                file_date = (await file_date_el.inner_text()).strip()

            collateral = None
            if await collateral_el.count():
                collateral = (await collateral_el.inner_text()).strip()
                if not collateral:
                    collateral = None

            # Collect debtor names from nested ListView.
            debtors: list[str] = []
            for j in range(5):
                desc_el = page.locator(
                    f"{prefix}_lvOR_ctrl{j}_lblDesc"
                )
                if await desc_el.count():
                    debtors.append(
                        (await desc_el.inner_text()).strip()
                    )

            debtor_name = debtors[0] if debtors else "Unknown"
            secured_party = debtors[1] if len(debtors) > 1 else None

            filings.append(
                {
                    "filing_number": file_no,
                    "state": self.state_code,
                    "debtor_name": debtor_name,
                    "secured_party": secured_party,
                    "filing_date": parse_date(file_date) if file_date else None,
                    "collateral_description": collateral,
                }
            )

        return filings

    # ------------------------------------------------------------------
    # TX SOS UCC Filing Tracker (supplementary)
    # ------------------------------------------------------------------

    async def _fetch_sos_tracker(self) -> list[dict]:
        """Query the SOS filing tracker; returns [] if unavailable."""
        seen: set[str] = set()
        all_filings: list[dict] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            init_resp = await client.get(_SOS_TRACKER_URL)
            init_resp.raise_for_status()
            tokens = _extract_tokens(init_resp.text)

            for term in _SEARCH_TERMS[:5]:  # Fewer terms for supplementary
                try:
                    rows = await self._sos_search(client, term, tokens)
                    for f in rows:
                        fn = f.get("filing_number", "")
                        if fn and fn not in seen:
                            seen.add(fn)
                            all_filings.append(f)
                except Exception:
                    continue

        return all_filings

    async def _sos_search(
        self,
        client: httpx.AsyncClient,
        term: str,
        tokens: dict[str, str],
    ) -> list[dict]:
        """POST a party-name search to the SOS filing tracker."""
        data = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": tokens["viewstate"],
            "__VIEWSTATEGENERATOR": tokens["viewstate_gen"],
            "__EVENTVALIDATION": tokens["event_validation"],
            "RadioButtonList1": "Search by Party Name",
            "txtSubmitterName": term,
            "txtFirstName": "",
            "txtLastName": "",
            "btnSubmitterName": "Search",
        }
        resp = await client.post(_SOS_TRACKER_URL, data=data)
        resp.raise_for_status()
        html = resp.text
        tokens.update(_extract_tokens(html))

        if "No entries found" in html:
            return []

        return self._parse_sos_results(html)

    def _parse_sos_results(self, html: str) -> list[dict]:
        """Parse the SOS filing tracker HTML table into filing dicts."""
        from app.scrapers.parsers import parse_html_table, rows_to_filing_dicts

        rows = parse_html_table(html)
        if not rows:
            return []

        header_row = rows[0]
        col_idx = _map_columns(header_row)
        if col_idx.get("filing_number") is None:
            col_idx = {
                "filing_number": 0,
                "debtor_name": 1,
                "secured_party": 2,
                "filing_date": 3,
                "collateral_description": 4,
            }

        return rows_to_filing_dicts(rows, self.state_code, col_idx)


def _extract_tokens(html: str) -> dict[str, str]:
    """Extract ASP.NET ViewState tokens from HTML."""
    vs = _VS_RE.search(html)
    vsg = _VSG_RE.search(html)
    ev = _EV_RE.search(html)
    return {
        "viewstate": vs.group(1) if vs else "",
        "viewstate_gen": vsg.group(1) if vsg else "",
        "event_validation": ev.group(1) if ev else "",
    }


def _map_columns(header_row: list[str]) -> dict[str, int]:
    """Map filing fields to column indices based on header text."""
    mapping: dict[str, int] = {}
    for i, hdr in enumerate(header_row):
        h = hdr.lower().strip()
        if "filing" in h and ("number" in h or "no" in h or "#" in h):
            mapping.setdefault("filing_number", i)
        elif "document" in h and ("number" in h or "no" in h or "#" in h):
            mapping.setdefault("filing_number", i)
        elif "debtor" in h:
            mapping.setdefault("debtor_name", i)
        elif "secured" in h or "party" in h:
            mapping.setdefault("secured_party", i)
        elif "date" in h and "filing" in h:
            mapping.setdefault("filing_date", i)
        elif "date" in h:
            mapping.setdefault("filing_date", i)
        elif "collateral" in h:
            mapping.setdefault("collateral_description", i)
        elif "name" in h and "debtor" not in mapping:
            mapping.setdefault("debtor_name", i)
    return mapping
