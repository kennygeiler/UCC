"""Search term rotation for Playwright Tier 1 scrapes."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db import get_session
from app.logging import get_logger
from app.mca.seed_data import KNOWN_MCA_LENDERS
from app.models.mca_alias import MCAlias

logger = get_logger("playwright_tier1.search_terms")

# Legacy broad-coverage terms when MCA table is empty.
_FALLBACK_TERMS: tuple[str, ...] = (
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
)


async def count_mca_funder_aliases() -> int:
    """Count aliases tagged ``mca_funder`` (used to cap MCA-term sweeps)."""
    async with get_session() as session:
        result = await session.execute(
            select(func.count())
            .select_from(MCAlias)
            .where(MCAlias.lender_class == "mca_funder")
        )
        return int(result.scalar_one())


async def load_mca_search_terms(*, limit: int = 200) -> list[str]:
    """MCA ``mca_funder`` alias names from DB, else seed list, uppercased for org search."""
    names: list[str] = []
    async with get_session() as session:
        result = await session.execute(
            select(MCAlias.alias_name)
            .where(MCAlias.lender_class == "mca_funder")
            .order_by(MCAlias.confidence.desc(), MCAlias.alias_name)
            .limit(limit)
        )
        names = [row[0] for row in result.all()]

    if not names:
        async with get_session() as session:
            result = await session.execute(
                select(MCAlias.alias_name)
                .order_by(MCAlias.confidence.desc(), MCAlias.alias_name)
                .limit(limit)
            )
            names = [row[0] for row in result.all()]

    if not names:
        names = [e["alias_name"] for e in KNOWN_MCA_LENDERS[:limit]]

    if not names:
        names = list(_FALLBACK_TERMS[:limit])

    # Organization search portals expect uppercase org names.
    return [n.upper() for n in names if n and n.strip()]


async def build_search_term_list(
    *,
    mca_limit: int,
    extra_terms: tuple[str, ...] = (),
    max_terms: int | None = None,
) -> list[str]:
    """MCA terms + env extras, deduped, capped."""
    funder_count = await count_mca_funder_aliases()
    effective_mca_limit = min(funder_count, mca_limit) if funder_count else mca_limit
    terms: list[str] = []
    seen: set[str] = set()

    for term in await load_mca_search_terms(limit=effective_mca_limit):
        key = term.strip().upper()
        if key and key not in seen:
            seen.add(key)
            terms.append(key)

    for raw in extra_terms:
        key = raw.strip().upper()
        if key and key not in seen:
            seen.add(key)
            terms.append(key)

    if max_terms is not None and len(terms) > max_terms:
        terms = terms[:max_terms]

    logger.info("search_terms_built", count=len(terms))
    return terms
