"""Roll UCC filings up to business accounts by normalized debtor + state."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.consolidation.classifier import classify_secured_party, load_alias_lender_classes
from app.consolidation.scorer import score_account_from_filings
from app.db import get_session
from app.logging import get_logger
from app.mca.detector import normalize_name
from app.models.account import BusinessAccount
from app.models.filing import UCCFiling
from app.models.lead import Lead

logger = get_logger("consolidation_rollup")


async def classify_filings(state: str, batch_size: int = 500) -> int:
    """Set ``lender_class`` on filings in *state* that lack it."""
    alias_map = await load_alias_lender_classes()
    updated = 0
    async with get_session() as session:
        result = await session.execute(
            select(UCCFiling)
            .where(UCCFiling.state == state, UCCFiling.lender_class.is_(None))
            .limit(batch_size)
        )
        filings = list(result.scalars().all())
        for filing in filings:
            filing.lender_class = classify_secured_party(
                filing.secured_party, alias_map
            )
            if filing.is_mca and filing.lender_class == "unknown":
                filing.lender_class = "mca_funder"
            updated += 1
    logger.info("classify_filings_complete", state=state, updated=updated)
    return updated


async def rollup_accounts(state: str) -> int:
    """Create/update ``business_accounts`` and link filings for *state*."""
    alias_map = await load_alias_lender_classes()
    async with get_session() as session:
        debtor_keys = await session.execute(
            select(
                UCCFiling.debtor_name,
                func.min(UCCFiling.id).label("sample_id"),
            )
            .where(UCCFiling.state == state)
            .group_by(UCCFiling.debtor_name)
        )
        groups = debtor_keys.all()

    accounts_touched = 0
    for debtor_name, _sample_id in groups:
        key = normalize_name(debtor_name)
        async with get_session() as session:
            result = await session.execute(
                select(UCCFiling).where(
                    UCCFiling.state == state,
                    UCCFiling.debtor_name == debtor_name,
                )
            )
            filings = list(result.scalars().all())
            if not filings:
                continue

            account = (
                await session.execute(
                    select(BusinessAccount).where(
                        BusinessAccount.debtor_name_normalized == key,
                        BusinessAccount.state == state,
                    )
                )
            ).scalar_one_or_none()

            if account is None:
                account = BusinessAccount(
                    debtor_name_normalized=key,
                    state=state,
                    display_name=debtor_name,
                )
                session.add(account)
                await session.flush()

            lead_by_filing: dict[int, Lead] = {}
            fids = [f.id for f in filings]
            if fids:
                lead_rows = await session.execute(
                    select(Lead).where(Lead.source_filing_id.in_(fids))
                )
                for lead in lead_rows.scalars().all():
                    if lead.source_filing_id:
                        lead_by_filing[lead.source_filing_id] = lead

            filing_dicts = []
            for f in filings:
                if f.lender_class is None:
                    f.lender_class = classify_secured_party(
                        f.secured_party, alias_map
                    )
                f.account_id = account.id
                lead = lead_by_filing.get(f.id)
                filing_dicts.append(
                    {
                        "lender_class": f.lender_class,
                        "filing_date": f.filing_date,
                        "collateral_description": f.collateral_description,
                        "is_mca": f.is_mca,
                        "secured_party": f.secured_party,
                        "mca_match_type": lead.mca_match_type if lead else None,
                        "mca_match_confidence": lead.mca_match_confidence if lead else None,
                    }
                )

            scored = score_account_from_filings(filing_dicts)
            account.display_name = debtor_name
            account.consolidation_score = scored["consolidation_score"]
            account.consolidation_tier = scored["consolidation_tier"]
            account.score_components = scored["score_components"]
            account.mca_funder_count = scored["mca_funder_count"]
            account.material_ucc_count = scored["material_ucc_count"]
            account.days_since_last_filing = scored["days_since_last_filing"]
            account.last_event_at = scored["last_event_at"]
            account.last_scored_at = datetime.now(timezone.utc)
            accounts_touched += 1

    logger.info("rollup_accounts_complete", state=state, accounts=accounts_touched)
    return accounts_touched


async def rescore_accounts(state: str) -> int:
    """Recompute scores for existing accounts without re-linking filings."""
    rescored = 0
    async with get_session() as session:
        accounts = (
            await session.execute(
                select(BusinessAccount).where(BusinessAccount.state == state)
            )
        ).scalars().all()

    for account in accounts:
        async with get_session() as session:
            acc = await session.get(BusinessAccount, account.id)
            if acc is None:
                continue
            result = await session.execute(
                select(UCCFiling).where(UCCFiling.account_id == acc.id)
            )
            filings = list(result.scalars().all())
            if not filings:
                continue
            fids = [f.id for f in filings]
            lead_rows = await session.execute(
                select(Lead).where(Lead.source_filing_id.in_(fids))
            )
            lead_by_filing = {
                l.source_filing_id: l
                for l in lead_rows.scalars().all()
                if l.source_filing_id
            }
            filing_dicts = [
                {
                    "lender_class": f.lender_class,
                    "filing_date": f.filing_date,
                    "collateral_description": f.collateral_description,
                    "is_mca": f.is_mca,
                    "secured_party": f.secured_party,
                    "mca_match_type": lead_by_filing.get(f.id).mca_match_type
                    if f.id in lead_by_filing
                    else None,
                    "mca_match_confidence": lead_by_filing.get(f.id).mca_match_confidence
                    if f.id in lead_by_filing
                    else None,
                }
                for f in filings
            ]
            scored = score_account_from_filings(filing_dicts)
            acc.consolidation_score = scored["consolidation_score"]
            acc.consolidation_tier = scored["consolidation_tier"]
            acc.score_components = scored["score_components"]
            acc.mca_funder_count = scored["mca_funder_count"]
            acc.material_ucc_count = scored["material_ucc_count"]
            acc.days_since_last_filing = scored["days_since_last_filing"]
            acc.last_event_at = scored["last_event_at"]
            acc.last_scored_at = datetime.now(timezone.utc)
            rescored += 1

    logger.info("rescore_accounts_complete", state=state, rescored=rescored)
    return rescored
