"""Structured, privacy-conscious request tracing for the deployed API."""
from __future__ import annotations

import contextvars
import json
import logging
import time
from typing import Any


_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")
_logger = logging.getLogger("qdfro.trace")

if not _logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def set_trace_id(value: str) -> contextvars.Token[str]:
    return _trace_id.set(value)


def reset_trace_id(token: contextvars.Token[str]) -> None:
    _trace_id.reset(token)


def trace_event(event: str, **fields: Any) -> None:
    """Emit one searchable JSON event without request bodies or secrets."""
    _logger.info(json.dumps({
        "event": event,
        "trace_id": _trace_id.get(),
        "at_ms": round(time.time() * 1000),
        **fields,
    }, sort_keys=True, default=str, separators=(",", ":")))
