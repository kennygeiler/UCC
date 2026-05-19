"""Secured-party → lender_class classification for consolidation scoring."""

from __future__ import annotations

import re

from sqlalchemy import select

from app.db import get_session
from app.mca.names import normalize_name
from app.models.mca_alias import MCAlias

LENDER_CLASSES = (
    "mca_funder",
    "bank",
    "registered_agent",
    "government",
    "insurance",
    "alternative_lender",
    "unknown",
)

MATERIAL_CLASSES = frozenset({"mca_funder", "bank", "alternative_lender"})
NOISE_CLASSES = frozenset({"registered_agent", "government"})

_BANK_PATTERNS = re.compile(
    r"\b(chase|bank of america|wells fargo|citibank|pnc bank|"
    r"us bank|truist|capital one|td bank|fifth third|regions bank)\b",
    re.IGNORECASE,
)
_REGISTERED_AGENT_PATTERNS = re.compile(
    r"\b(csc|ct corporation|national registered agents|"
    r"corporation service company|registered agent)\b",
    re.IGNORECASE,
)
from app.mca.lender_guard import NON_MCA_SECURED_PARTY_PATTERNS

_GOVERNMENT_PATTERNS = NON_MCA_SECURED_PARTY_PATTERNS
_INSURANCE_PATTERNS = re.compile(
    r"\b(insurance|assurance|indemnity|underwriters)\b",
    re.IGNORECASE,
)
_ALT_LENDER_PATTERNS = re.compile(
    r"\b(kabbage|lendingclub|fundation|forward financing)\b",
    re.IGNORECASE,
)

_alias_class_cache: dict[str, str] | None = None


async def load_alias_lender_classes() -> dict[str, str]:
    """Normalized alias name → lender_class from ``mca_aliases``."""
    global _alias_class_cache
    if _alias_class_cache is not None:
        return _alias_class_cache
    async with get_session() as session:
        rows = (await session.execute(select(MCAlias))).scalars().all()
    _alias_class_cache = {
        normalize_name(row.alias_name): row.lender_class or "mca_funder"
        for row in rows
    }
    return _alias_class_cache


def reset_alias_class_cache() -> None:
    """Clear cached alias map (for tests)."""
    global _alias_class_cache
    _alias_class_cache = None


def classify_secured_party_name(
    name: str,
    alias_map: dict[str, str] | None = None,
) -> str:
    """Classify a single secured-party name string."""
    if not name or not name.strip():
        return "unknown"
    normalized = normalize_name(name)
    if alias_map and normalized in alias_map:
        return alias_map[normalized]
    if _BANK_PATTERNS.search(name):
        return "bank"
    if _REGISTERED_AGENT_PATTERNS.search(name):
        return "registered_agent"
    if _GOVERNMENT_PATTERNS.search(name):
        return "government"
    if _INSURANCE_PATTERNS.search(name):
        return "insurance"
    if _ALT_LENDER_PATTERNS.search(name):
        return "alternative_lender"
    if any(kw in normalized for kw in ("capital", "funding", "advance", "merchant")):
        return "mca_funder"
    return "unknown"


def classify_secured_party(
    secured_party: str | None,
    alias_map: dict[str, str] | None = None,
) -> str:
    """Classify semicolon-separated secured parties; prefer strongest signal."""
    if not secured_party:
        return "unknown"
    parts = [p.strip() for p in secured_party.split(";") if p.strip()]
    if not parts:
        return "unknown"
    classes = [classify_secured_party_name(p, alias_map) for p in parts]
    priority = [
        "mca_funder",
        "alternative_lender",
        "bank",
        "insurance",
        "registered_agent",
        "government",
        "unknown",
    ]
    for cls in priority:
        if cls in classes:
            return cls
    return "unknown"
