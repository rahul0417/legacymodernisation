# MIGRATION TRACEABILITY
# MWU: MWU-CRUD-001
# RULES: n/a — cross-cutting infrastructure
# LEGACY: n/a — scaffold (PHP had no structured logging)
# COMPONENT: core/logging
# GENERATED: 2026-05-14
# STRATEGY: REWRITE_ASYNC_PG_REACT

"""
Stdlib logging setup — JSON or plain text.

Logger name convention: `crud.<module>` (e.g. `crud.users.service`).
Never log PII (full name, email) at INFO+ — only user `id`. DB-layer
errors translate to 409 and log the offending email scrubbed.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class _JsonFormatter(logging.Formatter):
    """Single-line JSON output for structured ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, _DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach any structured extras the caller passed via `extra=`.
        for key, value in record.__dict__.items():
            if key in (
                "args", "msg", "levelname", "levelno", "pathname", "filename",
                "module", "exc_info", "exc_text", "stack_info", "lineno",
                "funcName", "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process", "name",
            ):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Install handlers on the root logger. Idempotent."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    if json_logs:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
    root.addHandler(handler)
