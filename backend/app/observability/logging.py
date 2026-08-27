import json
import logging
import sys
from datetime import datetime, timezone
from app.config import settings


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for application logs.

    Converts standard logging records into single-line JSON objects, automatically
    attaching request_id, duration_ms, and status details. Redacts transcript text
    if DEBUG_TRACE is False per spec §40.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extra structured attributes
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Audit guard: redact raw transcript snippets if present unless debug_trace is True
        if not settings.debug_trace:
            msg_l = log_entry["message"].lower()
            if "transcript turn" in msg_l or "raw_text" in msg_l:
                log_entry["message"] = "[REDACTED TRANSCRIPT TEXT — set DEBUG_TRACE=true to view]"

        return json.dumps(log_entry)


def setup_logging():
    """Initializes root logger with structured JSON output."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(JSONFormatter())
    root.addHandler(console)
