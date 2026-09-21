import json
import logging
from typing import Any

from .tracing import get_current_trace


class JsonFormatter(logging.Formatter):
    """Render application logs as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        trace = get_current_trace()

        if trace is not None:
            payload["trace_id"] = trace.trace_id
            payload["span_id"] = trace.span_id

        extra = getattr(record, "observability", None)

        if isinstance(extra, dict):
            payload["context"] = extra

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())

    handler = next(
        (
            existing
            for existing in root.handlers
            if isinstance(existing, logging.StreamHandler)
        ),
        None,
    )

    if handler is None:
        handler = logging.StreamHandler()
        root.addHandler(handler)

    handler.setFormatter(JsonFormatter())
