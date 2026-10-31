"""Experimental fixed Cognitum alpha-worker parent-lifetime guard (Linux only).

Strictly for local testing. PR_SET_PDEATHSIG is *not* descendant containment,
OS isolation, host authority, or protection against a malicious worker that
clears its own parent death signal. Never register as a generic code runner.
"""
from __future__ import annotations

import ctypes
import os
import signal
import sys

PDEATHSIG = 1
SENTINEL_READY = b'R'
TOKEN_RELEASE = b'G'


def enter_fixed_worker(expected_parent: int, release_fd: int, ready_fd: int) -> int:
    if not sys.platform.startswith('linux'):
        return 75
    # Only a trusted parent should construct these inherited descriptors.
    if (type(expected_parent) is not int or expected_parent <= 1
            or type(release_fd) is not int or release_fd < 3
            or type(ready_fd) is not int or ready_fd < 3
            or release_fd == ready_fd):
        return 76
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PDEATHSIG, signal.SIGKILL, 0, 0, 0) != 0:
        return 77
    # A supervisor can die after fork but before prctl. Re-check after
    # registration, before any release or real worker execution.
    if os.getppid() != expected_parent:
        return 78
    try:
        os.write(ready_fd, SENTINEL_READY)
        os.close(ready_fd)
        if os.read(release_fd, 2) != TOKEN_RELEASE:
            return 79
        os.close(release_fd)
    except OSError:
        return 80
    # Covers the last controllable window before exec. Parent-death SIGKILL
    # remains installed through a normal, non-setuid exec on Linux.
    if os.getppid() != expected_parent:
        return 81
    os.execv(sys.executable, [sys.executable, '-m', 'cognitum.alpha_native_worker'])
    return 82


def main(args: list[str]) -> int:
    if len(args) != 3 or any(not arg.isdecimal() for arg in args):
        return 76
    return enter_fixed_worker(*(int(x) for x in args))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
