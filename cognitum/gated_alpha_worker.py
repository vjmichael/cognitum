"""Fixed-worker release barrier for the cgroup2 test fixture (Linux only).

This barrier does not confer host authority or OS sandboxing. The one-byte
release is accepted only after the *write side has closed*; extra tokens,
truncation, and retained inherited writers fail closed under a deadline.
"""
from __future__ import annotations

import ctypes
import os
import select
import signal
import sys
import time

RELEASE_TIMEOUT = 3.0
PR_SET_PDEATHSIG = 1


def arm_parent_death_sigkill(expected_parent_pid: int) -> bool:
    """Guard the real fixed worker across exec; never grants authority.

    Linux prctl is inherited across normal non-privileged exec, but not across
    every credential transition. This does not contain a hostile descendant or
    stop a worker with permission to clear its own parent-death signal.
    """
    if not sys.platform.startswith('linux') or type(expected_parent_pid) is not int or expected_parent_pid <= 1:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        return False
    # Parent may already have died in the fork/exec -> prctl race window.
    return os.getppid() == expected_parent_pid



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
    if not sys.platform.startswith('linux') or len(sys.argv) != 3 or not all(s.isdecimal() for s in sys.argv[1:]):
        return 79
    fd = int(sys.argv[1])
    expected_parent_pid = int(sys.argv[2])
    if fd < 3 or expected_parent_pid <= 1:
        return 79
    if not arm_parent_death_sigkill(expected_parent_pid):
        return 80
    try:
        accepted = read_release_token(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if not accepted:
        return 78
    # Recheck parent identity after EOF and just before the fixed worker exec.
    if os.getppid() != expected_parent_pid:
        return 81
    # The registered fixture is fixed and receives no model-selected command.
    os.execv(sys.executable, [sys.executable, '-m', 'cognitum.alpha_native_worker'])
    return 77


if __name__ == '__main__':
    sys.exit(main())
