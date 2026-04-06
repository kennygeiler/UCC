"""Compliance-specific exceptions."""


class ComplianceNotClearedError(RuntimeError):
    """Raised when export is attempted before compliance gate cleared the lead."""

    def __init__(self, compliance_status: str | None = None) -> None:
        self.compliance_status = compliance_status
        msg = "Lead is not compliance-cleared; export blocked (C-02)."
        if compliance_status:
            msg += f" status={compliance_status}"
        super().__init__(msg)
