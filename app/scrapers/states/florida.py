"""Florida SOS UCC filing scraper.

Uses the public REST API at publicsearchapi.floridaucc.com. Coverage comes from
deep Standard-mode pagination (``rowNumber`` / ``nextRowNumber``) across multiple
index profiles — **not** A–Z text cursors (Standard ignores ``text``).

Pipeline: multi-index search → optional Exact MCA pass → enrich → persist →
post-scrape consolidation (:func:`app.consolidation.pipeline.run_post_scrape_pipeline`).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from sqlalchemy import select

from app.config import Settings
from app.consolidation.checkpoints import get_checkpoint, profile_key, save_checkpoint
from app.consolidation.pipeline import run_post_scrape_pipeline
from app.db import get_session
from app.logging import get_logger
from app.models.filing import UCCFiling
from app.scrapers.base import BaseScraper
from app.scrapers.parsers import parse_date
from app.scrapers.user_agents import get_random_user_agent

logger = get_logger("scraper")

API_BASE = "https://publicsearchapi.floridaucc.com"
PAGE_SIZE = 20

DEFAULT_INDEX_PROFILES: list[tuple[str, str]] = [
    ("OrganizationDebtorName", "FiledCompactDebtorNameList"),
    ("OrganizationDebtorName", "FiledActualDebtorNameList"),
    ("IndividualDebtorName", "FiledCompactDebtorNameList"),
]


def _safe_json_loads(payload: bytes | str) -> dict | list | None:
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    else:
        text = payload
    try:
        return json.loads(text, strict=False)
    except (json.JSONDecodeError, ValueError):
        sanitized = "".join(c for c in text if c >= " " or c in "\t\n\r")
        try:
            return json.loads(sanitized, strict=False)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("fl_json_unparseable", error=str(exc), len=len(text))
            return None


def _extract_collateral_from_filing_payload(meta: dict) -> str | None:
    """Map collateral from ``GET /Filings/{ucc}`` payload when the API exposes it.

    As of 2026-05 the public FL search API typically returns filing dates only;
    collateral keys are probed for forward compatibility.
    """
    for key in (
        "collateral",
        "collateralDescription",
        "collateral_description",
        "collateralText",
    ):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    coll_list = meta.get("collaterals")
    if isinstance(coll_list, list):
        parts = [
            (item.get("description") or item.get("text") or "").strip()
            for item in coll_list
            if isinstance(item, dict)
        ]
        parts = [p for p in parts if p]
        if parts:
            return "; ".join(parts)
    return None


def parse_index_profiles(raw: str) -> list[tuple[str, str]]:
    """Parse ``FL_SCRAPE_INDEX_PROFILES`` env value."""
    profiles: list[tuple[str, str]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        sep = "|" if "|" in part else (":" if ":" in part else None)
        if not sep:
            continue
        opt_type, sub = part.split(sep, 1)
        profiles.append((opt_type.strip(), sub.strip()))
    return profiles or list(DEFAULT_INDEX_PROFILES)


class FloridaScraper(BaseScraper):
    """Florida UCC scraper with multi-index pagination and checkpoints."""

    def __init__(
        self,
        rate_limiter=None,
        *,
        max_pages: int | None = None,
        page_cap_per_run: int | None = None,
        index_profiles: list[tuple[str, str]] | None = None,
        exact_terms: list[str] | None = None,
        enrich_concurrency: int | None = None,
        fetch_filing_date: bool | None = None,
        run_consolidation: bool = True,
    ) -> None:
        super().__init__(rate_limiter=rate_limiter)
        try:
            settings = Settings()
        except Exception:
            settings = None

        self.max_pages = max_pages if max_pages is not None else (
            settings.FL_SCRAPE_MAX_PAGES if settings else 500
        )
        self.page_cap_per_run = page_cap_per_run if page_cap_per_run is not None else (
            settings.FL_SCRAPE_PAGE_CAP_PER_RUN if settings else 50
        )
        if index_profiles is not None:
            self.index_profiles = index_profiles
        elif settings:
            self.index_profiles = parse_index_profiles(settings.FL_SCRAPE_INDEX_PROFILES)
        else:
            self.index_profiles = list(DEFAULT_INDEX_PROFILES)

        if exact_terms is not None:
            self.exact_terms = exact_terms
        elif settings and settings.FL_SCRAPE_EXACT_TERMS.strip():
            self.exact_terms = [
                t.strip() for t in settings.FL_SCRAPE_EXACT_TERMS.split(",") if t.strip()
            ]
        else:
            self.exact_terms = []

        self.enrich_concurrency = enrich_concurrency if enrich_concurrency is not None else (
            settings.FL_SCRAPE_ENRICH_CONCURRENCY if settings else 5
        )
        self.fetch_filing_date = fetch_filing_date if fetch_filing_date is not None else (
            settings.FL_SCRAPE_FETCH_FILING_DATE if settings else True
        )
        self.run_consolidation = run_consolidation

    @property
    def state_code(self) -> str:
        return "FL"

    @property
    def tier(self) -> int:
        return 1

    @property
    def base_url(self) -> str:
        return f"{API_BASE}/search"

    @property
    def column_map(self) -> dict[str, int]:
        return {}

    def build_search_url(self) -> str:
        return self.base_url

    async def _fetch(self) -> str:
        """Legacy first-page fetch for unit tests."""
        await self.rate_limiter.wait(self.state_code, tier=self.tier)
        headers = {"User-Agent": get_random_user_agent()}
        opt_type, sub = self.index_profiles[0]
        params = {
            "text": "",
            "searchOptionType": opt_type,
            "searchOptionSubOption": sub,
            "searchCategory": "Standard",
            "rowNumber": "0",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.base_url, params=params, headers=headers)
            response.raise_for_status()
        self.rate_limiter.record_success(self.state_code)
        return response.text

    async def _fetch_search_page(
        self,
        client: httpx.AsyncClient,
        *,
        search_option_type: str,
        search_option_sub_option: str,
        row_number: int,
        text: str = "",
        search_category: str = "Standard",
    ) -> dict | None:
        params = {
            "text": text,
            "searchOptionType": search_option_type,
            "searchOptionSubOption": search_option_sub_option,
            "searchCategory": search_category,
            "rowNumber": str(row_number),
        }
        headers = {"User-Agent": get_random_user_agent()}
        try:
            response = await client.get(
                self.base_url, params=params, headers=headers
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "fl_search_page_failed",
                profile=profile_key(search_option_type, search_option_sub_option),
                row_number=row_number,
                category=search_category,
                error=str(exc),
            )
            self.rate_limiter.record_error(self.state_code)
            return None
        data = _safe_json_loads(response.content)
        if not isinstance(data, dict):
            return None
        return data.get("payload") or {}

    @staticmethod
    def _debtor_to_filing(debtor: dict, state_code: str) -> dict | None:
        ucc_number = (debtor.get("uccNumber") or "").strip()
        if not ucc_number:
            return None
        return {
            "filing_number": ucc_number,
            "state": state_code,
            "debtor_name": (debtor.get("name") or "Unknown").strip() or "Unknown",
            "secured_party": None,
            "filing_date": None,
            "collateral_description": None,
        }

    async def _fetch_secured_party(
        self,
        client: httpx.AsyncClient,
        ucc_number: str,
    ) -> str | None:
        url = f"{API_BASE}/Filings/{ucc_number}/deb-sec-names"
        try:
            response = await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("fl_detail_fetch_failed", ucc_number=ucc_number, error=str(exc))
            return None
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            return None
        data = _safe_json_loads(response.content)
        if not isinstance(data, dict):
            return None
        payload = data.get("payload") or {}
        names = [
            (entry.get("name") or "").strip()
            for entry in payload.get("secNames", [])
            if isinstance(entry, dict) and entry.get("name")
        ]
        names = [n for n in names if n]
        return "; ".join(names) if names else None

    async def _fetch_filing_metadata(
        self,
        client: httpx.AsyncClient,
        ucc_number: str,
    ) -> dict | None:
        url = f"{API_BASE}/Filings/{ucc_number}"
        try:
            response = await client.get(url)
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        data = _safe_json_loads(response.content)
        if not isinstance(data, dict):
            return None
        return data.get("payload") or {}

    async def _enrich_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        filing: dict,
    ) -> None:
        async with semaphore:
            sp = await self._fetch_secured_party(client, filing["filing_number"])
            if sp:
                filing["secured_party"] = sp
            if self.fetch_filing_date:
                meta = await self._fetch_filing_metadata(client, filing["filing_number"])
                if meta:
                    date_str = meta.get("date") or meta.get("createDate")
                    if isinstance(date_str, str):
                        parsed = self._parse_iso_date(date_str)
                        if parsed is not None:
                            filing["filing_date"] = parsed
                    collateral = _extract_collateral_from_filing_payload(meta)
                    if collateral and not filing.get("collateral_description"):
                        filing["collateral_description"] = collateral

    @staticmethod
    def _parse_iso_date(date_str: str):
        from datetime import datetime, timezone

        try:
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return parse_date(date_str.split("T")[0]) if "T" in date_str else parse_date(date_str)

    async def _enrich_filings(self, filings: list[dict]) -> list[dict]:
        if not filings:
            return filings
        semaphore = asyncio.Semaphore(max(1, self.enrich_concurrency))
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": get_random_user_agent()},
        ) as client:
            tasks = [self._enrich_one(client, semaphore, f) for f in filings]
            await asyncio.gather(*tasks, return_exceptions=False)
        return filings

    async def _paginate_profile(
        self,
        client: httpx.AsyncClient,
        seen: set[str],
        all_filings: list[dict],
        *,
        search_option_type: str,
        search_option_sub_option: str,
        text: str = "",
        search_category: str = "Standard",
        resume_row: int | None = None,
        save_checkpoints: bool = True,
    ) -> None:
        """Walk pages for one index profile; dedupe into *all_filings*."""
        prof = profile_key(search_option_type, search_option_sub_option)
        row_number = resume_row if resume_row is not None else await get_checkpoint(
            self.state_code, prof
        )
        pages_this_run = 0

        while pages_this_run < self.page_cap_per_run and pages_this_run < self.max_pages:
            await self.rate_limiter.wait(self.state_code, tier=self.tier)
            payload = await self._fetch_search_page(
                client,
                search_option_type=search_option_type,
                search_option_sub_option=search_option_sub_option,
                row_number=row_number,
                text=text,
                search_category=search_category,
            )
            pages_this_run += 1
            if not payload:
                break

            page_new = 0
            for debtor in payload.get("debtors") or []:
                filing = self._debtor_to_filing(debtor, self.state_code)
                if filing is None:
                    continue
                key = filing["filing_number"]
                if key in seen:
                    continue
                seen.add(key)
                all_filings.append(filing)
                page_new += 1

            logger.info(
                "fl_search_page",
                profile=prof,
                category=search_category,
                row_number=row_number,
                new_filings=page_new,
                total=len(all_filings),
            )

            if save_checkpoints and search_category == "Standard":
                await save_checkpoint(self.state_code, prof, row_number)

            next_row = payload.get("nextRowNumber")
            if not next_row or next_row == row_number:
                break
            row_number = int(next_row)

        self.rate_limiter.record_success(self.state_code)

    async def _fetch_filings(self) -> list[dict]:
        seen: set[str] = set()
        all_filings: list[dict] = []

        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": get_random_user_agent()},
        ) as client:
            for opt_type, sub in self.index_profiles:
                await self._paginate_profile(
                    client,
                    seen,
                    all_filings,
                    search_option_type=opt_type,
                    search_option_sub_option=sub,
                    text="",
                    search_category="Standard",
                )

            for term in self.exact_terms:
                await self._paginate_profile(
                    client,
                    seen,
                    all_filings,
                    search_option_type="OrganizationDebtorName",
                    search_option_sub_option="FiledCompactDebtorNameList",
                    text=term,
                    search_category="Exact",
                    resume_row=0,
                    save_checkpoints=False,
                )

        logger.info("fl_fetch_complete", total=len(all_filings))
        return all_filings

    async def scrape(self) -> int:
        run = await self._start_run()
        try:
            filings = await self._fetch_filings()
            await self._enrich_filings(filings)
            count = await self._persist(filings)
            await self._finish_run(run, count)
            if self.run_consolidation:
                await run_post_scrape_pipeline(state=self.state_code)
            return count
        except Exception as exc:
            await self._fail_run(run, exc)
            raise

    async def _persist(self, filings: list[dict]) -> int:
        inserted = 0
        updated = 0
        async with get_session() as session:
            for filing_data in filings:
                stmt = select(UCCFiling).where(
                    UCCFiling.filing_number == filing_data["filing_number"],
                    UCCFiling.state == self.state_code,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if existing is None:
                    session.add(UCCFiling(**filing_data))
                    inserted += 1
                    continue
                row_updated = False
                if existing.secured_party is None and filing_data.get("secured_party"):
                    existing.secured_party = filing_data["secured_party"]
                    row_updated = True
                if existing.filing_date is None and filing_data.get("filing_date"):
                    existing.filing_date = filing_data["filing_date"]
                    row_updated = True
                if (
                    existing.collateral_description is None
                    and filing_data.get("collateral_description")
                ):
                    existing.collateral_description = filing_data["collateral_description"]
                    row_updated = True
                if row_updated:
                    updated += 1
        logger.info(
            "persist_complete",
            state=self.state_code,
            inserted=inserted,
            updated=updated,
        )
        return inserted

    def parse_response(self, html: str) -> list[dict]:
        data: Any = _safe_json_loads(html)
        if not isinstance(data, dict):
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
        payload = data.get("payload") or {}
        results: list[dict] = []
        for debtor in payload.get("debtors") or []:
            filing = self._debtor_to_filing(debtor, self.state_code)
            if filing is not None:
                results.append(filing)
        return results
