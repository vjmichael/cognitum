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
from .host_survivor_arm import arm_watchkeeper
from .host_surviving_watchkeeper import WatchkeeperDenied
from .host_recovery import record_before_worker_release, mark_closed_after_verified_cleanup

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


def execute_fixed_in_cgroup(frame: bytes, *, delegated_root='/sys/fs/cgroup', evidence_dir=None,
                            recovery_state_dir=None) -> dict:
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
    watchdog = None
    watchdog_receipt = None
    recovery_registered = False
    pidfd = None
    reader = None
    writer = None
    complete = False
    try:
        # P46R5: the watchdog must be armed OUTSIDE this cgroup, with a
        # kernel-valid cgroup.kill handle, before any worker process exists.
        # Its parent pidfd survives retained pipe writers and a host SIGKILL.
        watchdog = arm_watchkeeper(scope.path, evidence_dir=evidence_dir)
        # P46R6: optional experimental durable reconciliation mode.  A record
        # must be fsynced before a worker is even spawned, not merely before
        # the release token. Any journal error aborts the launch.
        if recovery_state_dir is not None:
            record_before_worker_release(
                recovery_state_dir, scope.root, scope.path, watchdog.jobid,
                os.getpid(), watchdog.proc.pid,
            )
            recovery_registered = True
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
        # Reject a watchkeeper that died between its READY handshake and the
        # worker's release. This narrows a race but does not replace a service
        # manager capable of recovering from later watchkeeper crashes.
        if watchdog.proc.poll() is not None:
            raise ContainmentUnavailable('WATCHKEEPER_EXITED_BEFORE_WORKER_RELEASE')
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
        # Cleanup is performed and witnessed by the out-of-cgroup watchkeeper.
        # There is no successful return without its real kernel observation.
        watchdog_receipt = watchdog.await_cleanup()
        complete = True
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
            'host_surviving_cleanup_observed': True,
            'durable_recovery_recorded': recovery_registered,
            'watchkeeper_receipt': str(watchdog.receipt_path),
            'watchkeeper_job_id': watchdog.jobid,
        }
    finally:
        if writer is not None:
            os.close(writer)  # No permission token on an attachment failure.
        if reader is not None:
            os.close(reader)
        # The independent watcher continues even if the launching host dies.
        # A live host also closes the lease on ANY error, enabling cleanup.
        if watchdog is not None and watchdog_receipt is None:
            watchdog.close_lease()
            try:
                watchdog_receipt = watchdog.await_cleanup(timeout=8.0)
            except WatchkeeperDenied:
                pass  # Emergency fallback below, never success admission.
        # If the watchdog failed or was never armed, attempt local cleanup too.
        if scope.path is not None:
            if watchdog_receipt is None:
                try:
                    complete = scope.kill_and_verify_empty(timeout=3.0)
                except ContainmentUnavailable:
                    complete = False
            if complete:
                try: scope.remove_empty()
                except OSError: pass  # Leave a populated/uncertain scope for recovery.
                # Only a verified watchkeeper receipt followed by actual scope
                # deletion may retire a durable pending job. An interrupted
                # host leaves the pending record for independent recovery.
                if recovery_registered and scope.path is None and watchdog_receipt is not None:
                    mark_closed_after_verified_cleanup(recovery_state_dir, watchdog.jobid)
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            try: proc.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=3)
        if pidfd is not None:
            os.close(pidfd)
