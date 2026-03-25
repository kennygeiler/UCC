"""Shared test fixtures for the UCC pipeline test suite."""

import os

import pytest


@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_ucc")
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/0")

    # Clear cached factories so each test picks up monkeypatched env vars
    from app.db import _get_settings, get_engine, get_async_session_factory
    _get_settings.cache_clear()
    get_engine.cache_clear()
    get_async_session_factory.cache_clear()
