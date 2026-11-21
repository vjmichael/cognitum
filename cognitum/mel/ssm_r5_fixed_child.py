"""R5 fixed file-framed SSM child, callable ONLY by native host custody.

The Windows parent must launch this exact pinned script with CREATE_SUSPENDED,
attach the resulting process to a private kill-on-close kernel Job, and resume
it only after membership verification. The child has no access to Core grants,
HMAC credentials, journal DBs, signed checkpoint authority, or outbox release.
Data files are host-created in a private directory; successful math is only
untrusted numerical candidate data to be validated by the parent.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

MAX_REQUEST = 2 * 1024 * 1024
MAX_RESPONSE = 2 * 1024 * 1024


def _load(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("untrusted SSM frame")
    with path.open("rb") as f:
        raw = f.read(MAX_REQUEST + 1)
    if not 1 <= len(raw) <= MAX_REQUEST:
        raise ValueError("oversized SSM frame")
    def unique(pairs):
        obj = {}
        for name, val in pairs:
            if name in obj:
                raise ValueError("duplicate SSM frame field")
            obj[name] = val
        return obj
    request = json.loads(raw, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite SSM frame")))
    if type(request) is not dict or set(request) != {"operation", "payload"}:
        raise ValueError("SSM frame schema")
    return request


def _write_once(path: Path, reply: dict):
    raw = json.dumps(reply, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
    if not 1 <= len(raw) <= MAX_RESPONSE:
        raise ValueError("oversized SSM result")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())


def main():
    if len(sys.argv) != 3:
        return 2
    inp, out = (Path(x) for x in sys.argv[1:])
    if not inp.is_absolute() or not out.is_absolute() or inp.parent != out.parent:
        return 2
    # -I intentionally excludes the checkout; the fixed on-disk entrypoint
    # explicitly opts into its own repo's checked source tree.
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    from cognitum.mel.ssm_supervisor import (
        SSMComputeFactory, OP, MAX_WIRE, MAX_OUTPUT,
    )
    try:
        request = _load(inp)
        if request["operation"] != OP or type(request["payload"]) is not dict:
            raise ValueError("unreviewed SSM operation")
        from cognitum.mel.ssm_r4_protected import _canonical
        if len(_canonical(request)) > MAX_WIRE + 1024:
            raise ValueError("SSM input budget")
        reply = SSMComputeFactory().handle(OP, request["payload"])
        if len(_canonical(reply)) > MAX_OUTPUT:
            raise ValueError("SSM response budget")
        _write_once(out, {"status": "ok", "reply": reply})
        return 0
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        # A failure is intentionally not given a success-shaped result.
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
