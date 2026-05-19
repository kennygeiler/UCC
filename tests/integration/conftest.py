"""Integration tests use project ``.env`` DATABASE_URL when not the unit-test default."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_UNIT_TEST_DSN = "postgresql+asyncpg://test:test@localhost:5432/test_ucc"


@pytest.fixture(autouse=True)
def integration_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefer real Postgres from ``.env`` over the unit-test placeholder DSN."""
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
    url = os.environ.get("DATABASE_URL", "")
    if url and url != _UNIT_TEST_DSN:
        monkeypatch.setenv("DATABASE_URL", url)
        from app.db import _get_settings, get_async_session_factory, get_engine

        _get_settings.cache_clear()
        get_engine.cache_clear()
        get_async_session_factory.cache_clear()
