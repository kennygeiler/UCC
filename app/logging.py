"""Structured logging configuration using structlog.

Produces JSON output with component, status, error_type, and context fields
on every log entry. The self-healing agent parses these logs for diagnosis.
"""

import structlog


def configure_logging() -> None:
    """Configure structlog for JSON output to stdout."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger pre-bound with the component field.

    Args:
        component: The pipeline component name (e.g. 'scraper', 'enrichment').
    """
    return structlog.get_logger(
        component=component,
        status=None,
        error_type=None,
        context=None,
    )
