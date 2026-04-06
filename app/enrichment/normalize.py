"""Map vendor-specific enrichment JSON to canonical lead fields."""

from typing import Any


def normalize_vendor_response(source: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a vendor API JSON body to canonical enrichment keys.

    Canonical keys: ``phone``, ``email``, ``owner_name``, ``estimated_revenue``.
    Missing values are ``None``.

    Args:
        source: One of ``pdl``, ``apollo``, ``opencorporates``.
        raw: Parsed JSON from the vendor.

    Returns:
        Flat dict suitable for ``Lead`` update and cache storage.
    """
    if source == "pdl":
        return _normalize_pdl(raw)
    if source == "apollo":
        return _normalize_apollo(raw)
    if source == "opencorporates":
        return _normalize_opencorporates(raw)
    return {
        "phone": None,
        "email": None,
        "owner_name": None,
        "estimated_revenue": None,
    }


def _normalize_pdl(raw: dict[str, Any]) -> dict[str, Any]:
    phone = raw.get("phone") or raw.get("mobile_phone")
    email = raw.get("email")
    owner = raw.get("name") or raw.get("linkedin_url")
    revenue = raw.get("inferred_revenue") or raw.get("employee_count")
    est: float | None
    if isinstance(revenue, (int, float)):
        est = float(revenue)
    else:
        est = None
    return {
        "phone": str(phone).strip() if phone else None,
        "email": str(email).strip() if email else None,
        "owner_name": str(owner).strip() if owner else None,
        "estimated_revenue": est,
    }


def _normalize_apollo(raw: dict[str, Any]) -> dict[str, Any]:
    org = raw.get("organization") if isinstance(raw.get("organization"), dict) else raw
    if not isinstance(org, dict):
        org = {}
    phone = org.get("primary_phone", {}).get("number") if isinstance(org.get("primary_phone"), dict) else org.get("phone")
    email = org.get("email")
    owner = org.get("name")
    rev = org.get("estimated_annual_revenue") or org.get("annual_revenue")
    est: float | None
    if isinstance(rev, (int, float)):
        est = float(rev)
    else:
        est = None
    return {
        "phone": str(phone).strip() if phone else None,
        "email": str(email).strip() if email else None,
        "owner_name": str(owner).strip() if owner else None,
        "estimated_revenue": est,
    }


def _normalize_opencorporates(raw: dict[str, Any]) -> dict[str, Any]:
    companies = raw.get("results", {}).get("companies") if isinstance(raw.get("results"), dict) else None
    first: dict[str, Any] = {}
    if isinstance(companies, list) and companies:
        c0 = companies[0]
        if isinstance(c0, dict) and isinstance(c0.get("company"), dict):
            first = c0["company"]
    name = first.get("name")
    return {
        "phone": None,
        "email": None,
        "owner_name": str(name).strip() if name else None,
        "estimated_revenue": None,
    }


def enrichment_meets_bar(data: dict[str, Any]) -> bool:
    """Return True only when all required enrichment fields are present.

    Required: non-empty ``phone``, ``email``, ``owner_name``, and numeric
    ``estimated_revenue`` (may be zero only if explicitly present as number).

    Args:
        data: Canonical enrichment dict from :func:`normalize_vendor_response`.

    Returns:
        Whether the lead may be marked ``enrichment_status='complete'``.
    """
    phone = data.get("phone")
    email = data.get("email")
    owner = data.get("owner_name")
    rev = data.get("estimated_revenue")
    if not phone or not str(phone).strip():
        return False
    if not email or not str(email).strip():
        return False
    if not owner or not str(owner).strip():
        return False
    if rev is None:
        return False
    if isinstance(rev, (int, float)):
        return True
    return False
