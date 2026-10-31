"""P46R6: fail-closed, durable *restart* reconciliation for fixed Cognitum workers.

A trusted service manager must launch this separately on startup and after
watchkeeper failures. This module is NOT a system service, OS sandbox, Lu host
permission engine, or independent attestation. Production cleanup requires real
kernel cgroup v2 and an exact, private, immutable prelaunch record. A normal
filesystem fixture cannot be used via the public CLI.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
from pathlib import Path
from typing import Any

from .host_surviving_watchkeeper import (
    WatchkeeperDenied, kernel_cgroup_dirfd, kill_and_observe,
)

SCHEMA = 'cognitum.p46r6-durable-recovery.v1'
OBSERVATION_SCHEMA = 'cognitum.p46r6-recovery-attempt.v1'
_JOB = re.compile(r'[0-9a-f]{32}\Z')
_SCOPE = re.compile(r'cognitum-fixture-[0-9a-f]{24}\Z')
_PENDING = re.compile(r'p46r6-pending-([0-9a-f]{32})\.json\Z')
MAX_BYTES = 4096
MAX_SCAN = 256


class RecoveryDenied(RuntimeError):
    """A missing or contradictory prerequisite must not imply cleanup."""


def _private_fd(path: Path) -> int:
    if not path.is_absolute() or path.is_symlink():
        raise RecoveryDenied('STATE_PATH_UNTRUSTED')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise RecoveryDenied('STATE_DIRECTORY_UNAVAILABLE') from exc
    s = os.fstat(fd)
    if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o077:
        os.close(fd)
        raise RecoveryDenied('STATE_DIRECTORY_NOT_PRIVATE')
    return fd


def _kernel_root_fd(root: Path) -> int:
    if not root.is_absolute() or root.is_symlink():
        raise RecoveryDenied('ROOT_PATH_UNTRUSTED')
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise RecoveryDenied('KERNEL_ROOT_UNAVAILABLE') from exc
    if not kernel_cgroup_dirfd(fd):
        os.close(fd)
        raise RecoveryDenied('NOT_KERNEL_CGROUP2')
    return fd


def _scope_fd(root_fd: int, name: str) -> int:
    if type(name) is not str or _SCOPE.fullmatch(name) is None:
        raise RecoveryDenied('UNTRUSTED_SCOPE_NAME')
    try:
        result = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=root_fd)
    except OSError as exc:
        raise RecoveryDenied('SCOPE_MISSING_OR_UNTRUSTED') from exc
    if not kernel_cgroup_dirfd(result):
        os.close(result)
        raise RecoveryDenied('SCOPE_NOT_KERNEL_CGROUP2')
    return result


def _boot_id() -> str:
    try:
        val = Path('/proc/sys/kernel/random/boot_id').read_text(encoding='ascii').strip()
    except OSError as exc:
        raise RecoveryDenied('BOOT_ID_UNAVAILABLE') from exc
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', val):
        raise RecoveryDenied('INVALID_BOOT_ID')
    return val


def _json_bytes(value: dict[str, Any]) -> bytes:
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii') + b'\n'
    if len(raw) > MAX_BYTES:
        raise RecoveryDenied('RECORD_TOO_LARGE')
    return raw


def _create_once(fd: int, name: str, value: dict[str, Any]) -> None:
    """Write-and-fsync a complete immutable record; hardlink fails on replay."""
    if not re.fullmatch(r'p46r6-(?:pending|closed|attempt)-[0-9a-f-]{32,70}\.json', name):
        raise RecoveryDenied('INVALID_RECORD_NAME')
    raw = _json_bytes(value)
    tmp = f'.{name}.{os.getpid()}.{time.monotonic_ns()}.tmp'
    handle = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=fd)
    try:
        remaining = memoryview(raw)
        while remaining:
            written = os.write(handle, remaining)
            if written <= 0:
                raise RecoveryDenied('ZERO_BYTE_WRITE')
            remaining = remaining[written:]
        os.fsync(handle)
    finally:
        os.close(handle)
    try:
        os.link(tmp, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        os.fsync(fd)
    finally:
        os.unlink(tmp, dir_fd=fd)
    os.fsync(fd)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for k, v in pairs:
        if k in obj:
            raise RecoveryDenied('DUPLICATE_RECORD_KEY')
        obj[k] = v
    return obj


def _invalid_constant(_: str) -> None:
    raise RecoveryDenied('NONFINITE_RECORD_VALUE')


def _read_record(fd: int, name: str) -> dict[str, Any]:
    if not _PENDING.fullmatch(name):
        raise RecoveryDenied('INVALID_PENDING_NAME')
    try:
        h = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        try:
            item = os.fstat(h)
            if not stat.S_ISREG(item.st_mode) or item.st_nlink != 1 or item.st_mode & 0o077:
                raise RecoveryDenied('UNTRUSTED_RECORD_MODE')
            data = os.read(h, MAX_BYTES + 1)
        finally:
            os.close(h)
    except OSError as exc:
        raise RecoveryDenied('RECORD_READ_FAILED') from exc
    if len(data) > MAX_BYTES:
        raise RecoveryDenied('RECORD_TOO_LARGE')
    try:
        record = json.loads(data, object_pairs_hook=_unique,
                            parse_constant=_invalid_constant)
    except (UnicodeError, ValueError) as exc:
        raise RecoveryDenied('MALFORMED_RECORD') from exc
    if type(record) is not dict:
        raise RecoveryDenied('RECORD_NOT_OBJECT')
    required = {'schema', 'job_id', 'scope_name', 'root_device', 'root_inode',
                'scope_device', 'scope_inode', 'boot_id', 'host_pid',
                'watchkeeper_pid', 'production_authorized'}
    jobid = _PENDING.fullmatch(name).group(1)
    if (set(record) != required or record.get('schema') != SCHEMA
            or record.get('job_id') != jobid
            or not isinstance(record.get('scope_name'), str)
            or not _SCOPE.fullmatch(record['scope_name'])
            or any(type(record.get(k)) is not int or record[k] <= 0 for k in
                   ('root_device', 'root_inode', 'scope_device', 'scope_inode',
                    'host_pid', 'watchkeeper_pid'))
            or type(record.get('boot_id')) is not str
            or record.get('production_authorized') is not False):
        raise RecoveryDenied('CONTRADICTORY_PENDING_RECORD')
    return record


def record_before_worker_release(state_dir: Path, root: Path, scope: Path,
                                 jobid: str, host_pid: int,
                                 watchkeeper_pid: int) -> dict[str, Any]:
    """Durably record exact cgroup identity BEFORE any worker release token.

    A historical record does not authorize starting a worker or any extension.
    """
    if not sys.platform.startswith('linux'):
        raise RecoveryDenied('LINUX_REQUIRED')
    if type(jobid) is not str or not _JOB.fullmatch(jobid):
        raise RecoveryDenied('INVALID_JOB_ID')
    if (type(host_pid) is not int or host_pid != os.getpid()
            or type(watchkeeper_pid) is not int or watchkeeper_pid <= 1):
        raise RecoveryDenied('UNTRUSTED_PROCESS_IDENTITIES')
    root, scope = Path(root), Path(scope)
    if scope.parent != root or not _SCOPE.fullmatch(scope.name) or scope.is_symlink():
        raise RecoveryDenied('SCOPE_NOT_EXACT_CHILD')
    state_fd = _private_fd(Path(state_dir))
    root_fd = -1
    scope_fd = -1
    try:
        root_fd = _kernel_root_fd(root)
        scope_fd = _scope_fd(root_fd, scope.name)
        a, b = os.fstat(root_fd), os.fstat(scope_fd)
        record = {
            'schema': SCHEMA, 'job_id': jobid, 'scope_name': scope.name,
            'root_device': a.st_dev, 'root_inode': a.st_ino,
            'scope_device': b.st_dev, 'scope_inode': b.st_ino,
            'boot_id': _boot_id(), 'host_pid': host_pid,
            'watchkeeper_pid': watchkeeper_pid, 'production_authorized': False,
        }
        _create_once(state_fd, f'p46r6-pending-{jobid}.json', record)
        return record
    finally:
        if scope_fd >= 0: os.close(scope_fd)
        if root_fd >= 0: os.close(root_fd)
        os.close(state_fd)


def mark_closed_after_verified_cleanup(state_dir: Path, jobid: str) -> dict[str, Any]:
    """Only the trusted host calls this AFTER receipt validation and scope removal.

    The closed marker avoids repeated crash recovery for a normally completed
    fixture. It is a local host statement, never independent attestation.
    """
    if type(jobid) is not str or not _JOB.fullmatch(jobid):
        raise RecoveryDenied('INVALID_JOB_ID')
    fd = _private_fd(Path(state_dir))
    try:
        record = _read_record(fd, f'p46r6-pending-{jobid}.json')
        result = {
            'schema': OBSERVATION_SCHEMA, 'job_id': jobid,
            'status': 'HOST_REPORTED_CLOSED_UNATTESTED',
            'root_device': record['root_device'], 'root_inode': record['root_inode'],
            'scope_device': record['scope_device'], 'scope_inode': record['scope_inode'],
            'production_authorized': False, 'independent_attestation': False,
        }
        _create_once(fd, f'p46r6-closed-{jobid}.json', result)
        return result
    finally:
        os.close(fd)


def _closed(fd: int, record: dict[str, Any]) -> bool:
    name = f"p46r6-closed-{record['job_id']}.json"
    try:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
    except FileNotFoundError:
        return False
    try:
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
            raise RecoveryDenied('UNTRUSTED_CLOSED_RECORD')
        raw = os.read(handle, MAX_BYTES + 1)
    finally:
        os.close(handle)
    if len(raw) > MAX_BYTES:
        raise RecoveryDenied('CLOSED_RECORD_TOO_LARGE')
    try:
        obj = json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid_constant)
    except (UnicodeError, ValueError) as exc:
        raise RecoveryDenied('MALFORMED_CLOSED_RECORD') from exc
    expected = {
        'schema': OBSERVATION_SCHEMA, 'job_id': record['job_id'],
        'status': 'HOST_REPORTED_CLOSED_UNATTESTED',
        'root_device': record['root_device'], 'root_inode': record['root_inode'],
        'scope_device': record['scope_device'], 'scope_inode': record['scope_inode'],
        'production_authorized': False, 'independent_attestation': False,
    }
    if type(obj) is not dict or obj != expected:
        raise RecoveryDenied('CONTRADICTORY_CLOSED_RECORD')
    return True


def _deny_result(jobid: str, reason: str) -> dict[str, Any]:
    return {'schema': OBSERVATION_SCHEMA, 'job_id': jobid,
            'status': 'FAILED_CLOSED', 'reason': reason,
            'kill_written': False, 'subtree_empty': False,
            'kernel_cgroup2_checked': False, 'production_authorized': False,
            'independent_attestation': False}


def reconcile_job(state_dir: Path, delegated_root: Path, jobid: str,
                  *, execute: bool = False, timeout: float = 5.0) -> dict[str, Any]:
    """One bounded recovery attempt, no launch or unconditional success.

    `execute=False` is inspection-only. `execute=True` must use real cgroup2;
    test code can mock the kernel module functions, not an exposed bypass flag.
    """
    if type(jobid) is not str or not _JOB.fullmatch(jobid):
        raise RecoveryDenied('INVALID_JOB_ID')
    if type(execute) is not bool or not 0 < timeout <= 15:
        raise RecoveryDenied('INVALID_RECOVERY_OPTIONS')
    state_fd = _private_fd(Path(state_dir))
    root_fd = -1
    scope_fd = -1
    try:
        record = _read_record(state_fd, f'p46r6-pending-{jobid}.json')
        if _closed(state_fd, record):
            # Host closure is a local claim, not independent kernel evidence.
            return {'schema': OBSERVATION_SCHEMA, 'job_id': jobid,
                    'status': 'HOST_REPORTED_CLOSED_UNATTESTED',
                    'reason': 'NO_RECOVERY_ATTEMPT',
                    'kill_written': False, 'subtree_empty': False,
                    'kernel_cgroup2_checked': False, 'production_authorized': False,
                    'independent_attestation': False}
        if not execute:
            return {'schema': OBSERVATION_SCHEMA, 'job_id': jobid,
                    'status': 'INSPECTION_ONLY', 'reason': 'NOT_EXECUTED',
                    'kill_written': False, 'subtree_empty': False,
                    'kernel_cgroup2_checked': False, 'production_authorized': False,
                    'independent_attestation': False}
        reason = None
        checked = False
        written = empty = False
        try:
            if _boot_id() != record['boot_id']:
                raise RecoveryDenied('BOOT_ID_CHANGED')
            root_fd = _kernel_root_fd(Path(delegated_root))
            rs = os.fstat(root_fd)
            if (rs.st_dev, rs.st_ino) != (record['root_device'], record['root_inode']):
                raise RecoveryDenied('ROOT_IDENTITY_CHANGED')
            scope_fd = _scope_fd(root_fd, record['scope_name'])
            ss = os.fstat(scope_fd)
            if (ss.st_dev, ss.st_ino) != (record['scope_device'], record['scope_inode']):
                raise RecoveryDenied('SCOPE_IDENTITY_CHANGED')
            checked = True
            written, empty = kill_and_observe(scope_fd, timeout=timeout)
            if not (written and empty):
                raise RecoveryDenied('KERNEL_KILL_NOT_CONFIRMED')
            # Detect stale observation: independently re-read cgroup.events
            # and cgroup.procs from the same pinned directory descriptor.
            events_fd = os.open('cgroup.events', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=scope_fd)
            procs_fd = os.open('cgroup.procs', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                               dir_fd=scope_fd)
            try:
                events = os.read(events_fd, 4097)
                procs = os.read(procs_fd, 4097)
            finally:
                os.close(events_fd)
                os.close(procs_fd)
            lines = [line.split() for line in events.decode('ascii', 'strict').splitlines()]
            populated = [parts[1] for parts in lines if len(parts) == 2 and parts[0] == 'populated']
            if len(populated) != 1 or populated[0] != '0' or procs.strip():
                raise RecoveryDenied('FINAL_KERNEL_STATE_NOT_EMPTY')
            status = 'KERNEL_TREE_CLEARED_UNATTESTED'
            reason = 'KERNEL_KILL_AND_EMPTY_OBSERVED'
        except (RecoveryDenied, OSError, UnicodeError, WatchkeeperDenied) as exc:
            status = 'FAILED_CLOSED'
            reason = str(exc) if type(exc) is RecoveryDenied else type(exc).__name__
            # Keep observed write if post-write verification failed. It is never
            # enough on its own to grant a success claim.
        result = {
            'schema': OBSERVATION_SCHEMA, 'job_id': jobid,
            'status': status, 'reason': reason,
            'kill_written': bool(written), 'subtree_empty': bool(empty),
            'kernel_cgroup2_checked': checked, 'production_authorized': False,
            'independent_attestation': False,
        }
        # Durable, create-only attempt history; no rewrite of pending record.
        attempt = f'{time.monotonic_ns():x}'.zfill(32)[-32:]
        _create_once(state_fd, f'p46r6-attempt-{jobid}-{attempt}.json', result)
        return result
    finally:
        if scope_fd >= 0: os.close(scope_fd)
        if root_fd >= 0: os.close(root_fd)
        os.close(state_fd)


def reconcile_pending(state_dir: Path, delegated_root: Path, *, execute: bool = False,
                      max_records: int = MAX_SCAN) -> list[dict[str, Any]]:
    """Run after every watchkeeper supervisor restart; bounded and fail closed."""
    if type(max_records) is not int or not 1 <= max_records <= MAX_SCAN:
        raise RecoveryDenied('SCAN_LIMIT_INVALID')
    fd = _private_fd(Path(state_dir))
    try:
        names = sorted(n for n in os.listdir(fd) if n.startswith('p46r6-pending-'))
        if len(names) > max_records:
            raise RecoveryDenied('TOO_MANY_PENDING_RECORDS')
    finally:
        os.close(fd)
    results = []
    for name in names:
        match = _PENDING.fullmatch(name)
        if not match:
            results.append(_deny_result('unknown', 'INVALID_PENDING_FILENAME'))
            continue
        try:
            results.append(reconcile_job(state_dir, delegated_root, match.group(1), execute=execute))
        except (RecoveryDenied, OSError) as exc:
            results.append(_deny_result(match.group(1), str(exc)))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='P46R6 recovery inspector; no worker admission')
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--delegated-root', required=True)
    parser.add_argument('--execute', action='store_true', help='Attempt genuine kernel cgroup.kill (never mocked)')
    args = parser.parse_args(argv)
    try:
        if args.execute:
            # A CLI invoked with zero pending records must not succeed merely
            # because all([]) is true. Verify a *real writable* cgroup2 mount
            # before making any kernel-cleanup claim, even for an empty ledger.
            fd = _kernel_root_fd(Path(args.delegated_root))
            try:
                if os.fstatvfs(fd).f_flag & os.ST_RDONLY:
                    raise RecoveryDenied('CGROUP2_READ_ONLY')
            finally:
                os.close(fd)
        results = reconcile_pending(Path(args.state_dir), Path(args.delegated_root), execute=args.execute)
    except (RecoveryDenied, OSError) as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'reason': str(exc)}), flush=True)
        return 2
    print(json.dumps({'schema': OBSERVATION_SCHEMA, 'results': results}, sort_keys=True))
    if args.execute and all(r['status'] == 'KERNEL_TREE_CLEARED_UNATTESTED' for r in results):
        # Only an independently sampled, exact-kernel empty-subtree result is
        # eligible for a successful cleanup command exit. In particular a
        # host-authored closed marker is NOT kernel evidence, and must never
        # be interpreted as a successful recovery by an external supervisor.
        # This still does NOT grant worker admission or cryptographic attestation.
        return 0
    return 2 if args.execute else 0


if __name__ == '__main__':
    sys.exit(main())
