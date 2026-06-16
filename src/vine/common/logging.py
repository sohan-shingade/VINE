"""Structured logging. One configured logger factory for the whole project."""

from __future__ import annotations

import logging

import structlog

from vine.common.config import settings

_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(format="%(message)s", level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structured logger, e.g. `log = get_logger(__name__)`."""
    _configure()
    return structlog.get_logger(name)
