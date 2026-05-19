"""MCA funder account CSV export — dashboard download and CLI."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timezone

from sqlalchemy import or_, select

from app.dashboard.queries import (
    CONSOLIDATION_TIERS,
    _ilike,
    _mca_lead_account_filter,
    get_last_fl_scraper_finished_at,
)
from app.db import get_session
from app.models.account import BusinessAccount
from app.models.filing import UCCFiling

MCA_EXPORT_COLUMNS: tuple[str, ...] = (
    "account_id",
    "display_name",
    "state",
    "debtor_name_normalized",
    "consolidation_tier",
    "consolidation_score",
    "mca_funder_count",
    "material_ucc_count",
    "days_since_last_filing",
    "last_event_at",
    "mca_funders",
    "filing_count",
    "top_secured_parties",
    "phone",
    "email",
    "owner_name",
    "estimated_revenue",
)

ENRICHMENT_PLACEHOLDER_COLUMNS = ("phone", "email", "owner_name", "estimated_revenue")


def _is_mca_filing(filing: UCCFiling) -> bool:
    return filing.lender_class == "mca_funder" or filing.is_mca is True


def _distinct_secured_parties(
    filings: Sequence[UCCFiling],
    *,
    mca_only: bool = False,
    limit: int | None = None,
) -> list[str]:
    """Distinct non-empty secured party names, stable sort."""
    seen: set[str] = set()
    names: list[str] = []
    for filing in filings:
        if mca_only and not _is_mca_filing(filing):
            continue
        sp = (filing.secured_party or "").strip()
        if not sp:
            continue
        key = sp[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(sp)
    names.sort(key=str.lower)
    if limit is not None:
        return names[:limit]
    return names


def aggregate_filings_for_export(filings: Sequence[UCCFiling]) -> dict[str, str | int]:
    """Derive filing aggregates for one account's linked filings."""
    mca_names = _distinct_secured_parties(filings, mca_only=True)
    top_parties = _distinct_secured_parties(filings, mca_only=False, limit=3)
    return {
        "mca_funders": "; ".join(mca_names),
        "filing_count": len(filings),
        "top_secured_parties": "; ".join(top_parties),
    }


def account_to_csv_row(account: BusinessAccount, filing_stats: dict[str, str | int]) -> dict[str, str | int | float | None]:
    """Map account + aggregates to a flat CSV row dict."""
    last_event = ""
    if account.last_event_at:
        last_event = account.last_event_at.isoformat()
    row: dict[str, str | int | float | None] = {
        "account_id": account.id,
        "display_name": account.display_name,
        "state": account.state,
        "debtor_name_normalized": account.debtor_name_normalized,
        "consolidation_tier": account.consolidation_tier or "",
        "consolidation_score": account.consolidation_score,
        "mca_funder_count": account.mca_funder_count,
        "material_ucc_count": account.material_ucc_count,
        "days_since_last_filing": account.days_since_last_filing,
        "last_event_at": last_event,
        "mca_funders": filing_stats["mca_funders"],
        "filing_count": filing_stats["filing_count"],
        "top_secured_parties": filing_stats["top_secured_parties"],
    }
    for col in ENRICHMENT_PLACEHOLDER_COLUMNS:
        row[col] = ""
    return row


def mca_export_filename(*, state: str, on_date: date | None = None) -> str:
    """Build download filename, e.g. ``ucc-mca-leads-FL-2026-05-19.csv``."""
    st = (state or "FL").strip().upper() or "FL"
    day = on_date or datetime.now(timezone.utc).date()
    return f"ucc-mca-leads-{st}-{day.isoformat()}.csv"


def rows_to_csv_text(rows: Iterable[dict[str, object]], *, columns: Sequence[str] = MCA_EXPORT_COLUMNS) -> str:
    """Serialize rows to UTF-8 CSV with proper escaping."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: _csv_cell(row.get(col)) for col in columns})
    return buf.getvalue()


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(value)
    return str(value)


async def export_mca_accounts_csv_rows(
    *,
    state: str | None = None,
    debtor_name: str | None = None,
    tier: str | None = None,
    consolidation_tier: str | None = None,
    since_last_run: bool = False,
) -> list[dict[str, str | int | float | None]]:
    """Fetch MCA lead accounts and filing aggregates for CSV export."""
    conditions = [_mca_lead_account_filter()]
    if state and state.strip():
        conditions.append(BusinessAccount.state == state.strip().upper())
    debtor_filt = _ilike(BusinessAccount.display_name, debtor_name)
    if debtor_filt is not None:
        conditions.append(debtor_filt)
    tier_val = (tier or consolidation_tier or "").strip().lower()
    if tier_val in CONSOLIDATION_TIERS:
        conditions.append(BusinessAccount.consolidation_tier == tier_val)

    last_run = await get_last_fl_scraper_finished_at() if since_last_run else None
    if last_run is not None:
        conditions.append(
            or_(
                BusinessAccount.last_event_at > last_run,
                BusinessAccount.updated_at > last_run,
            )
        )

    async with get_session() as session:
        data_stmt = select(BusinessAccount).order_by(
            BusinessAccount.consolidation_score.desc().nulls_last(),
            BusinessAccount.mca_funder_count.desc(),
            BusinessAccount.id.desc(),
        )
        for cond in conditions:
            data_stmt = data_stmt.where(cond)
        accounts = list((await session.execute(data_stmt)).scalars().all())
        if not accounts:
            return []

        account_ids = [a.id for a in accounts]
        filings_result = await session.execute(
            select(UCCFiling)
            .where(UCCFiling.account_id.in_(account_ids))
            .order_by(UCCFiling.account_id, UCCFiling.id)
        )
        filings_by_account: dict[int, list[UCCFiling]] = {aid: [] for aid in account_ids}
        for filing in filings_result.scalars().all():
            if filing.account_id is not None:
                filings_by_account.setdefault(filing.account_id, []).append(filing)

    rows: list[dict[str, str | int | float | None]] = []
    for account in accounts:
        filings = filings_by_account.get(account.id, [])
        stats = aggregate_filings_for_export(filings)
        rows.append(account_to_csv_row(account, stats))
    return rows


async def build_mca_accounts_csv(
    *,
    state: str | None = None,
    debtor_name: str | None = None,
    tier: str | None = None,
    consolidation_tier: str | None = None,
    since_last_run: bool = False,
) -> str:
    """Full CSV document for MCA funder accounts matching filters."""
    rows = await export_mca_accounts_csv_rows(
        state=state,
        debtor_name=debtor_name,
        tier=tier,
        consolidation_tier=consolidation_tier,
        since_last_run=since_last_run,
    )
    return rows_to_csv_text(rows)
