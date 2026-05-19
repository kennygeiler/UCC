"""Consolidation score 0–100 and tier assignment per business account."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.consolidation.classifier import MATERIAL_CLASSES, NOISE_CLASSES
from app.mca.detector import check_collateral_keywords

TIER_PRIORITY = "priority"
TIER_WORK = "work"
TIER_MONITOR = "monitor"
TIER_SUPPRESS = "suppress"

PRIORITY_MIN = 70.0
WORK_MIN = 50.0
MONITOR_MIN = 30.0


def _days_since(dt: datetime | None, now: datetime) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def _recency_points(days: int | None) -> float:
    """Recency component (max 25)."""
    if days is None:
        return 0.0
    if days <= 30:
        return 25.0
    if days <= 90:
        return 18.0
    if days <= 180:
        return 10.0
    if days <= 365:
        return 4.0
    return 0.0


def _mca_stack_points(mca_funder_count: int) -> float:
    """MCA stack component (max 35)."""
    if mca_funder_count <= 0:
        return 0.0
    if mca_funder_count == 1:
        return 12.0
    if mca_funder_count == 2:
        return 24.0
    return 35.0


def _velocity_points(filings_last_90d: int) -> float:
    """Filing velocity component (max 15)."""
    if filings_last_90d <= 0:
        return 0.0
    if filings_last_90d == 1:
        return 5.0
    if filings_last_90d == 2:
        return 10.0
    return 15.0


def _material_stack_points(material_count: int) -> float:
    """Material lender stack component (max 15)."""
    if material_count <= 0:
        return 0.0
    if material_count == 1:
        return 6.0
    if material_count == 2:
        return 11.0
    return 15.0


def _collateral_points(has_collateral: bool) -> float:
    return 10.0 if has_collateral else 0.0


def _noise_penalty(noise_count: int, total_filings: int, *, mca_funder_count: int) -> float:
    if total_filings <= 0 or noise_count <= 0:
        return 0.0
    ratio = noise_count / total_filings
    cap = 8.0 if mca_funder_count >= 1 else 15.0
    return min(cap, ratio * 12.0)


def _trust_penalty(fuzzy_matches: int, low_confidence: int) -> float:
    return min(10.0, fuzzy_matches * 4.0 + low_confidence * 2.0)


def assign_consolidation_tier(score: float) -> str:
    if score >= PRIORITY_MIN:
        return TIER_PRIORITY
    if score >= WORK_MIN:
        return TIER_WORK
    if score >= MONITOR_MIN:
        return TIER_MONITOR
    return TIER_SUPPRESS


def score_account_from_filings(
    filings: list[dict],
    *,
    now: datetime | None = None,
) -> dict:
    """Compute consolidation score from aggregated filing stats.

    Each filing dict expects keys: ``lender_class``, ``filing_date``,
    ``collateral_description``, ``is_mca``, ``mca_match_type``,
    ``mca_match_confidence``.
    """
    now = now or datetime.now(timezone.utc)
    total = len(filings)
    mca_funders: set[str] = set()
    material_count = 0
    noise_count = 0
    fuzzy_matches = 0
    low_confidence = 0
    has_collateral = False
    dates: list[datetime] = []
    filings_last_90d = 0
    cutoff_90 = now - timedelta(days=90)

    for f in filings:
        cls = f.get("lender_class") or "unknown"
        if cls == "mca_funder" or f.get("is_mca"):
            sp = f.get("secured_party") or ""
            mca_funders.add(sp[:80] if sp else "mca")
        if cls in MATERIAL_CLASSES:
            material_count += 1
        if cls in NOISE_CLASSES:
            noise_count += 1
        if f.get("mca_match_type") == "fuzzy":
            fuzzy_matches += 1
        conf = f.get("mca_match_confidence")
        if conf is not None and conf < 0.85:
            low_confidence += 1
        collateral = f.get("collateral_description")
        if collateral and check_collateral_keywords(collateral):
            has_collateral = True
        fd = f.get("filing_date")
        if fd:
            if fd.tzinfo is None:
                fd = fd.replace(tzinfo=timezone.utc)
            dates.append(fd)
            if fd >= cutoff_90:
                filings_last_90d += 1

    mca_funder_count = len(mca_funders) if mca_funders else sum(
        1 for f in filings if f.get("is_mca") or f.get("lender_class") == "mca_funder"
    )
    last_date = max(dates) if dates else None
    days_since = _days_since(last_date, now)

    components = {
        "mca_stack": _mca_stack_points(mca_funder_count),
        "recency": _recency_points(days_since),
        "velocity": _velocity_points(filings_last_90d),
        "material_stack": _material_stack_points(material_count),
        "collateral": _collateral_points(has_collateral),
    }
    raw = sum(components.values())
    noise_pen = _noise_penalty(noise_count, total, mca_funder_count=mca_funder_count)
    trust_pen = _trust_penalty(fuzzy_matches, low_confidence)
    components["noise_penalty"] = -round(noise_pen, 2)
    components["match_trust_penalty"] = -round(trust_pen, 2)
    score = round(max(0.0, min(100.0, raw - noise_pen - trust_pen)), 2)

    # Priority bump for stacked or recent single-MCA accounts
    if mca_funder_count >= 2 and score < PRIORITY_MIN:
        score = max(score, PRIORITY_MIN)
    elif (
        mca_funder_count >= 1
        and days_since is not None
        and days_since <= 60
        and score < WORK_MIN
    ):
        score = max(score, WORK_MIN)

    tier = assign_consolidation_tier(score)

    return {
        "consolidation_score": score,
        "consolidation_tier": tier,
        "score_components": components,
        "mca_funder_count": mca_funder_count,
        "material_ucc_count": material_count,
        "days_since_last_filing": days_since,
        "last_event_at": last_date,
    }
