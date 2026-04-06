"""Rolling enrichment error-rate tracker."""

from app.enrichment.normalize import enrichment_meets_bar
from app.enrichment.rate_tracker import EnrichmentRateTracker


def test_failure_rate_trips_after_min_attempts():
    """Threshold applies once enough attempts exist in window."""
    clock = [0.0]

    def now() -> float:
        return clock[0]

    t = EnrichmentRateTracker(
        window_seconds=300.0,
        threshold=0.2,
        min_attempts=5,
        now_fn=now,
    )
    for i in range(5):
        clock[0] = float(i)
        t.record_attempt("pdl")
        t.record_failure("pdl")
    assert t.failure_rate("pdl") == 1.0
    assert t.should_trip("pdl") is True


def test_enrichment_meets_bar_partial():
    """Partial dict does not trip completeness without all fields."""
    assert enrichment_meets_bar(
        {
            "phone": "1",
            "email": "a@b.com",
            "owner_name": "x",
            "estimated_revenue": 1.0,
        }
    )
    assert not enrichment_meets_bar({"phone": "1", "email": "", "owner_name": "x", "estimated_revenue": 1.0})
