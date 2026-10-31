"""P46R7: separately supervised, fail-closed recovery-service entrypoint.

Does not start workers, grant admission, attest kernel security, or install a
service. On execution it MUST use a real writable cgroup2 root, exact durable
P46R6 records and a private per-UID exclusive lock. Inspection is explicitly
non-destructive and may use local test fixtures.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
from typing import Any

from . import host_recovery as rec

SCHEMA = 'cognitum.p46r7-recovery-service.v1'
MAX_INTERVAL = 60.0
STOP = False


class ServiceDenied(RuntimeError):
    pass


def _root_ready(root: Path) -> dict[str, Any]:
    """Read-only namespace/mount must deny kernel execution before scanning.

    Merely having cgroup.kill on the kernel hierarchy is NOT sufficient;
    actual worker cgroups must already have been assigned by trusted host.
    """
    fd = rec._kernel_root_fd(Path(root))
    try:
        s = os.fstat(fd)
        v = os.fstatvfs(fd)
        if v.f_flag & os.ST_RDONLY:
            raise ServiceDenied('CGROUP2_READ_ONLY')
        return {'root_device': s.st_dev, 'root_inode': s.st_ino,
                'root_writable_mount': True}
    finally:
        os.close(fd)


def _lock_state(state: Path) -> int:
    """Keep lock descriptor open for the duration of service, across scans."""
    fd = rec._private_fd(Path(state))
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise ServiceDenied('INVALID_STATE_DIRECTORY')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            raise ServiceDenied('ALREADY_RUNNING') from exc
        return fd
    except BaseException:
        os.close(fd)
        raise


def _cycle(state: Path, root: Path, *, inspection_only: bool) -> dict[str, Any]:
    if type(inspection_only) is not bool:
        raise ServiceDenied('INVALID_MODE')
    readiness = None if inspection_only else _root_ready(root)
    records = rec.reconcile_pending(state, root, execute=not inspection_only)
    if inspection_only:
        status = 'INSPECTION_ONLY'
    else:
        # A host-written "closed" marker is not an independently observed
        # empty subtree. Do not silently treat it as service success.
        if any(r['status'] == 'HOST_REPORTED_CLOSED_UNATTESTED' for r in records):
            status = 'UNATTESTED_CLOSURE_REQUIRES_REVIEW'
        elif any(r['status'] != 'KERNEL_TREE_CLEARED_UNATTESTED' for r in records):
            status = 'FAILED_CLOSED'
        else:
            status = 'NO_PENDING' if not records else 'KERNEL_OBSERVED_UNATTESTED'
    return {'schema': SCHEMA, 'status': status, 'records': records,
            'kernel_root': readiness, 'service_pid': os.getpid(),
            'production_authorized': False,
            'independent_attestation': False}


def run_service(state: Path, root: Path, *, inspection_only: bool = False,
                interval: float = 2.0, cycles: int | None = None,
                stop=lambda: STOP) -> list[dict[str, Any]]:
    """A manager (e.g. systemd) must restart this process after its own death.

    `cycles` is test-only, not exposed by public CLI. In production the main
    function remains alive until stopped and rechecks each pending record.
    """
    if (type(interval) not in (float, int) or not 0.05 <= interval <= MAX_INTERVAL
            or cycles is not None and (type(cycles) is not int or cycles < 1)):
        raise ServiceDenied('INVALID_SERVICE_OPTIONS')
    if not sys.platform.startswith('linux'):
        raise ServiceDenied('LINUX_REQUIRED')
    fd = _lock_state(state)
    # A manager-owned service ordinarily runs indefinitely. Never accumulate
    # one potentially large receipt per polling interval in process memory.
    # Explicit bounded test calls still return their complete cycle history.
    results = []
    cycle_count = 0
    try:
        while not stop():
            result = _cycle(state, root, inspection_only=inspection_only)
            cycle_count += 1
            if cycles is not None:
                results.append(result)
            print(json.dumps(result, sort_keys=True, separators=(',', ':')), flush=True)
            if result['status'] in ('FAILED_CLOSED', 'UNATTESTED_CLOSURE_REQUIRES_REVIEW'):
                raise ServiceDenied(result['status'])
            if cycles is not None and cycle_count >= cycles:
                break
            # Sleep small increments for prompt manager stop; no background work
            # after process exit or successful shutdown is ever promised.
            end = time.monotonic() + interval
            while time.monotonic() < end and not stop():
                time.sleep(min(0.05, max(0.0, end - time.monotonic())))
        return results
    finally:
        os.close(fd)


def _stop(_signum, _frame):
    global STOP
    STOP = True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='P46R7 local recovery service; no worker admission')
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--delegated-root', type=Path, required=True)
    parser.add_argument('--interval', type=float, default=2.0)
    parser.add_argument('--inspect-only', action='store_true', help='Never attempt kernel cleanup')
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        run_service(args.state_dir, args.delegated_root,
                    inspection_only=args.inspect_only, interval=args.interval)
        return 0
    except (rec.RecoveryDenied, ServiceDenied, OSError) as exc:
        print(json.dumps({'schema': SCHEMA, 'status': 'FAILED_CLOSED',
                          'reason': str(exc), 'production_authorized': False,
                          'independent_attestation': False}), flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())
