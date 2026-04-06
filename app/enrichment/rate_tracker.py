"""Rolling error-rate tracking per enrichment source (C-03).

When failure rate in the configured window exceeds the threshold, the corresponding
pybreaker is opened and enrichment HALT is armed (see ``check_pipeline_halt``).
"""

from collections import defaultdict, deque
from time import time
from typing import Callable

from app.logging import get_logger

logger = get_logger("enrichment_rate_tracker")


class EnrichmentRateTracker:
    """Track attempts and failures per source in a sliding time window."""

    def __init__(
        self,
        window_seconds: float,
        threshold: float,
        min_attempts: int,
        now_fn: Callable[[], float] | None = None,
    ) -> None:
        self.window_seconds = window_seconds
        self.threshold = threshold
        self.min_attempts = min_attempts
        self._now = now_fn or time
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self.halted: bool = False

    def _prune(self, source: str) -> None:
        cutoff = self._now() - self.window_seconds
        for dq in (self._attempts[source], self._failures[source]):
            while dq and dq[0] < cutoff:
                dq.popleft()

    def record_attempt(self, source: str) -> None:
        self._prune(source)
        self._attempts[source].append(self._now())

    def record_failure(self, source: str) -> None:
        self._prune(source)
        self._failures[source].append(self._now())

    def failure_rate(self, source: str) -> float:
        self._prune(source)
        a = len(self._attempts[source])
        f = len(self._failures[source])
        if a == 0:
            return 0.0
        return f / a

    def should_trip(self, source: str) -> bool:
        self._prune(source)
        a = len(self._attempts[source])
        if a < self.min_attempts:
            return False
        return self.failure_rate(source) >= self.threshold

    def reset(self) -> None:
        self._attempts.clear()
        self._failures.clear()
        self.halted = False


_tracker: EnrichmentRateTracker | None = None


def get_rate_tracker() -> EnrichmentRateTracker:
    """Singleton rate tracker configured from Settings (lazy)."""
    global _tracker
    if _tracker is None:
        from app.config import Settings

        s = Settings()
        _tracker = EnrichmentRateTracker(
            window_seconds=float(s.ENRICH_BREAKER_ERROR_WINDOW_SECONDS),
            threshold=s.ENRICH_BREAKER_ERROR_RATE_THRESHOLD,
            min_attempts=s.ENRICH_RATE_MIN_ATTEMPTS_BEFORE_HALT,
        )
    return _tracker


def reset_rate_tracker_for_tests() -> None:
    """Clear tracker singleton (tests only)."""
    global _tracker
    _tracker = None
