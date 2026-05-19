"""MCA name normalization — shared by detector and consolidation classifier."""

import re

_SUFFIX_RE = re.compile(
    r"\s*(llc|inc|corp|corporation|ltd|lp|llp|co|company|group|partners?)\.?\s*$",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Strip legal suffixes and normalize whitespace for matching."""
    cleaned = _SUFFIX_RE.sub("", name.strip())
    return " ".join(cleaned.split()).lower()
