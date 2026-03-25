"""Async rate limiter with per-state delays, jitter, and exponential backoff."""

import asyncio
import random
import time


class RateLimiter:
    """Per-state async rate limiter with jitter and exponential backoff.

    Default: 1 request per 3 seconds with +/-20% jitter.
    On error: exponential backoff doubling from base_delay up to max_backoff.
    """

    def __init__(
        self,
        base_delay: float = 3.0,
        jitter_pct: float = 0.20,
        max_backoff: float = 60.0,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            base_delay: Base delay in seconds between requests.
            jitter_pct: Jitter percentage (+/- this fraction of delay).
            max_backoff: Maximum backoff delay in seconds after errors.
        """
        self.base_delay = base_delay
        self.jitter_pct = jitter_pct
        self.max_backoff = max_backoff
        self._last_request: dict[str, float] = {}
        self._error_count: dict[str, int] = {}

    def _compute_delay(self, state: str) -> float:
        """Compute the next delay for a state, including jitter and backoff."""
        errors = self._error_count.get(state, 0)
        if errors > 0:
            delay = min(self.base_delay * (2 ** errors), self.max_backoff)
        else:
            delay = self.base_delay
        jitter = delay * self.jitter_pct * (2 * random.random() - 1)
        return max(0.0, delay + jitter)

    async def wait(self, state: str) -> None:
        """Wait the appropriate delay before the next request for a state.

        Args:
            state: The state code to rate-limit.
        """
        delay = self._compute_delay(state)
        last = self._last_request.get(state, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request[state] = time.monotonic()

    def record_success(self, state: str) -> None:
        """Reset backoff counter after a successful request.

        Args:
            state: The state code.
        """
        self._error_count[state] = 0

    def record_error(self, state: str) -> None:
        """Increment backoff counter after a failed request.

        Args:
            state: The state code.
        """
        self._error_count[state] = self._error_count.get(state, 0) + 1
