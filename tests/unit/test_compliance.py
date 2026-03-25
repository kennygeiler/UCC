"""Tests for the compliance gate module."""

from app.compliance.gate import (
    check_internal_dnc,
    check_datamerch,
    check_dnc_scrub,
    check_blacklist_alliance,
)


def test_internal_dnc_returns_false_for_no_contact_info():
    """No phone/email should not be blocked."""
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        check_internal_dnc(None, None)
    )
    assert result is False


def test_datamerch_returns_false_when_unconfigured(monkeypatch):
    """DataMerch fallback returns False when API key is not set."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/0")
    monkeypatch.delenv("DATAMERCH_API_KEY", raising=False)

    from app.db import _get_settings
    _get_settings.cache_clear()

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        check_datamerch("Test Business")
    )
    assert result is False


def test_dnc_scrub_returns_false_for_no_phone():
    """No phone number should not be blocked."""
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        check_dnc_scrub(None)
    )
    assert result is False


def test_blacklist_returns_false_for_no_phone():
    """No phone number should not be blocked."""
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        check_blacklist_alliance(None)
    )
    assert result is False
