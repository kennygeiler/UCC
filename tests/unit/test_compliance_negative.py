"""Negative scenarios for compliance layers (COMPLY-06)."""

import pytest

from app.compliance.gate import (
    check_blacklist_alliance,
    check_dnc_scrub,
    check_internal_dnc,
)


@pytest.mark.asyncio
async def test_internal_dnc_blocks_when_active_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phone on active internal DNC returns blocked."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        class S:
            async def execute(self, stmt):
                class R:
                    def scalar_one_or_none(self):
                        # Any select(InternalDNC.id) with limit → one row
                        return 1

                return R()

            async def commit(self) -> None:
                return None

            async def rollback(self) -> None:
                return None

            async def close(self) -> None:
                return None

        yield S()

    monkeypatch.setattr("app.compliance.gate.get_session", fake_session)
    blocked = await check_internal_dnc("5550001111", None)
    assert blocked is True


@pytest.mark.asyncio
async def test_dnc_scrub_blocks_on_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """DNC scrub returns blocked when API says on list."""
    monkeypatch.setenv("DNC_SCRUB_API_KEY", "secret-key")
    from app.db import _get_settings

    _get_settings.cache_clear()

    import httpx

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"on_dnc_list": True}

    async def fake_get(*_a, **_k):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    blocked = await check_dnc_scrub("5551234567")
    assert blocked is True


@pytest.mark.asyncio
async def test_blacklist_blocks_litigator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blacklist Alliance returns blocked for litigator."""
    monkeypatch.setenv("BLACKLIST_API_KEY", "secret-key")
    from app.db import _get_settings

    _get_settings.cache_clear()

    import httpx

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"is_litigator": True}

    async def fake_get(*_a, **_k):
        return FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    blocked = await check_blacklist_alliance("5559998888")
    assert blocked is True
