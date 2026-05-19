"""Scraper-specific exceptions."""


class ScraperNotReadyError(RuntimeError):
    """Raised when a Tier 1 state scraper is registered but not yet implemented."""

    def __init__(self, state_code: str, reason: str) -> None:
        self.state_code = state_code
        self.reason = reason
        super().__init__(f"{state_code}: {reason}")
