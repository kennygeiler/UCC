"""MCA detector — matches UCC filing secured parties against known aliases.

Fuzzy matching scans normalized alias keys in O(n) per secured party. Acceptable
while ``mca_aliases`` row counts stay in the low thousands; if n grows large,
add batching or an indexed lookup strategy.
"""

from rapidfuzz import fuzz, process
from sqlalchemy import select

from app.config import Settings
from app.db import get_session
from app.logging import get_logger
from app.mca.lender_guard import (
    get_blocked_lender_classes,
    has_significant_token_overlap,
    should_skip_mca_alias_matching,
)
from app.mca.names import normalize_name
from app.mca.seed_data import SHELL_COMPANY_PATTERNS, MCA_COLLATERAL_KEYWORDS
from app.models.mca_alias import MCAlias

logger = get_logger("mca_detector")

async def load_alias_map() -> dict[str, tuple[str, float]]:
    """Load all aliases from DB into a normalized lookup dict.

    Returns:
        Dict mapping normalized alias to (canonical_name, confidence).
    """
    async with get_session() as session:
        result = await session.execute(select(MCAlias))
        aliases = result.scalars().all()
    return {
        normalize_name(a.alias_name): (a.canonical_lender_name, a.confidence or 0.9)
        for a in aliases
    }


def _fuzzy_match_alias(
    normalized: str,
    alias_map: dict[str, tuple[str, float]],
    *,
    settings: Settings | None = None,
) -> tuple[str, float] | None:
    """Match secured party to the closest normalized alias key using WRatio.

    Returns:
        (canonical_lender, confidence) or None if below cutoff or too short.
    """
    settings = settings or Settings()
    if len(normalized) < settings.MCA_FUZZY_MIN_ALIAS_LEN:
        return None
    if not alias_map:
        return None

    keys = list(alias_map.keys())
    result = process.extractOne(
        normalized,
        keys,
        scorer=fuzz.WRatio,
        score_cutoff=settings.MCA_FUZZY_SCORE_CUTOFF,
    )
    if result is None:
        return None
    match_key, score, _ = result
    if settings.MCA_FUZZY_REQUIRE_TOKEN_OVERLAP and not has_significant_token_overlap(
        normalized, match_key
    ):
        return None
    canonical, base_conf = alias_map[match_key]
    adjusted = (base_conf or 0.9) * (score / 100.0)
    return canonical, min(adjusted, 0.99)


def check_collateral_keywords(collateral: str | None) -> bool:
    """Check if collateral description contains MCA-indicative keywords.

    Args:
        collateral: Collateral description text from UCC filing.
    """
    if not collateral:
        return False
    lower = collateral.lower()
    return any(kw in lower for kw in MCA_COLLATERAL_KEYWORDS)


def check_shell_patterns(name: str) -> float:
    """Check if a name matches common shell company patterns.

    Args:
        name: Secured party name to check.

    Returns:
        Confidence score (0.7 if matched, 0.0 if not).
    """
    lower = name.lower()
    for pattern in SHELL_COMPANY_PATTERNS:
        if pattern in lower:
            return 0.7
    return 0.0


async def detect_mca(
    secured_party: str | None,
    collateral: str | None,
    *,
    alias_map: dict[str, tuple[str, float]] | None = None,
    alias_class_map: dict[str, str] | None = None,
) -> tuple[bool, str | None, float, str | None]:
    """Determine if a filing is MCA-related.

    Precedence: lender guard → exact normalized alias → fuzzy alias → shell →
    collateral keywords.

    Args:
        secured_party: Name of the secured party from the filing.
        collateral: Collateral description text.
        alias_map: Optional preloaded map (normalized key → canonical, conf).
            When None, loads from the database.
        alias_class_map: Optional normalized alias → lender_class for guard.

    Returns:
        Tuple of (is_mca, canonical_lender_name, confidence, match_type).
        ``match_type`` is one of exact|fuzzy|shell|collateral when MCA, else None.
    """
    if not secured_party:
        return False, None, 0.0, None

    settings = Settings()
    if alias_class_map is None:
        if alias_map is not None:
            alias_class_map = {}
        else:
            from app.consolidation.classifier import load_alias_lender_classes

            alias_class_map = await load_alias_lender_classes()
    blocked = get_blocked_lender_classes(settings)
    skip, lender_class = should_skip_mca_alias_matching(
        secured_party,
        alias_class_map=alias_class_map,
        blocked_classes=blocked,
    )
    if skip:
        logger.debug(
            "mca_match_skipped",
            lender_class=lender_class,
            secured_party=secured_party[:80],
        )
        return False, None, 0.0, None

    if alias_map is None:
        alias_map = await load_alias_map()

    normalized = normalize_name(secured_party)

    if normalized in alias_map:
        canonical, confidence = alias_map[normalized]
        return True, canonical, confidence or 0.9, "exact"

    fuzzy_hit = _fuzzy_match_alias(normalized, alias_map, settings=settings)
    if fuzzy_hit is not None:
        canonical, confidence = fuzzy_hit
        return True, canonical, confidence, "fuzzy"

    shell_confidence = check_shell_patterns(secured_party)
    if shell_confidence > 0:
        return True, secured_party, shell_confidence, "shell"

    if check_collateral_keywords(collateral):
        return True, secured_party, 0.5, "collateral"

    return False, None, 0.0, None
