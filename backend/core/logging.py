"""
backend/core/logging.py
=======================
Structured logging setup (JSON in production, colored text in development).
"""

import logging
import sys
from typing import Any

from backend.core.config import settings


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        import traceback

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))

        if hasattr(record, "extra"):
            payload.update(record.extra)  # type: ignore[arg-type]

        return json.dumps(payload, default=str, ensure_ascii=False)


def setup_logging() -> None:
    """Configure the root logger for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.LOG_FORMAT == "json" or settings.is_production:
        handler.setFormatter(JSONFormatter())
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root_logger.addHandler(handler)

    # Optional file handler
    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn").setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Use as: logger = get_logger(__name__)"""
    return logging.getLogger(name)
