"""P46R5 host-side fixed-worker watchkeeper handoff.

The trusted local *test* host creates a cgroup before spawning ANY worker,
arms an out-of-cgroup watchkeeper first, and only then releases the worker.
A real deployment requires an independently managed watchkeeper service and
policy/authentication integration; this is not a general Lu execution path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import select
import stat
import subprocess
import sys
import tempfile

from .host_surviving_watchkeeper import (
    SCHEMA, WatchkeeperDenied, kernel_cgroup_dirfd,
)

ROOT = Path(__file__).resolve().parent.parent


class ArmedWatchkeeper:
    def __init__(self, proc, lease_writefd: int, jobid: str,
                 evidence_dir: Path, scope_device: int, scope_inode: int):
        self.proc = proc
        self.lease_writefd = lease_writefd
        self.jobid = jobid
        self.evidence_dir = evidence_dir
        self.scope_device = scope_device
        self.scope_inode = scope_inode

    @property
    def receipt_path(self) -> Path:
        return self.evidence_dir / f'p46r5-{self.jobid}.json'

    def close_lease(self) -> None:
        if self.lease_writefd >= 0:
            os.close(self.lease_writefd)
            self.lease_writefd = -1

    def await_cleanup(self, *, timeout: float = 10.0,
                      expected_trigger: str = 'LEASE_CLOSED') -> dict:
        """Fail closed unless the independent watchdog actually observed empty.

        This is a local unauthenticated JSON receipt, not production attestation.
        """
        self.close_lease()
        try:
            code = self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise WatchkeeperDenied('WATCHKEEPER_DID_NOT_FINISH') from exc
        if code != 0:
            raise WatchkeeperDenied('WATCHKEEPER_FAILED')
        try:
            raw = self.receipt_path.read_bytes()
            if len(raw) > 4096:
                raise WatchkeeperDenied('RECEIPT_TOO_LARGE')
            data = _strict_receipt(raw)
        except (OSError, ValueError) as exc:
            raise WatchkeeperDenied('MISSING_OR_INVALID_WATCHKEEPER_RECEIPT') from exc
        required = {'schema', 'job_id', 'watchkeeper_pid',
                    'observed_parent_pid', 'scope_device', 'scope_inode',
                    'trigger', 'ready_before_trigger', 'kernel_cgroup2_verified',
                    'cgroup_kill_written', 'subtree_empty', 'status', 'elapsed_ms',
                    'production_authorized', 'independent_attestation',
                    'watchkeeper_survived_its_own_crash'}
        if (type(data) is not dict or set(data) != required
                or data.get('schema') != SCHEMA
                or data.get('job_id') != self.jobid
                or type(data.get('watchkeeper_pid')) is not int
                or data['watchkeeper_pid'] != self.proc.pid
                or type(data.get('observed_parent_pid')) is not int
                or data['observed_parent_pid'] != os.getpid()
                or type(data.get('scope_device')) is not int
                or data['scope_device'] != self.scope_device
                or type(data.get('scope_inode')) is not int
                or data['scope_inode'] != self.scope_inode
                or type(data.get('elapsed_ms')) is not int
                or not 0 <= data['elapsed_ms'] <= 120000
                or data.get('trigger') != expected_trigger
                or data.get('status') != 'KERNEL_TREE_CLEARED'
                or any(data.get(name) is not True for name in
                       ('ready_before_trigger', 'kernel_cgroup2_verified',
                        'cgroup_kill_written', 'subtree_empty'))
                or data.get('production_authorized') is not False
                or data.get('independent_attestation') is not False
                or data.get('watchkeeper_survived_its_own_crash') is not False):
            raise WatchkeeperDenied('CONTRADICTORY_WATCHKEEPER_RECEIPT')
        return data


def _strict_receipt(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_RECEIPT_KEY')
            result[key] = value
        return result
    def reject_constant(token):
        raise ValueError('NON_FINITE_RECEIPT_VALUE')
    data = json.loads(raw, object_pairs_hook=unique,
                      parse_constant=reject_constant)
    if type(data) is not dict:
        raise ValueError('RECEIPT_NOT_OBJECT')
    return data


def arm_watchkeeper(scope_path: Path, *, evidence_dir: Path | None = None,
                    ready_timeout: float = 5.0) -> ArmedWatchkeeper:
    """No worker may be launched if this exact handoff doesn't complete."""
    if not sys.platform.startswith('linux') or not hasattr(os, 'pidfd_open'):
        raise WatchkeeperDenied('LINUX_PIDFD_REQUIRED')
    if not 0 < ready_timeout <= 10:
        raise WatchkeeperDenied('BAD_ARM_TIMEOUT')
    path = Path(scope_path)
    if path.is_symlink():
        raise WatchkeeperDenied('SYMLINK_SCOPE')
    if evidence_dir is None:
        # Local-only fallback. A real host must supply its durable, private
        # trusted state directory; temporary directories are not a restart log.
        evidence_dir = Path(tempfile.mkdtemp(prefix='cognitum-p46r5-'))
    evidence_dir = Path(evidence_dir)
    scope_fd = -1
    evidence_fd = -1
    lease_read = lease_write = -1
    ready_read = ready_write = -1
    proc = None
    try:
        scope_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY
                           | os.O_CLOEXEC | os.O_NOFOLLOW)
        if not kernel_cgroup_dirfd(scope_fd):
            raise WatchkeeperDenied('NOT_KERNEL_CGROUP_SCOPE')
        evidence_fd = os.open(evidence_dir, os.O_RDONLY | os.O_DIRECTORY
                              | os.O_CLOEXEC | os.O_NOFOLLOW)
        owner = os.fstat(evidence_fd)
        if (not stat.S_ISDIR(owner.st_mode) or owner.st_uid != os.geteuid()
                or owner.st_mode & 0o077):
            raise WatchkeeperDenied('UNTRUSTED_RECEIPT_DIRECTORY')
        scope_identity = os.fstat(scope_fd)
        lease_read, lease_write = os.pipe2(os.O_CLOEXEC)
        ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
        jobid = secrets.token_hex(16)
        proc = subprocess.Popen(
            [sys.executable, '-m', 'cognitum.host_surviving_watchkeeper',
             str(lease_read), str(scope_fd), str(evidence_fd),
             str(ready_write), str(os.getpid()), jobid],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
            close_fds=True,
            pass_fds=(lease_read, scope_fd, evidence_fd, ready_write),
        )
        for fd in (lease_read, scope_fd, evidence_fd, ready_write):
            os.close(fd)
        lease_read = scope_fd = evidence_fd = ready_write = -1
        if not select.select([ready_read], [], [], ready_timeout)[0]:
            raise WatchkeeperDenied('WATCHKEEPER_ARM_TIMEOUT')
        if os.read(ready_read, 2) != b'R' or proc.poll() is not None:
            raise WatchkeeperDenied('WATCHKEEPER_ARM_REJECTED')
        os.close(ready_read)
        ready_read = -1
        handle = ArmedWatchkeeper(proc, lease_write, jobid, evidence_dir,
                                  scope_identity.st_dev, scope_identity.st_ino)
        lease_write = -1
        return handle
    except (OSError, WatchkeeperDenied):
        # The host caller MUST also kill its scope. No worker may start.
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
        raise
    finally:
        for fd in (scope_fd, evidence_fd, lease_read, lease_write,
                   ready_read, ready_write):
            if fd >= 0:
                try: os.close(fd)
                except OSError: pass
