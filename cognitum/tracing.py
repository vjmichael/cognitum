"""Fail-closed metadata-only traces; payload/result fields are never accepted.

This is not a de-identification service. The caller must use opaque IDs,
trusted module names and sanitized error codes, never user text or secrets.
"""
import json
import math
import re
from threading import Lock

_TRACE_FIELDS = frozenset({
    "trace_version", "request_id", "correlation_id", "operation",
    "module", "execution_status", "error", "latency_ms",
})
_MODULE_FIELDS = frozenset({"name", "version"})
_ERROR_CODE = re.compile(r"[a-z][a-z0-9_]{0,127}\Z")
_STATUS_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


def _bounded_text(value, label):
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise ValueError(f"invalid trace {label}")
    return value


def validated_event(event):
    """Return an independent, closed metadata record; reject extras."""
    if type(event) is not dict or set(event) != _TRACE_FIELDS:
        raise ValueError("trace must contain exactly the metadata fields")
    if event["trace_version"] != "1.0.0":
        raise ValueError("unsupported trace version")
    safe = {"trace_version": "1.0.0"}
    for key in ("request_id", "correlation_id", "operation"):
        safe[key] = _bounded_text(event[key], key)
    module = event["module"]
    if module is not None:
        if type(module) is not dict or set(module) != _MODULE_FIELDS:
            raise ValueError("invalid trace module metadata")
        module = {key: _bounded_text(module[key], "module " + key)
                  for key in ("name", "version")}
    safe["module"] = module
    status = event["execution_status"]
    if type(status) is not str or not _STATUS_CODE.fullmatch(status):
        raise ValueError("invalid trace status code")
    safe["execution_status"] = status
    error = event["error"]
    if error is not None and (type(error) is not str or not _ERROR_CODE.fullmatch(error)):
        raise ValueError("trace errors must be sanitized codes")
    safe["error"] = error
    latency = event["latency_ms"]
    if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
        raise ValueError("invalid trace latency")
    safe["latency_ms"] = latency
    return safe


class Trace:
    """Validated metadata-only in-memory/JSONL trace; failures propagate."""

    def __init__(self, path=None):
        self.path = path
        self.events = []
        self.lock = Lock()

    def append(self, event):
        safe = validated_event(event)
        record = json.dumps(safe, sort_keys=True, allow_nan=False)
        with self.lock:
            if self.path:
                with open(self.path, "a", encoding="utf-8") as stream:
                    stream.write(record + "\n")
            # Append only after the on-disk write succeeds. If disk writing
            # fails, callers must not mistake a memory-only entry for an audit.
            self.events.append(safe)
