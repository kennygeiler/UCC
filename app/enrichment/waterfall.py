"""Generic waterfall executor — shared by enrichment, compliance, and scraper fallback.

Tries sources in configured order, returns first success. Skips strategies whose
circuit breaker is open. ADR-008 pattern: generic waterfall executor as shared infrastructure.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pybreaker

from app.logging import get_logger

logger = get_logger("waterfall")


class WaterfallExecutor:
    """Execute callables in order, returning first successful result.

    Each strategy is an async callable that returns a result or raises.
    The executor tries each in order, skipping those with open circuit breakers.
    """

    def __init__(
        self,
        strategies: list[tuple[str, Callable[..., Awaitable[Any]]]],
        breakers: dict[str, pybreaker.CircuitBreaker] | None = None,
        on_attempt: Callable[[str], None] | None = None,
        on_failure: Callable[[str, Exception], None] | None = None,
    ) -> None:
        """Initialize with ordered list of (name, async_callable) pairs.

        Args:
            strategies: List of (source_name, async_function) tuples.
            breakers: Optional map of source name to pybreaker; open breakers are skipped.
            on_attempt: Called with source name before each invocation (not when skipped).
            on_failure: Called with (source_name, exc) after a raised exception.
        """
        self.strategies = strategies
        self.breakers = breakers or {}
        self.on_attempt = on_attempt
        self.on_failure = on_failure

    async def execute(self, **kwargs: Any) -> tuple[str, Any]:
        """Try each strategy in order, return first success.

        Args:
            **kwargs: Arguments passed to each strategy callable.

        Returns:
            Tuple of (source_name, result) from the first successful strategy.

        Raises:
            WaterfallExhaustedError: All strategies failed or were skipped.
        """
        errors: list[tuple[str, Exception]] = []
        skipped: list[str] = []

        for name, strategy in self.strategies:
            breaker = self.breakers.get(name)
            if breaker is not None and breaker.current_state == "open":
                skipped.append(name)
                logger.info(
                    "waterfall_skip",
                    component="enrichment",
                    status="skipped",
                    error_type="circuit_open",
                    context=name,
                )
                continue

            if self.on_attempt:
                self.on_attempt(name)

            try:
                result = await strategy(**kwargs)
                logger.info("waterfall_hit", source=name)
                return name, result
            except Exception as exc:
                if self.on_failure:
                    self.on_failure(name, exc)
                logger.warning(
                    "waterfall_miss",
                    source=name,
                    error=str(exc)[:200],
                )
                errors.append((name, exc))

        raise WaterfallExhaustedError(errors, skipped=skipped)


class WaterfallExhaustedError(Exception):
    """All waterfall strategies failed or were skipped (e.g. all breakers open)."""

    def __init__(
        self,
        errors: list[tuple[str, Exception]],
        skipped: list[str] | None = None,
    ) -> None:
        self.errors = errors
        self.skipped = skipped or []
        parts: list[str] = []
        if self.errors:
            parts.append("failed: " + ", ".join(name for name, _ in self.errors))
        if self.skipped:
            parts.append("skipped: " + ", ".join(self.skipped))
        msg = "; ".join(parts) if parts else "no strategies available"
        super().__init__(f"Waterfall exhausted ({msg})")
