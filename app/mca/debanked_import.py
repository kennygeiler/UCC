"""Import MCA UCC aliases from deBanked's public alias table."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.consolidation.classifier import reset_alias_class_cache
from app.dashboard.queries import upsert_mca_alias
from app.db import get_session
from app.logging import get_logger
from app.mca.names import normalize_name

logger = get_logger("debanked_import")

DEBANKED_MCA_URL = (
    "https://debanked.com/merchant-cash-advance-resource/merchant-cash-advance-ucc/"
)
DEFAULT_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "debanked_mca_aliases.csv"

# Companies to omit entirely (non-MCA / payment processors).
_SKIP_COMPANIES = frozenset(
    {
        "first data",
        "lending club",
    }
)

# Canonical names that are registered agents — import as registered_agent, not mca_funder.
_REGISTERED_AGENT_MARKERS = (
    "corporation service company",
    "ct corporation",
    "corp service co",
    "cht d company",
    "csc, as representative",
    "financial agent services",
    "secured lender solutions",
)

_CONTINUED_RE = re.compile(r"\s*\(continued\)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DebankedImportStats:
    """Counts from one import run."""

    added: int = 0
    updated: int = 0
    skipped_duplicate: int = 0
    skipped_excluded: int = 0
    skipped_empty: int = 0
    registered_agent: int = 0


def _normalize_company(name: str) -> str:
    return _CONTINUED_RE.sub("", name).strip()


def _company_lender_class(company_name: str) -> str | None:
    """Return lender_class, or None if the company should be skipped entirely."""
    normalized_company = _normalize_company(company_name)
    key = normalize_name(normalized_company)
    raw = normalized_company.lower()
    if key in _SKIP_COMPANIES or raw in _SKIP_COMPANIES:
        return None
    for marker in _REGISTERED_AGENT_MARKERS:
        if marker in key or marker in raw:
            return "registered_agent"
    return "mca_funder"


def parse_debanked_table_rows(
    rows: list[tuple[str, ...]],
) -> list[tuple[str, str, str]]:
    """Parse table body rows into (canonical, alias, lender_class) triples."""
    out: list[tuple[str, str, str]] = []
    seen_aliases: set[str] = set()

    for row in rows:
        if not row or not row[0].strip():
            continue
        company = _normalize_company(row[0])
        lender_class = _company_lender_class(company)
        if lender_class is None:
            continue
        # Columns after company: phone + up to 5 aliases (HTML/CSV layouts vary).
        alias_cells = [c.strip() for c in row[1:] if c and c.strip()]
        # Drop phone-like first cell when present (digits and dashes only).
        if alias_cells and re.fullmatch(r"[\d\-\(\)\s\.]+", alias_cells[0]):
            alias_cells = alias_cells[1:]
        if not alias_cells:
            alias_cells = [company]
        for alias in alias_cells:
            norm = normalize_name(alias)
            if not norm or norm in seen_aliases:
                continue
            seen_aliases.add(norm)
            out.append((company, alias, lender_class))
    return out


def parse_debanked_html(html: str) -> list[tuple[str, str, str]]:
    """Extract alias rows from deBanked MCA UCC page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    body_rows: list[tuple[str, ...]] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not cells or cells[0].lower() in ("company name", "company"):
            continue
        body_rows.append(tuple(cells))
    return parse_debanked_table_rows(body_rows)


def parse_debanked_csv(csv_path: Path) -> list[tuple[str, str, str]]:
    """Read bundled CSV: company_name, alias_1..alias_5."""
    rows: list[tuple[str, ...]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            if row[0].lower() in ("company_name", "company name"):
                continue
            rows.append(tuple(cell.strip() for cell in row))
    return parse_debanked_table_rows(rows)


async def fetch_debanked_html(*, timeout: float = 30.0) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(DEBANKED_MCA_URL)
        resp.raise_for_status()
        return resp.text


async def import_debanked_mca_aliases(
    *,
    use_live_fetch: bool = False,
    csv_path: Path | None = None,
) -> DebankedImportStats:
    """Upsert deBanked MCA aliases into ``mca_aliases`` (idempotent)."""
    from sqlalchemy import select

    from app.models.mca_alias import MCAlias

    if use_live_fetch:
        html = await fetch_debanked_html()
        triples = parse_debanked_html(html)
    else:
        path = csv_path or DEFAULT_CSV_PATH
        triples = parse_debanked_csv(path)

    added = updated = skipped_empty = registered_agent = 0
    async with get_session() as session:
        existing_rows = (
            await session.execute(select(MCAlias.alias_name))
        ).all()
        existing_names = {row[0] for row in existing_rows}

    for company, alias, lender_class in triples:
        if not alias.strip():
            skipped_empty += 1
            continue
        if lender_class == "registered_agent":
            registered_agent += 1

        was_present = alias.strip() in existing_names
        await upsert_mca_alias(
            alias_name=alias,
            canonical_lender_name=company,
            lender_class=lender_class,
            consolidation_weight=1.0,
            confidence=1.0,
            source="debanked",
        )
        if was_present:
            updated += 1
        else:
            added += 1
            existing_names.add(alias.strip())

    reset_alias_class_cache()
    stats = DebankedImportStats(
        added=added,
        updated=updated,
        registered_agent=registered_agent,
        skipped_empty=skipped_empty,
    )
    logger.info("debanked_import_complete", **stats.__dict__)
    return stats
