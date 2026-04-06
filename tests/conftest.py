"""Shared test fixtures for the UCC pipeline test suite."""

import os
import sys

import pytest

# Valid Sentry DSN for imports of app.main / agent.main (SDK validates at import time).
_VALID_SENTRY_DSN = "https://public@o123456.ingest.sentry.io/1234567"

if "pytest" in sys.modules:
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_ucc")
    os.environ["SENTRY_DSN"] = _VALID_SENTRY_DSN
    os.environ.setdefault("SCRAPER_SCHEDULER_ENABLED", "false")


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_ucc")
    monkeypatch.setenv("SENTRY_DSN", _VALID_SENTRY_DSN)
    monkeypatch.setenv("SCRAPER_SCHEDULER_ENABLED", "false")

    # Clear cached factories so each test picks up monkeypatched env vars
    from app.db import _get_settings, get_async_session_factory, get_engine

    _get_settings.cache_clear()
    get_engine.cache_clear()
    get_async_session_factory.cache_clear()
