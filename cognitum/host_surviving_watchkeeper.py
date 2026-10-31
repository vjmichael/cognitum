"""P46R5: experimental Linux host-surviving cgroup2 cleanup watchkeeper.

This process is deliberately outside the fixed worker's cgroup.  It survives
SIGKILL of its Python launching parent and observes that parent's pidfd, even
if an unrelated process retains the lease pipe.  On death or lease closure it
writes cgroup.kill and verifies cgroup.events populated=0.

A watchdog is not a system service manager: its *own* crash, revocation of its
cgroup delegation, and hostile worker cgroup migration are NOT solved here.
This is for a fixed Cognitum worker fixture, not arbitrary plugin admission.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import select
import stat
import sys
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = 'cognitum.host-surviving-cgroup-watchkeeper.v1'
CGROUP2_MAGIC = 0x63677270
RECEIPT_LIMIT = 4096
MAX_LIFETIME_SECONDS = 60.0   # fixed-worker experiment only
KILL_POLL_SECONDS = 5.0
_READY = b'R'
_ALLOWED_ID = re.compile(r'[0-9a-f]{32}\Z')

class WatchkeeperDenied(RuntimeError):
    """Never release a worker when a watchkeeper cannot be armed."""


@dataclass(frozen=True)
class CleanupObservation:
    trigger: str
    kernel_cgroup_v2: bool
    kill_written: bool
    subtree_empty: bool
    elapsed_ms: int
    status: str


def kernel_cgroup_dirfd(fd: int) -> bool:
    """Use fstatfs on an inherited directory FD, not a path under /tmp."""
    if type(fd) is not int or fd < 3 or not sys.platform.startswith('linux'):
        return False
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            return False
        libc = ctypes.CDLL(None, use_errno=True)
        raw = ctypes.create_string_buffer(512)
        if libc.fstatfs(ctypes.c_int(fd), ctypes.byref(raw)) != 0:
            return False
        return ctypes.c_long.from_buffer(raw).value == CGROUP2_MAGIC
    except (OSError, ValueError):
        return False


def _open_scopefile(scope_fd: int, name: str, flags: int) -> int:
    if name not in ('cgroup.kill', 'cgroup.events', 'cgroup.procs'):
        raise WatchkeeperDenied('UNEXPECTED_CGROUP_FILE')
    return os.open(name, flags | os.O_CLOEXEC | os.O_NOFOLLOW,
                   dir_fd=scope_fd)


def _read_scopefile(scope_fd: int, name: str) -> str:
    fd = _open_scopefile(scope_fd, name, os.O_RDONLY)
    try:
        result = os.read(fd, 4097)
        if len(result) > 4096:
            raise WatchkeeperDenied('CGROUP_READ_TOO_LARGE')
        return result.decode('ascii', 'strict')
    finally:
        os.close(fd)


def _populated(scope_fd: int) -> bool:
    fields = {}
    for line in _read_scopefile(scope_fd, 'cgroup.events').splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[0] in fields:
            raise WatchkeeperDenied('MALFORMED_CGROUP_EVENTS')
        fields[parts[0]] = parts[1]
    if fields.get('populated') not in ('0', '1'):
        raise WatchkeeperDenied('MISSING_POPULATED_EVENT')
    return fields['populated'] == '1'


def kill_and_observe(scope_fd: int, *, timeout: float = KILL_POLL_SECONDS,
                     require_real_kernel: bool = True) -> tuple[bool, bool]:
    """Returns (kill_written, observed_empty). No synthetics allowed in service.

    Tests may call this with a disposable fake directory only by passing
    require_real_kernel=False *directly* (not exposed by CLI/watchkeeper_main).
    """
    if require_real_kernel and not kernel_cgroup_dirfd(scope_fd):
        return False, False
    if not 0 < timeout <= 30:
        return False, False
    try:
        with os.fdopen(_open_scopefile(scope_fd, 'cgroup.kill', os.O_WRONLY),
                       'wb', closefd=True) as writer:
            writer.write(b'1')
            writer.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _populated(scope_fd):
                return True, True
            time.sleep(.03)
        return True, False
    except (OSError, UnicodeError, WatchkeeperDenied):
        return False, False


def monitor_parent(parent_pidfd: int, lease_readfd: int, *,
                   timeout: float = MAX_LIFETIME_SECONDS) -> str:
    """Monitor two independent signals; pidfd prevents leaked lease-writer bypass.

    There is no callback execution in this monitoring loop. The production
    watchdog always invokes kernel cgroup.kill after this returns.
    """
    if not 0 < timeout <= MAX_LIFETIME_SECONDS:
        raise WatchkeeperDenied('INVALID_WATCH_TIMEOUT')
    poller = select.poll()
    poller.register(parent_pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    poller.register(lease_readfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    deadline = time.monotonic() + timeout
    while True:
        # Check parent FIRST, even if the lease pipe is still held by a child.
        check = select.poll()
        check.register(parent_pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if check.poll(0):
            return 'HOST_PIDFD_EXITED'
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return 'HOST_LIFETIME_EXPIRED'
        for fd, event in poller.poll(min(500, max(1, int(remaining * 1000)))):
            if fd == parent_pidfd and event:
                return 'HOST_PIDFD_EXITED'
            if fd == lease_readfd and event:
                try:
                    byte = os.read(lease_readfd, 1)
                except OSError:
                    return 'LEASE_READ_ERROR'
                return 'LEASE_CLOSED' if byte == b'' else 'UNEXPECTED_LEASE_DATA'


def _write_receipt(dirfd: int, jobid: str, result: dict) -> None:
    if not _ALLOWED_ID.fullmatch(jobid):
        raise WatchkeeperDenied('INVALID_JOB_ID')
    info = os.fstat(dirfd)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise WatchkeeperDenied('UNTRUSTED_RECEIPT_DIRECTORY')
    data = json.dumps(result, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True).encode('ascii') + b'\n'
    if len(data) > RECEIPT_LIMIT:
        raise WatchkeeperDenied('RECEIPT_TOO_LARGE')
    final_name = f'p46r5-{jobid}.json'
    temporary = f'.{final_name}.{os.getpid()}.tmp'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=dirfd)
    try:
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
    finally:
        os.close(fd)
    # Hard-link creation is atomic and fails with EEXIST; os.rename would
    # silently overwrite an earlier receipt, undermining evidence integrity.
    try:
        os.link(temporary, final_name, src_dir_fd=dirfd, dst_dir_fd=dirfd,
                follow_symlinks=False)
        os.fsync(dirfd)
    finally:
        os.unlink(temporary, dir_fd=dirfd)
    os.fsync(dirfd)


def _watchkeeper_main(lease_fd: int, scope_fd: int, evidence_fd: int,
                      ready_fd: int, parent_pid: int, jobid: str) -> int:
    start = time.monotonic()
    parent_fd = -1
    kill_fd = -1
    trigger = 'BOOTSTRAP_REJECTED'
    kernel = False
    written = False
    empty = False
    ready = False
    try:
        scope_stat = os.fstat(scope_fd)
        scope_device, scope_inode = scope_stat.st_dev, scope_stat.st_ino
    except OSError:
        scope_device, scope_inode = -1, -1
    try:
        if not _ALLOWED_ID.fullmatch(jobid):
            raise WatchkeeperDenied('INVALID_JOB_ID')
        if not kernel_cgroup_dirfd(scope_fd):
            raise WatchkeeperDenied('NOT_REAL_CGROUP2_FD')
        kernel = True
        if os.getppid() != parent_pid:
            raise WatchkeeperDenied('PARENT_ALREADY_EXITED')
        if not hasattr(os, 'pidfd_open'):
            raise WatchkeeperDenied('PIDFD_UNAVAILABLE')
        parent_fd = os.pidfd_open(parent_pid)
        if os.getppid() != parent_pid:
            raise WatchkeeperDenied('PARENT_CHANGED_DURING_ARM')
        # Verify the watchdog is outside the worker cgroup, and that
        # cgroup.kill can be opened for writing before worker admission.
        members = {int(s) for s in _read_scopefile(scope_fd, 'cgroup.procs').split()}
        if os.getpid() in members:
            raise WatchkeeperDenied('WATCHKEEPER_INSIDE_WORKER_CGROUP')
        kill_fd = _open_scopefile(scope_fd, 'cgroup.kill', os.O_WRONLY)
        _populated(scope_fd)  # Ensure cgroup.events is readable and parseable.
        os.write(ready_fd, _READY)
        ready = True
        trigger = monitor_parent(parent_fd, lease_fd)
    except (OSError, ValueError, UnicodeError, WatchkeeperDenied) as exc:
        trigger = 'ARM_OR_MONITOR_FAILURE_' + type(exc).__name__
    finally:
        try:
            os.close(ready_fd)
        except OSError:
            pass
        if kernel:
            # We keep a live kernel cgroup FD. Never report success without
            # seeing its recursive populated event become zero.
            # This also attempts cleanup on a bootstrap failure.
            written, empty = kill_and_observe(scope_fd)
        result = {
            'schema': SCHEMA, 'job_id': jobid,
            'watchkeeper_pid': os.getpid(), 'observed_parent_pid': parent_pid,
            'scope_device': scope_device, 'scope_inode': scope_inode,
            'trigger': trigger, 'ready_before_trigger': ready,
            'kernel_cgroup2_verified': kernel,
            'cgroup_kill_written': written, 'subtree_empty': empty,
            'status': 'KERNEL_TREE_CLEARED' if ready and written and empty else 'FAILED_CLOSED',
            'elapsed_ms': max(0, round((time.monotonic()-start)*1000)),
            'production_authorized': False, 'independent_attestation': False,
            'watchkeeper_survived_its_own_crash': False,
        }
        try:
            _write_receipt(evidence_fd, jobid, result)
        except (OSError, ValueError, WatchkeeperDenied):
            pass  # A missing receipt is failure, never implied success.
        for fd in (kill_fd, parent_fd, scope_fd, lease_fd, evidence_fd):
            if fd >= 0:
                try: os.close(fd)
                except OSError: pass
    return 0 if result['status'] == 'KERNEL_TREE_CLEARED' else 1


def main(argv: list[str]) -> int:
    if not sys.platform.startswith('linux') or len(argv) != 6:
        return 90
    lease, scope, evidence, ready, parent = argv[:5]
    jobid = argv[5]
    if (not all(v.isdecimal() for v in (lease, scope, evidence, ready, parent))
            or not _ALLOWED_ID.fullmatch(jobid)):
        return 90
    fds = list(map(int, (lease, scope, evidence, ready)))
    if any(fd < 3 for fd in fds) or len(set(fds)) != len(fds) or int(parent) <= 1:
        return 90
    return _watchkeeper_main(*fds, int(parent), jobid)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
