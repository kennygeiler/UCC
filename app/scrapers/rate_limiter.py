"""Async rate limiter with per-state delays, jitter, and exponential backoff.

Tier-3 states (C-09) enforce a minimum 10-second delay and rotate proxies.
"""

import asyncio
import itertools
import random
import time

from app.config import Settings


# Tier-3 constraint C-09: 1 request per 10 seconds minimum
TIER3_MIN_DELAY = 10.0


class RateLimiter:
    """Per-state async rate limiter with jitter and exponential backoff.

    Default: 1 request per 3 seconds with +/-20% jitter.
    Tier-3: minimum 10-second delay with proxy rotation (C-09).
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
        self._proxy_cycle = self._build_proxy_cycle()

    @staticmethod
    def _build_proxy_cycle():
        """Build a cycling iterator over configured proxy URLs.

        Returns None if PROXY_URL is not configured or Settings cannot be loaded
        (e.g. in unit tests without full env).
        """
        try:
            settings = Settings()
        except Exception:
            return None
        proxy_url = settings.PROXY_URL
        if not proxy_url:
            return None
        # Support comma-separated list of proxies for rotation
        proxies = [p.strip() for p in proxy_url.split(",") if p.strip()]
        if not proxies:
            return None
        return itertools.cycle(proxies)

    def _compute_delay(self, state: str, tier: int | None = None) -> float:
        """Compute the next delay for a state, including jitter and backoff.

        For tier-3 states the delay floor is TIER3_MIN_DELAY (10 s).
        """
        errors = self._error_count.get(state, 0)
        if errors > 0:
            delay = min(self.base_delay * (2 ** errors), self.max_backoff)
        else:
            delay = self.base_delay

        jitter = delay * self.jitter_pct * (2 * random.random() - 1)
        final_delay = max(0.0, delay + jitter)

        # Tier-3 floor (C-09): never go below 10 seconds, applied AFTER jitter
        if tier == 3:
            final_delay = max(final_delay, TIER3_MIN_DELAY)

        return final_delay

    async def wait(self, state: str, tier: int | None = None) -> None:
        """Wait the appropriate delay before the next request for a state.

        Args:
            state: The state code to rate-limit.
            tier: Optional tier (1, 2, or 3). Tier 3 enforces C-09 limits.
        """
        delay = self._compute_delay(state, tier=tier)
        last = self._last_request.get(state, 0.0)
        elapsed = time.monotonic() - last
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request[state] = time.monotonic()

    def get_proxy(self, tier: int | None = None) -> str | None:
        """Return the next proxy URL for tier-3 requests, or None.

        Args:
            tier: The state tier. Only tier 3 gets proxy rotation.

        Returns:
            Proxy URL string or None if proxies are unavailable or not tier 3.
        """
        if tier != 3 or self._proxy_cycle is None:
            return None
        return next(self._proxy_cycle)

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
