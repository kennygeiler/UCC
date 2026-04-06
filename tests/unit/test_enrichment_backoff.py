"""Backoff schedule for enrichment retries."""

from app.enrichment.backoff import next_backoff_seconds


def test_next_backoff_seconds_mapping():
    assert next_backoff_seconds(1) == 3600
    assert next_backoff_seconds(2) == 14400
    assert next_backoff_seconds(3) == 86400
    assert next_backoff_seconds(4) == 259200
    assert next_backoff_seconds(99) == 259200
