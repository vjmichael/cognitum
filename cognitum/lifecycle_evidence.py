"""Fail-closed *structural* review of local Linux worker lifecycle probe receipts.

This is not an OS isolation probe, a signature verifier, or Lu authorization.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "cognitum.lifecycle.v1"
REQUIRED_LINUX = frozenset({
    "supervisor-death-idle",
    "supervisor-death-launch-race",
    "supervisor-death-midflight",
    "cancel-with-descendants",
    "output-pipe-backpressure",
})
ALLOWED_PROBES = REQUIRED_LINUX
MAX_RECEIPT_BYTES = 131_072
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class InvalidEvidence(ValueError):
    """The receipt cannot be used to claim a complete passing gate."""


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    output = {}
    for name, value in items:
        if name in output:
            raise InvalidEvidence(f"duplicate JSON key: {name}")
        output[name] = value
    return output


def _reject_constant(value: str) -> None:
    raise InvalidEvidence(f"nonfinite JSON number: {value}")


def evaluate_receipt(payload: bytes, *, source_sha256: str | None = None) -> dict[str, Any]:
    """Validate one bounded receipt. Return a deterministic verdict; never throw on probe failures.

    Raises InvalidEvidence only for corrupt/unparseable receipt envelopes.
    """
    if not isinstance(payload, bytes) or len(payload) > MAX_RECEIPT_BYTES:
        raise InvalidEvidence("receipt must be bounded bytes")
    try:
        doc = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidEvidence("receipt is not strict UTF-8 JSON") from exc
    if not isinstance(doc, dict):
        raise InvalidEvidence("receipt must be a JSON object")
    allowed = {"schema", "platform", "source_sha256", "runner_id", "cases"}
    if set(doc) != allowed or doc.get("schema") != SCHEMA or doc.get("platform") != "linux":
        raise InvalidEvidence("unsupported or incomplete receipt envelope")
    actual_hash = doc["source_sha256"]
    if not isinstance(actual_hash, str) or not _SHA256.fullmatch(actual_hash):
        raise InvalidEvidence("source_sha256 must be a lowercase SHA-256 digest")
    if source_sha256 is not None and (not isinstance(source_sha256, str)
                                     or actual_hash != source_sha256):
        raise InvalidEvidence("receipt source does not match expected source digest")
    if (not isinstance(doc["runner_id"], str) or not doc["runner_id"].strip()
            or len(doc["runner_id"]) > 128):
        raise InvalidEvidence("missing or oversized runner_id")
    cases = doc["cases"]
    if not isinstance(cases, list) or len(cases) > 64:
        raise InvalidEvidence("cases must be a bounded list")

    seen: set[str] = set()
    failures: list[str] = []
    for i, case in enumerate(cases):
        if not isinstance(case, dict) or set(case) != {
            "id", "outcome", "observed", "worker_pid", "reaped", "live_descendant_pids",
        }:
            failures.append(f"case {i}: missing or unknown fields")
            continue
        probe_id = case["id"]
        if not isinstance(probe_id, str) or probe_id not in ALLOWED_PROBES:
            failures.append(f"case {i}: unknown probe")
            continue
        if probe_id in seen:
            failures.append(f"{probe_id}: duplicate probe outcome")
            continue
        seen.add(probe_id)
        if case["outcome"] != "PASS":
            failures.append(f"{probe_id}: non-passing outcome")
        if case["observed"] is not True:
            failures.append(f"{probe_id}: no positive observation")
        pid = case["worker_pid"]
        if type(pid) is not int or pid < 0:
            failures.append(f"{probe_id}: invalid worker PID")
        elif pid == 0 and probe_id != "supervisor-death-launch-race":
            failures.append(f"{probe_id}: zero PID outside launch race")
        if case["reaped"] is not True:
            failures.append(f"{probe_id}: worker not confirmed reaped")
        survivors = case["live_descendant_pids"]
        if not isinstance(survivors, list) or any(type(p) is not int or p <= 0 for p in survivors):
            failures.append(f"{probe_id}: invalid descendant PID list")
        elif survivors:
            failures.append(f"{probe_id}: descendants survived")

    for missing in sorted(REQUIRED_LINUX - seen):
        failures.append(f"{missing}: required probe missing")
    return {
        "schema": SCHEMA,
        "status": "PASS" if not failures else "FAIL",
        "receipt_sha256": hashlib.sha256(payload).hexdigest(),
        "source_sha256": actual_hash,
        "checked_probes": len(seen),
        "required_probes": len(REQUIRED_LINUX),
        "failures": failures,
        "qualification": "structural-only; NOT OS isolation certification",
    }


def verify_file(path: str | Path, *, source_sha256: str | None = None) -> dict[str, Any]:
    with open(path, "rb") as handle:
        payload = handle.read(MAX_RECEIPT_BYTES + 1)
    return evaluate_receipt(payload, source_sha256=source_sha256)
