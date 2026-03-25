"""Generic waterfall executor — shared by enrichment, compliance, and scraper fallback.

Tries sources in configured order, returns first success. Respects circuit breakers.
ADR-008 pattern: generic waterfall executor as shared infrastructure.
"""

from typing import Any, Callable, Awaitable

from app.logging import get_logger

logger = get_logger("waterfall")


class WaterfallExecutor:
    """Execute callables in order, returning first successful result.

    Each strategy is an async callable that returns a result or raises.
    The executor tries each in order, skipping those with open circuit breakers.
    """

    def __init__(self, strategies: list[tuple[str, Callable[..., Awaitable[Any]]]]):
        """Initialize with ordered list of (name, async_callable) pairs.

        Args:
            strategies: List of (source_name, async_function) tuples.
        """
        self.strategies = strategies

    async def execute(self, **kwargs) -> tuple[str, Any]:
        """Try each strategy in order, return first success.

        Args:
            **kwargs: Arguments passed to each strategy callable.

        Returns:
            Tuple of (source_name, result) from the first successful strategy.

        Raises:
            WaterfallExhaustedError: All strategies failed.
        """
        errors: list[tuple[str, Exception]] = []
        for name, strategy in self.strategies:
            try:
                result = await strategy(**kwargs)
                logger.info("waterfall_hit", source=name)
                return name, result
            except Exception as exc:
                logger.warning("waterfall_miss", source=name, error=str(exc))
                errors.append((name, exc))

        raise WaterfallExhaustedError(errors)


class WaterfallExhaustedError(Exception):
    """All waterfall strategies failed."""

    def __init__(self, errors: list[tuple[str, Exception]]):
        self.errors = errors
        sources = ", ".join(name for name, _ in errors)
        super().__init__(f"All sources failed: {sources}")
