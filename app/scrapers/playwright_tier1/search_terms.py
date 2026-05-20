"""Search term rotation for Playwright Tier 1 scrapes."""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import func, select

from app.db import get_session
from app.logging import get_logger
from app.mca.seed_data import KNOWN_MCA_LENDERS
from app.models.mca_alias import MCAlias

logger = get_logger("playwright_tier1.search_terms")

# Trailing org tokens stripped before first-token extraction (NY org search).
_ORG_SUFFIX_TOKENS: frozenset[str] = frozenset(
    {
        "LLC",
        "L.L.C.",
        "INC",
        "INC.",
        "CORP",
        "CORPORATION",
        "LTD",
        "LTD.",
        "LP",
        "L.P.",
        "LLP",
        "L.L.P.",
        "LLLP",
        "CO",
        "COMPANY",
        "GROUP",
        "PARTNERS",
        "PARTNER",
        "NA",
        "N.A.",
        "PLC",
    }
)

_TRAILING_SUFFIX_RE = re.compile(
    r"\s+(?:" + "|".join(re.escape(s.rstrip(".")) for s in _ORG_SUFFIX_TOKENS) + r")\.?\s*$",
    re.IGNORECASE,
)

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
    """Count aliases tagged ``mca_funder`` (used to cap NY secured-party sweeps)."""
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


def _normalize_search_term(raw: str) -> str:
    return " ".join(raw.strip().upper().split())


def _strip_trailing_org_suffixes(name: str) -> str:
    """Remove trailing LLC / INC / CORP / LP tokens for token extraction."""
    text = _normalize_search_term(name)
    while text:
        stripped = _TRAILING_SUFFIX_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return text


def first_significant_token(name: str, *, min_len: int = 3) -> str | None:
    """First non-suffix token (e.g. YELLOWSTONE from YELLOWSTONE CAPITAL LLC)."""
    core = _strip_trailing_org_suffixes(name)
    for tok in core.split():
        clean = re.sub(r"[^A-Z0-9]", "", tok.upper())
        if len(clean) < min_len:
            continue
        if clean in _ORG_SUFFIX_TOKENS:
            continue
        return clean
    return None


def expand_secured_party_variants(
    aliases: list[str],
    *,
    variant_limit: int | None = None,
) -> list[tuple[str, str]]:
    """Expand one funder's aliases into portal search variants.

    Returns ``(match_type, term)`` pairs (match_type is ``SW``; NY uses separate
    profiles for ``BW``). Per alias: full name, then first significant token.
    Terms are deduped case-insensitively within the funder.
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    def _add(term: str, match_type: str = "SW") -> None:
        key = _normalize_search_term(term)
        if not key or key in seen:
            return
        seen.add(key)
        out.append((match_type, key))

    for alias in aliases:
        if not alias or not str(alias).strip():
            continue
        _add(alias)
        token = first_significant_token(alias)
        if token:
            _add(token)

    if variant_limit is not None and len(out) > variant_limit:
        out = out[:variant_limit]
    return out


def expand_secured_party_search_terms(
    aliases: list[str],
    *,
    variant_limit: int | None = None,
) -> list[str]:
    """Deduped uppercase terms for NY secured-party profiles (SW and BW share terms)."""
    return [term for _match, term in expand_secured_party_variants(aliases, variant_limit=variant_limit)]


async def load_mca_funder_alias_groups(*, funder_limit: int) -> list[list[str]]:
    """Group ``mca_funder`` aliases by canonical lender; up to ``funder_limit`` funders."""
    groups: dict[str, list[tuple[float, str]]] = defaultdict(list)

    async with get_session() as session:
        result = await session.execute(
            select(
                MCAlias.canonical_lender_name,
                MCAlias.alias_name,
                MCAlias.confidence,
            )
            .where(MCAlias.lender_class == "mca_funder")
            .order_by(MCAlias.confidence.desc().nullslast(), MCAlias.alias_name)
        )
        rows = result.all()

    if not rows:
        seed_by_canonical: dict[str, list[str]] = defaultdict(list)
        for entry in KNOWN_MCA_LENDERS[: max(funder_limit, 1)]:
            canon = entry["canonical_lender_name"]
            seed_by_canonical[canon].append(entry["alias_name"])
        ordered = sorted(seed_by_canonical.items(), key=lambda x: x[0])[:funder_limit]
        return [[a.upper() for a in aliases] for _, aliases in ordered]

    for canonical, alias_name, confidence in rows:
        if not alias_name or not str(alias_name).strip():
            continue
        conf = float(confidence) if confidence is not None else 0.0
        key = (canonical or alias_name).strip()
        groups[key].append((conf, alias_name.strip()))

    ranked: list[tuple[float, str, list[str]]] = []
    for canonical, entries in groups.items():
        best_conf = max(c for c, _ in entries)
        aliases = []
        seen_alias: set[str] = set()
        for _c, name in sorted(entries, key=lambda x: (-x[0], x[1])):
            upper = name.upper()
            if upper not in seen_alias:
                seen_alias.add(upper)
                aliases.append(upper)
        ranked.append((best_conf, canonical, aliases))

    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [aliases for _conf, _canon, aliases in ranked[:funder_limit]]


async def build_secured_party_variant_terms(
    *,
    funder_limit: int,
    variant_limit_per_funder: int | None = None,
    extra_terms: tuple[str, ...] = (),
) -> list[str]:
    """MCA funders (capped) → per-funder variant expansion → global dedupe."""
    funder_count = await count_mca_funder_aliases()
    effective_funder_limit = (
        min(funder_count, funder_limit) if funder_count else funder_limit
    )
    groups = await load_mca_funder_alias_groups(funder_limit=effective_funder_limit)

    terms: list[str] = []
    seen: set[str] = set()
    variant_rows = 0

    for aliases in groups:
        for term in expand_secured_party_search_terms(
            aliases, variant_limit=variant_limit_per_funder
        ):
            key = _normalize_search_term(term)
            if key and key not in seen:
                seen.add(key)
                terms.append(key)
                variant_rows += 1

    for raw in extra_terms:
        key = _normalize_search_term(raw)
        if key and key not in seen:
            seen.add(key)
            terms.append(key)

    logger.info(
        "secured_party_variants_built",
        funder_count=len(groups),
        variant_terms=variant_rows,
        total_terms=len(terms),
    )
    return terms


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
