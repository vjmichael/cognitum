"""Fixed-worker release barrier for the cgroup2 test fixture (Linux only).

This barrier does not confer host authority or OS sandboxing. The one-byte
release is accepted only after the *write side has closed*; extra tokens,
truncation, and retained inherited writers fail closed under a deadline.
"""
from __future__ import annotations

import os
import select
import sys
import time

RELEASE_TIMEOUT = 3.0


def read_release_token(fd: int, timeout: float = RELEASE_TIMEOUT) -> bool:
    """Exactly b'G' then EOF; no unaudited continuation with a live writer."""
    if type(fd) is not int or fd < 3 or not (0 < timeout <= 30):
        return False
    deadline = time.monotonic() + timeout
    payload = bytearray()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                return False
            chunk = os.read(fd, 2)
            if not chunk:
                return payload == b'G'
            payload.extend(chunk)
            if len(payload) > 1:
                return False
    except (OSError, ValueError):
        return False


def main() -> int:
    if not sys.platform.startswith('linux') or len(sys.argv) != 2 or not sys.argv[1].isdecimal():
        return 79
    fd = int(sys.argv[1])
    if fd < 3:
        return 79
    try:
        accepted = read_release_token(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if not accepted:
        return 78
    # The registered fixture is fixed and receives no model-selected command.
    os.execv(sys.executable, [sys.executable, '-m', 'cognitum.alpha_native_worker'])
    return 77


if __name__ == '__main__':
    sys.exit(main())
