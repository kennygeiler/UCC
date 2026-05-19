"""Shared MCA matching guards — single source for classifier and detector.

Blocks fuzzy/alias MCA matching for non-lender secured parties (government,
registered agents, banks, etc.) and obvious non-MCA name patterns (SBA, CSC).
"""

from __future__ import annotations

import re

# Obvious non-MCA secured parties — checked before fuzzy alias matching.
NON_MCA_SECURED_PARTY_PATTERNS = re.compile(
    r"\b("
    r"sba|small\s+business\s+administration|"
    r"u\.?\s*s\.?\s*small\s+business|"
    r"corporation\s+service\s+company|csc\s+global|"
    r"ct\s+corporation|national\s+registered\s+agents|"
    r"internal\s+revenue\s+service|\birs\b|"
    r"department\s+of\s+(revenue|treasury)|"
    r"secretary\s+of\s+state|"
    r"county\s+of|city\s+of|state\s+of\s+\w+"
    r")\b",
    re.IGNORECASE,
)

# Tokens ignored when requiring significant overlap for fuzzy alias matches.
_FUZZY_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "of",
        "for",
        "llc",
        "inc",
        "corp",
        "company",
        "group",
        "capital",
        "funding",
        "business",
        "services",
        "national",
        "american",
        "global",
        "financial",
    }
)


def get_blocked_lender_classes(settings) -> frozenset[str]:
    """Parse ``MCA_BLOCKED_LENDER_CLASSES`` from settings."""
    raw = getattr(settings, "MCA_BLOCKED_LENDER_CLASSES", "") or ""
    if not raw.strip():
        return frozenset({"government", "registered_agent", "insurance", "bank"})
    return frozenset(c.strip() for c in raw.split(",") if c.strip())


def is_non_mca_secured_party_pattern(name: str) -> bool:
    """True when secured-party text matches known non-MCA patterns (SBA, CSC, etc.)."""
    if not name or not name.strip():
        return False
    return bool(NON_MCA_SECURED_PARTY_PATTERNS.search(name))


def is_mca_matching_blocked(
    lender_class: str,
    *,
    blocked_classes: frozenset[str] | None = None,
) -> bool:
    """True when alias/fuzzy MCA matching must not run for this lender class."""
    if blocked_classes is None:
        blocked_classes = frozenset(
            {"government", "registered_agent", "insurance", "bank"}
        )
    return lender_class in blocked_classes


def significant_tokens(text: str, *, min_len: int = 4) -> set[str]:
    """Extract significant tokens from normalized secured-party text."""
    return {
        tok
        for tok in text.split()
        if len(tok) >= min_len and tok not in _FUZZY_STOPWORDS
    }


def has_significant_token_overlap(normalized: str, alias_key: str) -> bool:
    """Require at least one non-stopword token overlap for fuzzy acceptance."""
    a = significant_tokens(normalized)
    b = significant_tokens(alias_key)
    if not a or not b:
        return False
    return bool(a & b)


def should_skip_mca_alias_matching(
    secured_party: str | None,
    *,
    alias_class_map: dict[str, str] | None = None,
    blocked_classes: frozenset[str] | None = None,
) -> tuple[bool, str]:
    """Return (skip, lender_class) when alias/fuzzy/shell/collateral MCA paths must not run."""
    if not secured_party or not secured_party.strip():
        return True, "unknown"

    if is_non_mca_secured_party_pattern(secured_party):
        return True, "government"

    from app.consolidation.classifier import (
        classify_secured_party,
        classify_secured_party_name,
    )

    lender_class = classify_secured_party(secured_party, alias_class_map)
    if is_mca_matching_blocked(lender_class, blocked_classes=blocked_classes):
        return True, lender_class

    # Per-party pattern check for semicolon-separated lists
    for part in (p.strip() for p in secured_party.split(";") if p.strip()):
        if is_non_mca_secured_party_pattern(part):
            return True, "government"
        part_class = classify_secured_party_name(part, alias_class_map)
        if is_mca_matching_blocked(part_class, blocked_classes=blocked_classes):
            return True, part_class

    return False, lender_class
