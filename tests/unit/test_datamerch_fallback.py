"""DataMerch layer behavior when API key is missing (C-15)."""

import pytest

from app.compliance.gate import check_datamerch


@pytest.mark.asyncio
async def test_datamerch_fail_open_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default: no key → not blocked (fail-open)."""
    monkeypatch.delenv("DATAMERCH_API_KEY", raising=False)
    monkeypatch.delenv("COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH", raising=False)
    from app.db import _get_settings

    _get_settings.cache_clear()
    result = await check_datamerch("Test Business")
    assert result is False


@pytest.mark.asyncio
async def test_datamerch_fail_closed_when_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH blocks when key absent."""
    monkeypatch.delenv("DATAMERCH_API_KEY", raising=False)
    monkeypatch.setenv("COMPLIANCE_FAIL_CLOSED_WITHOUT_DATAMERCH", "true")
    from app.db import _get_settings

    _get_settings.cache_clear()
    result = await check_datamerch("Test Business")
    assert result is True
