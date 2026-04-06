"""Tests for alias updater scheduler entrypoint."""

import pytest

from app.mca.alias_updater import run_alias_update_job


@pytest.mark.asyncio
async def test_run_alias_update_job_swallows_inner_errors(monkeypatch):
    """Scheduler must not crash if run_alias_update raises."""

    async def _boom() -> int:
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr("app.mca.alias_updater.run_alias_update", _boom)
    await run_alias_update_job()
