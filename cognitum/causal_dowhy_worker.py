"""C14 optional DoWhy process entrypoint. Only Protobuf frames on stdin/stdout.

This file is not a sandbox; Lu must enforce separate OS policy and process-tree kill.
"""
from __future__ import annotations
from pathlib import Path
import sys

if __name__ == '__main__':
    # Python -I suppresses site/user path injections. Whitelisted source root
    # is resolved from the pinned worker path, not from request or environment.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from cognitum.causal_dowhy_backend import _compute_worker, MAX_FRAME
    raw=sys.stdin.buffer.read(MAX_FRAME+1)
    if len(raw)>MAX_FRAME:
        sys.exit(3)
    sys.stdout.buffer.write(_compute_worker(raw))
