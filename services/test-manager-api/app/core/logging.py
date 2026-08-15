"""Structured logging with context injection."""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from app.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)


class ContextFilter(logging.Filter):
    """Inject request_id/job_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.job_id = job_id_var.get() or "-"
        return True


def _make_json_formatter() -> logging.Formatter:
    from pythonjsonlogger import jsonlogger

    return jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(job_id)s"
    )


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    context_filter = ContextFilter()
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(_make_json_formatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [req=%(request_id)s job=%(job_id)s] %(message)s"
            )
        )
    handler.addFilter(context_filter)
    root.addHandler(handler)
    root.addFilter(context_filter)
    for name in ("uvicorn.access", "uvicorn.error"):
        h = logging.StreamHandler(sys.stdout)
        h.addFilter(context_filter)
        h.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s [req=%(request_id)s job=%(job_id)s] %(message)s"
            )
        )
        logger_obj = logging.getLogger(name)
        logger_obj.handlers = [h]
        logger_obj.propagate = False
