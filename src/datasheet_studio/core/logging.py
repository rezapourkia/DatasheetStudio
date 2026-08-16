"""Temporary debug-logging helper for Datasheet Studio.

All events (opening files, saving, AI requests, errors, and uncaught
exceptions) are buffered in memory. The user can view and copy everything
from the menu action **Help -> Debug Log...**.

This is a temporary aid for debugging; it keeps at most ``_MAX_RECORDS``
entries and never writes logs to disk.
"""

import logging
from collections import deque

_MAX_RECORDS = 2000
LOG_BUFFER: deque[str] = deque(maxlen=_MAX_RECORDS)


class _BufferHandler(logging.Handler):
    """Handler that appends formatted records to the in-memory buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:  # noqa: BLE001 - logging must never crash the app
            pass


def setup_logging(level: int = logging.INFO) -> None:
    """Install the in-memory buffer handler on the root logger (idempotent)."""
    root = logging.getLogger()
    if any(isinstance(h, _BufferHandler) for h in root.handlers):
        return
    handler = _BufferHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)


def get_log_text() -> str:
    """Return all buffered log lines (oldest first, newest last)."""
    return "\n".join(LOG_BUFFER)
