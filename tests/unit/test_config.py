"""Tests for app.config — Settings validation."""

import pytest
from pydantic import ValidationError


_VALID_SENTRY = "https://public@o123456.ingest.sentry.io/1234567"


def test_settings_raises_when_database_url_missing(monkeypatch):
    """Settings() must raise ValidationError when DATABASE_URL is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENTRY_DSN", _VALID_SENTRY)

    from importlib import reload

    import app.config

    reload(app.config)
    with pytest.raises(ValidationError):
        app.config.Settings(_env_file=None)


def test_settings_loads_when_sentry_dsn_missing(monkeypatch):
    """SENTRY_DSN is optional for local runs; pipeline skips Sentry init if unset."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/db")
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    from importlib import reload

    import app.config

    reload(app.config)
    settings = app.config.Settings(_env_file=None)
    assert settings.SENTRY_DSN is None


def test_settings_loads_with_required_vars(monkeypatch):
    """Settings() loads successfully when required vars are present."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/db")
    monkeypatch.setenv("SENTRY_DSN", _VALID_SENTRY)

    from importlib import reload

    import app.config

    reload(app.config)
    settings = app.config.Settings(_env_file=None)
    assert settings.DATABASE_URL == "postgresql://x:x@localhost/db"
    assert settings.SENTRY_DSN == _VALID_SENTRY


def test_settings_optional_vars_default_to_none(monkeypatch):
    """Optional vars should default to None when not in environment."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@localhost/db")
    monkeypatch.setenv("SENTRY_DSN", _VALID_SENTRY)

    from importlib import reload

    import app.config

    reload(app.config)
    settings = app.config.Settings(_env_file=None)
    assert settings.GHL_API_KEY is None
    assert settings.APOLLO_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.MANAGER_EMAIL is None
