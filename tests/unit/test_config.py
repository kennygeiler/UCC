"""Tests for app.config — Settings validation."""

import os

import pytest
from pydantic import ValidationError


def test_settings_raises_when_database_url_missing(monkeypatch):
    """Settings() must raise ValidationError when DATABASE_URL is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/0")

    from importlib import reload
    import app.config

    reload(app.config)
    with pytest.raises(ValidationError):
        app.config.Settings()


def test_settings_raises_when_sentry_dsn_missing(monkeypatch):
    """Settings() must raise ValidationError when SENTRY_DSN is missing."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/db")
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    from importlib import reload
    import app.config

    reload(app.config)
    with pytest.raises(ValidationError):
        app.config.Settings()


def test_settings_loads_with_required_vars(monkeypatch):
    """Settings() loads successfully when required vars are present."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/db")
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/0")

    from importlib import reload
    import app.config

    reload(app.config)
    settings = app.config.Settings()
    assert settings.DATABASE_URL == "postgresql://x:x@localhost/db"
    assert settings.SENTRY_DSN == "https://fake@sentry.io/0"


def test_settings_optional_vars_default_to_none(monkeypatch):
    """Optional vars should default to None."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/db")
    monkeypatch.setenv("SENTRY_DSN", "https://fake@sentry.io/0")

    from importlib import reload
    import app.config

    reload(app.config)
    settings = app.config.Settings()
    assert settings.GHL_API_KEY is None
    assert settings.APOLLO_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.MANAGER_EMAIL is None
