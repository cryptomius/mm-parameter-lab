"""Structured logging for the engine.

structlog with rich console renderer in development; JSON in production /
batch runs. The frontend log stream consumes the same structured records
through the websocket.
"""

from __future__ import annotations

import logging
import os

import structlog


def configure(level: str = "INFO", json: bool | None = None) -> None:
    use_json = json if json is not None else os.environ.get("MM_LOG_JSON", "0") == "1"
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    if use_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
