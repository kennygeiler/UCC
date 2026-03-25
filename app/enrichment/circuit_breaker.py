"""Circuit breaker for enrichment source protection.

Opens when error rate exceeds threshold, preventing cascade failures.
Uses pybreaker for state management.
"""

import pybreaker

from app.logging import get_logger

logger = get_logger("circuit_breaker")


def create_breaker(name: str, fail_max: int = 5, reset_timeout: int = 300) -> pybreaker.CircuitBreaker:
    """Create a circuit breaker for an enrichment source.

    Args:
        name: Source name for logging.
        fail_max: Number of failures before opening.
        reset_timeout: Seconds before attempting to close.

    Returns:
        Configured CircuitBreaker instance.
    """
    return pybreaker.CircuitBreaker(
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        name=name,
    )


# Pre-configured breakers for each enrichment source
pdl_breaker = create_breaker("pdl")
apollo_breaker = create_breaker("apollo")
opencorporates_breaker = create_breaker("opencorporates")
whitepages_breaker = create_breaker("whitepages")
twilio_breaker = create_breaker("twilio")

BREAKERS: dict[str, pybreaker.CircuitBreaker] = {
    "pdl": pdl_breaker,
    "apollo": apollo_breaker,
    "opencorporates": opencorporates_breaker,
    "whitepages": whitepages_breaker,
    "twilio": twilio_breaker,
}


def is_any_breaker_open() -> bool:
    """Check if any enrichment source breaker is open.

    Returns:
        True if any breaker is in the open state.
    """
    return any(b.current_state == "open" for b in BREAKERS.values())


def get_breaker_status() -> dict[str, str]:
    """Get current state of all breakers.

    Returns:
        Dict mapping source name to state string.
    """
    return {name: b.current_state for name, b in BREAKERS.items()}
