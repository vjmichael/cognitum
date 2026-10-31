"""P48 Linux-only, non-production *reference* process lifecycle probe.

Runs fixed, unprivileged Python subprocesses. Does NOT exercise the unrecovered
P46 worker, confer sandboxing, or establish independently authenticated evidence.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
from typing import Callable

from .lifecycle_evidence import SCHEMA, evaluate_receipt

PDEATHSIG = 1
CHILD_SUBREAPER = 36
MAX_WAIT = 8.0
RUNNER_ID = 'p48-reference-linux-unattested-v1'

WORKER = r'''
import ctypes, os, signal, sys, time
parent = int(sys.argv[1])
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
    sys.exit(67)
# Explicit parent check closes the gap between process start and prctl setup.
if os.getppid() != parent:
    sys.exit(68)
print('READY', flush=True)
while True: time.sleep(0.1)
'''
SUPERVISOR = r'''
import subprocess, sys, os, ctypes, signal
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != int(sys.argv[3]): sys.exit(67)
mode = sys.argv[1]
if mode == 'launch':
    print('PRELAUNCH', flush=True)
    os.read(0, 1)
    sys.exit(69)
p = subprocess.Popen([sys.executable, '-u', '-c', sys.argv[2], str(os.getpid())],
                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
print('PID', p.pid, flush=True)
if p.stdout.readline() != b'READY\n': sys.exit(70)
print('READY', flush=True)
os.read(0, 1)
'''
TREE = r'''
import os, subprocess, sys, time, ctypes, signal
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != int(sys.argv[1]): sys.exit(67)
child_code = """
import os, sys, time, ctypes, signal
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != int(sys.argv[1]): sys.exit(67)
print('READY', flush=True)
while True: time.sleep(.1)
"""
p = subprocess.Popen([sys.executable, '-u', '-c', child_code, str(os.getpid())],
                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
if p.stdout.readline() != b'READY\n': sys.exit(70)
print('CHILD', p.pid, flush=True)
while True: time.sleep(.1)
'''
BACKPRESSURE = r'''
import os, sys, ctypes, signal
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != int(sys.argv[1]): sys.exit(67)
b = b'x' * 65536
while True: os.write(1, b)
'''


def _subreaper() -> None:
    if not sys.platform.startswith('linux') or not Path('/proc').is_dir():
        raise RuntimeError('P48 requires Linux and /proc')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
        raise RuntimeError(f'prctl child-subreaper failed (errno {ctypes.get_errno()})')


def _line(proc: subprocess.Popen[bytes], timeout: float = MAX_WAIT) -> str:
    if proc.stdout is None:
        return ''
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        return ''
    raw = proc.stdout.readline(96)
    return raw.decode('ascii', 'replace').strip()


def _reap(pid: int, timeout: float = MAX_WAIT) -> tuple[bool, int | None]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return False, None  # Exit is not evidence that this observer reaped it.
        if waited == pid:
            return True, status
        time.sleep(.02)
    return False, None


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _cleanup(proc: subprocess.Popen[bytes] | None, pids: list[int]) -> None:
    if proc is not None:
        # Only send signals to the fresh session created by this runner.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=.5)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait(timeout=.5)
        if proc.stdin: proc.stdin.close()
        if proc.stdout: proc.stdout.close()
        if proc.stderr: proc.stderr.close()
    for pid in pids:
        if _alive(pid):
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass
        _reap(pid, timeout=.7)  # Explicitly reap adopted descendants after cleanup kill.


def _case(probe_id: str, fn: Callable[[], tuple[int, bool, bool, list[int]]]) -> dict:
    try:
        pid, observed, reaped, survivors = fn()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        # Never assert observation or cleanup on unexpected failures.
        return {'id': probe_id, 'outcome': 'FAIL', 'observed': False,
                'worker_pid': 0,  # No verified worker PID. Deliberately FAIL the P47 gate.
                'reaped': False, 'live_descendant_pids': []}
    outcome = 'PASS' if observed and reaped and not survivors else 'FAIL'
    return {'id': probe_id, 'outcome': outcome, 'observed': observed,
            'worker_pid': pid, 'reaped': reaped, 'live_descendant_pids': survivors}


def _parent_death(mode: str, *, disable_pdeath: bool = False) -> tuple[int, bool, bool, list[int]]:
    proc = None
    worker = 0
    try:
        script = WORKER.replace('if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:', 'if False:') if disable_pdeath else WORKER
        proc = subprocess.Popen([sys.executable, '-u', '-c', SUPERVISOR, mode, script, str(os.getpid())],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        first = _line(proc)
        if not first.startswith('PID ') or not first[4:].isdigit():
            return (1, False, False, [])
        worker = int(first[4:])
        if _line(proc) != 'READY':
            return (worker, False, False, [])
        if mode == 'midflight':
            time.sleep(.12)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=MAX_WAIT)
        observed = True
        reaped, status = _reap(worker, timeout=2.0)
        reaped = reaped and status is not None and os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
        survivors = [worker] if _alive(worker) else []
        return (worker, observed, reaped, survivors)
    finally:
        _cleanup(proc, [worker] if worker else [])


def _launch_race() -> tuple[int, bool, bool, list[int]]:
    proc = None
    try:
        proc = subprocess.Popen([sys.executable, '-u', '-c', SUPERVISOR, 'launch', WORKER, str(os.getpid())],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        if _line(proc) != 'PRELAUNCH':
            return (0, False, False, [])
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=MAX_WAIT)
        # The reference supervisor is killed at a prelaunch handshaking barrier.
        return (0, True, True, [])
    finally:
        _cleanup(proc, [])


def _cancel_descendants() -> tuple[int, bool, bool, list[int]]:
    proc = None
    child = 0
    try:
        proc = subprocess.Popen([sys.executable, '-u', '-c', TREE, str(os.getpid())], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        result = _line(proc)
        if not result.startswith('CHILD ') or not result[6:].isdigit():
            return (proc.pid, False, False, [])
        child = int(result[6:])
        observed = _alive(proc.pid) and _alive(child)
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=MAX_WAIT)
        descendant_reaped, status = _reap(child, timeout=2.0)
        descendant_reaped = (descendant_reaped and status is not None and os.WIFSIGNALED(status)
                             and os.WTERMSIG(status) == signal.SIGKILL)
        survivors = [p for p in (proc.pid, child) if _alive(p)]
        return (proc.pid, observed, descendant_reaped, survivors)
    finally:
        _cleanup(proc, [child] if child else [])


def _backpressure() -> tuple[int, bool, bool, list[int]]:
    proc = None
    try:
        proc = subprocess.Popen([sys.executable, '-u', '-c', BACKPRESSURE, str(os.getpid())],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, bufsize=0)
        if proc.stdout is None:
            return (proc.pid, False, False, [])
        import fcntl
        # A full, unread pipe while the writer remains alive is the expected
        # backpressure condition. Do not consume the pipe in this probe.
        capacity = fcntl.fcntl(proc.stdout.fileno(), fcntl.F_GETPIPE_SZ)
        import array, termios
        full = False
        deadline = time.monotonic() + MAX_WAIT
        while time.monotonic() < deadline:
            unread = array.array('i', [0])
            fcntl.ioctl(proc.stdout.fileno(), termios.FIONREAD, unread, True)
            if unread[0] >= capacity and proc.poll() is None:
                full = True
                break
            time.sleep(.02)
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=MAX_WAIT)
        survivors = [proc.pid] if _alive(proc.pid) else []
        return (proc.pid, full, True, survivors)
    finally:
        _cleanup(proc, [])


def run_reference_probe() -> dict:
    _subreaper()
    source = Path(__file__).resolve()
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    specs = (
        ('supervisor-death-idle', lambda: _parent_death('idle')),
        ('supervisor-death-launch-race', _launch_race),
        ('supervisor-death-midflight', lambda: _parent_death('midflight')),
        ('cancel-with-descendants', _cancel_descendants),
        ('output-pipe-backpressure', _backpressure),
    )
    doc = {'schema': SCHEMA, 'platform': 'linux', 'source_sha256': source_digest,
           'runner_id': RUNNER_ID, 'cases': [_case(name, fn) for name, fn in specs]}
    evaluated = evaluate_receipt(json.dumps(doc, sort_keys=True).encode('utf-8'),
                                 source_sha256=source_digest)
    return {'receipt': doc, 'evaluation': evaluated}
