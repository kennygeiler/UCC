"""Backoff schedule for enrichment retry queue (1h, 4h, 24h, 72h)."""


def next_backoff_seconds(attempt_number: int) -> int:
    """Seconds until next retry after a failed enrichment attempt.

    attempt_number is 1 for the first scheduled retry, 2 for the second, etc.

    Args:
        attempt_number: Which retry generation (>=1).

    Returns:
        Delay in seconds before ``next_retry_at``.
    """
    if attempt_number <= 1:
        return 3600  # 1h
    if attempt_number == 2:
        return 14400  # 4h
    if attempt_number == 3:
        return 86400  # 24h
    return 259200  # 72h
