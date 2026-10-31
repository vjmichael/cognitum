"""Developer-only cgroup v2 launch experiment for the *fixed* alpha worker.

This is NOT Lu host policy or a sandbox implementation. It cannot run in a
read-only/undelegated cgroup environment. There is no arbitrary executable,
argument, path, or command input; the only payload is bounded Protobuf bytes.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import select
import time
import subprocess
import sys

from .alpha_native import MAX_FRAME
from .cgroup2_contract import ContainmentUnavailable, FixtureCgroupScope

ROOT = Path(__file__).resolve().parent.parent
MAX_OUTPUT = 16384 + 4


def _birth_ticks(pid: int) -> int:
    # A pidfd pins identity, while /proc start time detects PID reuse around
    # the cgroup.procs numerical-PID attach. This is not an atomic kernel API.
    raw = (Path('/proc') / str(pid) / 'stat').read_text(encoding='ascii')
    return int(raw[raw.rfind(')') + 2:].split()[19])


def _pidfd_exited(pidfd: int) -> bool:
    poll = select.poll()
    poll.register(pidfd, select.POLLIN | select.POLLHUP)
    return bool(poll.poll(0))


def _require_same_attached_worker(proc, pidfd: int, born: int, scope) -> None:
    """Reject stale/replaced PIDs and a dead worker before release.

    These checks close common fixed-fixture races; they do NOT atomically
    establish hostile-worker containment or authorize Lu execution.
    """
    if proc.pid not in scope.members():
        raise ContainmentUnavailable('WORKER_NOT_IN_KERNEL_CGROUP')
    try:
        same_identity = _birth_ticks(proc.pid) == born
    except (OSError, IndexError, ValueError):
        same_identity = False
    if not same_identity or _pidfd_exited(pidfd) or proc.poll() is not None:
        raise ContainmentUnavailable('WORKER_IDENTITY_CHANGED_BEFORE_RELEASE')


def execute_fixed_in_cgroup(frame: bytes, *, delegated_root='/sys/fs/cgroup') -> dict:
    """Attach a gated fixed worker BEFORE it receives its execution token.

    The return value describes developer process control only; it explicitly
    makes no claim about untrusted plugin isolation or Lu authorization.
    """
    if type(frame) is not bytes or not 4 <= len(frame) <= MAX_FRAME + 4:
        raise ValueError('INVALID_BOUNDED_PROTOBUF_FRAME')
    # No worker process can start before this succeeds on *kernel cgroup2*.
    scope = FixtureCgroupScope(delegated_root)
    scope.create()
    proc = None
    pidfd = None
    reader = None
    writer = None
    complete = False
    try:
        reader, writer = os.pipe2(os.O_CLOEXEC)
        proc = subprocess.Popen([sys.executable, '-m', 'cognitum.gated_alpha_worker', str(reader), str(os.getpid())],
                                cwd=ROOT, pass_fds=(reader,), start_new_session=True,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=0)
        os.close(reader)
        reader = None
        pidfd = os.pidfd_open(proc.pid)
        try:
            born = _birth_ticks(proc.pid)
        except (OSError, IndexError, ValueError) as exc:
            raise ContainmentUnavailable('WORKER_IDENTITY_UNAVAILABLE') from exc
        if _pidfd_exited(pidfd):
            raise ContainmentUnavailable('WORKER_EXITED_BEFORE_ATTACH')
        scope.attach_before_release(proc.pid)
        _require_same_attached_worker(proc, pidfd, born, scope)
        # The fixed worker additionally waits for writer EOF, rejecting an
        # accidentally inherited or retained release handle.
        os.write(writer, b'G')
        os.close(writer)
        writer = None
        try:
            stdout, stderr = proc.communicate(frame, timeout=7.5)
        except subprocess.TimeoutExpired as exc:
            raise ContainmentUnavailable('WORKER_TIMEOUT') from exc
        if len(stdout) > MAX_OUTPUT or stderr or proc.returncode != 0:
            raise ContainmentUnavailable('FIXED_WORKER_DID_NOT_SUCCEED')
        # Even after the direct worker exits, independently kill the whole
        # cgroup: a surviving descendant would not be allowed to outlive it.
        complete = scope.kill_and_verify_empty(timeout=5.0)
        if not complete:
            raise ContainmentUnavailable('CGROUP_NOT_EMPTY_AFTER_KILL')
        poll = select.poll()
        poll.register(pidfd, select.POLLIN | select.POLLHUP)
        if not poll.poll(0):
            raise ContainmentUnavailable('WORKER_PIDFD_NOT_EXITED')
        return {
            'status': 'FIXED_FIXTURE_OBSERVED', 'worker_pid': proc.pid,
            'worker_exit': proc.returncode, 'cgroup_empty': complete,
            'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
            'stdout_bytes': len(stdout), 'untrusted_worker_authorized': False,
            'lu_integrated': False, 'production_sandbox_verified': False,
        }
    finally:
        if writer is not None:
            os.close(writer)  # No permission token on an attachment failure.
        if reader is not None:
            os.close(reader)
        # cgroup.kill is the primary descendant-tree cleanup; process groups
        # are deliberately NOT accepted as an escape-proof boundary.
        if scope.path is not None:
            if not complete:
                scope.kill_and_verify_empty(timeout=3.0)
            try:
                scope.remove_empty()
            except OSError:
                pass  # Do not claim containment if a scope remains populated.
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try: proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=3)
        if pidfd is not None:
            os.close(pidfd)
