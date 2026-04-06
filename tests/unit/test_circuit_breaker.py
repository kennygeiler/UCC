"""Circuit breaker helpers for enrichment sources."""

import pybreaker

from app.enrichment.circuit_breaker import is_any_breaker_open


def test_pybreaker_current_state_strings():
    """pybreaker exposes string state via current_state."""
    b = pybreaker.CircuitBreaker(fail_max=2, reset_timeout=1)
    assert b.current_state == "closed"
    b.open()
    assert b.current_state == "open"


def test_is_any_breaker_open_detects_global_breaker():
    """is_any_breaker_open reflects an opened registered breaker."""
    from app.enrichment import circuit_breaker as cb

    br = cb.BREAKERS["whitepages"]
    prev = br.current_state
    try:
        br.open()
        assert is_any_breaker_open() is True
    finally:
        if prev == "closed":
            br.close()
