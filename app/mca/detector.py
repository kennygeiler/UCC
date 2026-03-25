"""MCA detector — matches UCC filing secured parties against known aliases."""

import re

from sqlalchemy import select

from app.db import get_session
from app.logging import get_logger
from app.models.mca_alias import MCAlias
from app.mca.seed_data import SHELL_COMPANY_PATTERNS, MCA_COLLATERAL_KEYWORDS

logger = get_logger("mca_detector")

_SUFFIX_RE = re.compile(
    r"\s*(llc|inc|corp|corporation|ltd|lp|llp|co|company|group|partners?)\.?\s*$",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Strip legal suffixes and normalize whitespace for matching.

    Args:
        name: Company name to normalize.
    """
    cleaned = _SUFFIX_RE.sub("", name.strip())
    return " ".join(cleaned.split()).lower()


async def load_alias_map() -> dict[str, tuple[str, float]]:
    """Load all aliases from DB into a normalized lookup dict.

    Returns:
        Dict mapping normalized alias to (canonical_name, confidence).
    """
    async with get_session() as session:
        result = await session.execute(select(MCAlias))
        aliases = result.scalars().all()
    return {
        normalize_name(a.alias_name): (a.canonical_lender_name, a.confidence)
        for a in aliases
    }


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
    secured_party: str | None, collateral: str | None
) -> tuple[bool, str | None, float]:
    """Determine if a filing is MCA-related.

    Args:
        secured_party: Name of the secured party from the filing.
        collateral: Collateral description text.

    Returns:
        Tuple of (is_mca, canonical_lender_name, confidence).
    """
    if not secured_party:
        return False, None, 0.0

    alias_map = await load_alias_map()
    normalized = normalize_name(secured_party)

    # Exact alias match
    if normalized in alias_map:
        canonical, confidence = alias_map[normalized]
        return True, canonical, confidence

    # Shell company pattern match
    shell_confidence = check_shell_patterns(secured_party)
    if shell_confidence > 0:
        return True, secured_party, shell_confidence

    # Collateral keyword match (weaker signal)
    if check_collateral_keywords(collateral):
        return True, secured_party, 0.5

    return False, None, 0.0
