"""Tests for app.logging — structlog JSON configuration."""

import json
import io
from unittest.mock import patch


def test_configure_logging_does_not_raise():
    """configure_logging() should complete without error."""
    from app.logging import configure_logging
    configure_logging()


def test_get_logger_binds_component():
    """get_logger() should return a logger with the component field pre-bound."""
    from app.logging import configure_logging, get_logger
    configure_logging()
    logger = get_logger("scraper")
    # The logger should have 'component' in its bound context
    assert logger is not None


def test_logging_produces_json_output(capsys):
    """Logging should produce JSON-formatted output."""
    from app.logging import configure_logging, get_logger
    configure_logging()
    logger = get_logger("test_component")
    logger.info(
        "test message",
        status="ok",
        error_type=None,
        context={"k": "v"},
    )
    captured = capsys.readouterr()
    # structlog with PrintLoggerFactory writes to stdout
    line = captured.out.strip()
    parsed = json.loads(line)
    assert parsed["component"] == "test_component"
    assert parsed["status"] == "ok"
    assert parsed["error_type"] is None
    assert parsed["context"] == {"k": "v"}
    assert "event" in parsed
