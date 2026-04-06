"""Enrichment retry queue behavior."""

import pytest


@pytest.mark.asyncio
async def test_process_enrichment_retries_zero_when_halted(monkeypatch):
    async def halted() -> bool:
        return True

    monkeypatch.setattr("app.enrichment.retry_worker.check_pipeline_halt", halted)
    from app.enrichment.retry_worker import process_enrichment_retries

    n = await process_enrichment_retries(batch_size=5)
    assert n == 0
