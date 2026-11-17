"""Structured JSON logging with a per-document correlation id."""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        cid = get_correlation_id()
        if cid:
            payload["correlation_id"] = cid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any structured extras passed via logger.info(..., extra={"fields": {...}})
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str = "docpipe") -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, msg: str, **fields) -> None:
    """Emit a structured log line with arbitrary extra fields."""
    logger.info(msg, extra={"fields": fields})
