"""Tests for watchdog structured logging (PLAT-07, C-07)."""

import json

from watchdog.logging_config import configure_logging, get_logger


def test_watchdog_logging_json_shape(capsys):
    """Watchdog logger emits JSON with required keys."""
    configure_logging()
    log = get_logger("watchdog_test")
    log.info(
        "test_event",
        status="ok",
        error_type=None,
        context={"check": "unit"},
    )
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["component"] == "watchdog_test"
    assert parsed["status"] == "ok"
    assert "error_type" in parsed
    assert "context" in parsed
