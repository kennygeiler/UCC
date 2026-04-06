"""Enrichment pipeline unit tests."""

import pytest

from app.enrichment.cache import enrichment_cache_key


def test_enrichment_cache_key_stable():
    assert enrichment_cache_key("  Acme LLC ", "tx") == "acme llc|TX"


@pytest.mark.asyncio
async def test_run_enrichment_pipeline_returns_zero_when_halted(monkeypatch):
    """When check_pipeline_halt is true, batch does no work."""

    async def halted() -> bool:
        return True

    monkeypatch.setattr("app.enrichment.pipeline.check_pipeline_halt", halted)
    from app.enrichment.pipeline import run_enrichment_pipeline

    n = await run_enrichment_pipeline(batch_size=10)
    assert n == 0
