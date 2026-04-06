"""Ensure campaign export cannot bypass the compliance gate (COMPLY-05, C-02)."""

from app.compliance.exceptions import ComplianceNotClearedError


def require_compliance_cleared(lead_data: dict) -> None:
    """Raise if ``lead_data`` is not cleared for export.

    Args:
        lead_data: Dict containing ``compliance_status`` (e.g. from Lead ORM or export payload).

    Raises:
        ComplianceNotClearedError: When status is not exactly ``cleared``.
    """
    status = lead_data.get("compliance_status")
    if status != "cleared":
        raise ComplianceNotClearedError(compliance_status=status)
