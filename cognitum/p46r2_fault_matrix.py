"""P46R2: fixed native Linux *negative controls* for worker lifetime gaps.

The subprocesses are solely disposable test fixtures or the fixed rational
Protobuf alpha worker. This module does NOT provide an arbitrary task runner,
OS sandbox, process-tree containment, or authorization to execute plugins.

The three cases expose failure of parent-death signals, descendant sessions,
and pipe-EOF liveness assumptions. Each escaped process is pinned by a pidfd
before its supervisor is killed, then killed/reaped in finally by the observer.
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

SCHEMA = 'cognitum.p46r2.negative-fault-matrix.v1'
ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / 'cognitum' / 'fixed_parent_lifetime.py'
WORKER = ROOT / 'cognitum' / 'alpha_native_worker.py'
CASE_IDS = ('cleared-parent-death-signal', 'setsid-descendant-escape',
            'inherited-stdin-writer')
WAIT_SECONDS = 4.0

_GUARD_SCRIPT = r'''
import ctypes, os, signal, subprocess, sys, time
mode = sys.argv[1]
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0: sys.exit(81)
if os.getppid() <= 1: sys.exit(82)
if mode == 'clear':
    if libc.prctl(1, 0, 0, 0, 0) != 0: sys.exit(83)
    check = ctypes.c_int(-1)
    if libc.prctl(2, ctypes.byref(check), 0, 0, 0) != 0 or check.value != 0: sys.exit(84)
    print('GUARD_READY 0', flush=True)
else:
    g = subprocess.Popen([sys.executable, '-u', '-c', sys.argv[2]],
                         stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, bufsize=0)
    if g.stdout.readline() != b'GRAND_READY\n': sys.exit(85)
    g.stdout.close()
    print('GUARD_READY', g.pid, flush=True)
while True: time.sleep(.1)
'''
_GRAND_SCRIPT = r'''
import os, time
print('GRAND_READY', flush=True)
while True: time.sleep(.1)
'''
_HOLDER_SCRIPT = r'''
import os, sys, time
fd = int(sys.argv[1])
os.fstat(fd)
print('HOLDER_READY', flush=True)
while True: time.sleep(.1)
'''
_SUPERVISOR_SCRIPT = r'''
import os, struct, subprocess, sys, time
mode = sys.argv[1]
if mode in ('clear', 'grandchild'):
    p = subprocess.Popen([sys.executable, '-u', '-c', sys.argv[2],
                          'clear' if mode == 'clear' else 'grandchild', sys.argv[3]],
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, start_new_session=True, bufsize=0)
    ready = p.stdout.readline().decode('ascii', 'replace').strip()
    p.stdout.close()
    if not ready.startswith('GUARD_READY '): sys.exit(71)
    _, descendant = ready.split()
    print('PIDS', p.pid, descendant, flush=True)
else:
    reader, writer = os.pipe()
    worker = subprocess.Popen([sys.executable, '-m', 'cognitum.alpha_native_worker'],
                              stdin=reader, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True, bufsize=0)
    os.close(reader)
    holder = subprocess.Popen([sys.executable, '-u', '-c', sys.argv[4], str(writer)],
                              pass_fds=(writer,), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              start_new_session=True, bufsize=0)
    if holder.stdout.readline() != b'HOLDER_READY\n': sys.exit(72)
    holder.stdout.close()
    os.write(writer, struct.pack('>I', 100) + b'X')
    print('PIDS', worker.pid, holder.pid, flush=True)
while True: time.sleep(.1)
'''


def _start_ticks(pid: int) -> int:
    stat = Path('/proc/%d/stat' % pid).read_text(encoding='ascii')
    return int(stat[stat.rfind(')')+2:].split()[19])


def _pidfd_exited(fd: int, timeout_ms: int = 0) -> bool:
    poll = select.poll()
    poll.register(fd, select.POLLIN | select.POLLHUP)
    return bool(poll.poll(timeout_ms))


def _reap_adopted(pid: int, deadline: float = WAIT_SECONDS) -> bool:
    until = time.monotonic() + deadline
    while time.monotonic() < until:
        try:
            result, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return False
        if result == pid:
            return True
        time.sleep(.015)
    return False


def _read_pid_line(p: subprocess.Popen, timeout: float) -> tuple[int, int]:
    if p.stdout is None:
        raise RuntimeError('NO_SUPERVISOR_STDOUT')
    # Parent writes one tiny line and flushes. Avoid waiting forever on EOF.
    if not select.select([p.stdout], [], [], timeout)[0]:
        raise TimeoutError('SUPERVISOR_READINESS_TIMEOUT')
    line = p.stdout.readline(96).decode('ascii', 'strict').strip()
    words = line.split()
    if len(words) != 3 or words[0] != 'PIDS' or not all(s.isdecimal() for s in words[1:]):
        raise RuntimeError('INVALID_SUPERVISOR_PID_REPORT')
    ids = int(words[1]), int(words[2])
    if ids[0] <= 1 or (ids[1] and ids[1] == ids[0]):
        raise RuntimeError('DUPLICATE_OR_INVALID_PID')
    return ids


def _run_one(case_id: str) -> dict:
    if case_id not in CASE_IDS:
        raise ValueError('INVALID_FIXED_CASE')
    if sys.platform != 'linux' or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('LINUX_PIDFD_REQUIRED')
    mode = {'cleared-parent-death-signal':'clear',
            'setsid-descendant-escape':'grandchild',
            'inherited-stdin-writer':'pipe'}[case_id]
    proc: subprocess.Popen | None = None
    handles: dict[str, tuple[int, int, int]] = {}
    exited: dict[str, bool] = {}
    reaped: dict[str, bool] = {}
    observer_error = None
    supervisor_killed = False
    names = ('worker', 'descendant') if mode != 'pipe' else ('worker', 'writer-holder')
    try:
        proc = subprocess.Popen([sys.executable, '-u', '-c', _SUPERVISOR_SCRIPT,
                                 mode, _GUARD_SCRIPT, _GRAND_SCRIPT, _HOLDER_SCRIPT],
                                cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True, bufsize=0)
        pids = _read_pid_line(proc, WAIT_SECONDS)
        for name, pid in zip(names, pids):
            if pid == 0:
                continue
            fd = os.pidfd_open(pid)
            handles[name] = (pid, fd, _start_ticks(pid))
        if 'worker' not in handles or mode != 'clear' and names[1] not in handles:
            raise RuntimeError('MISSING_OBSERVED_CHILD')
        if mode == 'grandchild':
            # The descendant has created its own session, outside supervisor's
            # and guarded worker's process groups.
            if os.getsid(pids[1]) != pids[1]:
                raise RuntimeError('DESCENDANT_DID_NOT_SET_SETSID')
        if mode == 'pipe' and _pidfd_exited(handles['worker'][1]):
            raise RuntimeError('REAL_WORKER_EXITED_BEFORE_PARENT_CRASH')
        # All observable children are pinned by identity-stable kernel handles
        # before the test deliberately kills its supervisor.
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=WAIT_SECONDS)
        supervisor_killed = proc.returncode == -signal.SIGKILL
        for name, (_, fd, _) in handles.items():
            exited[name] = _pidfd_exited(fd, 1200 if mode == 'grandchild' and name == 'worker' else 180)
    except Exception as exc:
        observer_error = type(exc).__name__ + ': ' + str(exc)[:90]
    finally:
        if proc is not None:
            if proc.poll() is None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            try: proc.wait(timeout=WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=WAIT_SECONDS)
        for name, (pid, fd, _) in handles.items():
            try:
                if not _pidfd_exited(fd):
                    signal.pidfd_send_signal(fd, signal.SIGKILL)
                reaped[name] = _reap_adopted(pid)
            except (ProcessLookupError, OSError):
                reaped[name] = False
            finally:
                os.close(fd)
        if proc is not None:
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
    expected = {'cleared-parent-death-signal': {'worker': False},
                'setsid-descendant-escape': {'worker': True, 'descendant': False},
                'inherited-stdin-writer': {'worker': False, 'writer-holder': False}}[case_id]
    expected_outcome = (observer_error is None and supervisor_killed
                        and set(exited) == set(expected) and exited == expected
                        and all(reaped.get(name) is True for name in exited))
    return {'id':case_id, 'supervisor_sigkill_reaped':supervisor_killed,
            'pidfd_pinned_before_supervisor_kill':len(handles) == len(expected),
            'children': {name:{'pid':pid, 'proc_start_ticks':ticks,
                               'exit_observed_after_supervisor_death':exited.get(name),
                               'cleanup_reaped':reaped.get(name, False)}
                         for name,(pid,_,ticks) in handles.items()},
            'expected_negative_control':True,
            'expected_observation_matched':expected_outcome,
            'error':observer_error}


def run_fault_matrix() -> dict:
    if sys.platform != 'linux':
        raise RuntimeError('LINUX_ONLY')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise RuntimeError('SUBREAPER_UNAVAILABLE')
    cases = [_run_one(case) for case in CASE_IDS]
    result = {'schema':SCHEMA, 'host_platform':'linux',
              'source_sha256':hashlib.sha256(GUARD.read_bytes()).hexdigest(),
              'real_worker_sha256':hashlib.sha256(WORKER.read_bytes()).hexdigest(),
              'cases':cases, 'security_admission':'DENIED',
              'native_containment_verified':False,
              'assurance':'LOCAL_HOST_OBSERVED_UNATTESTED',
              'finding':'PDEATHSIG_AND_PIPE_EOF_NOT_PROCESS_TREE_CONTAINMENT',
              'verdict':'NEGATIVE_CONTROLS_OBSERVED' if all(c['expected_observation_matched'] for c in cases)
                        else 'FAIL'}
    return result


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                      separators=(',', ':')).encode('ascii')


def _no_duplicates(pairs):
    obj = {}
    for key, val in pairs:
        if key in obj:
            raise ValueError('DUPLICATE_KEY')
        obj[key] = val
    return obj


def verify_receipt(raw: bytes, expected_guard_sha256: str,
                   expected_worker_sha256: str) -> str:
    """Strict *structural* check. Local receipts can be forged, not attested."""
    if type(raw) is not bytes or len(raw) > 64*1024:
        return 'INVALID'
    try:
        v = json.loads(raw.decode('utf-8','strict'), object_pairs_hook=_no_duplicates,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE')))
        if type(v) is not dict or set(v) != {'schema','host_platform','source_sha256',
                'real_worker_sha256','cases','security_admission','native_containment_verified',
                'assurance','finding','verdict'}:
            return 'INVALID'
        if (v['schema'] != SCHEMA or v['host_platform'] != 'linux'
                or v['source_sha256'] != expected_guard_sha256
                or v['real_worker_sha256'] != expected_worker_sha256
                or v['security_admission'] != 'DENIED'
                or v['native_containment_verified'] is not False
                or v['assurance'] != 'LOCAL_HOST_OBSERVED_UNATTESTED'
                or v['finding'] != 'PDEATHSIG_AND_PIPE_EOF_NOT_PROCESS_TREE_CONTAINMENT'
                or type(v['cases']) is not list or len(v['cases']) != 3):
            return 'INVALID'
        for cid, case in zip(CASE_IDS, v['cases']):
            if type(case) is not dict or set(case) != {'id','supervisor_sigkill_reaped',
                    'pidfd_pinned_before_supervisor_kill','children',
                    'expected_negative_control','expected_observation_matched','error'}:
                return 'INVALID'
            if case['id'] != cid or any(type(case[k]) is not bool for k in
                    ('supervisor_sigkill_reaped','pidfd_pinned_before_supervisor_kill',
                     'expected_negative_control','expected_observation_matched')):
                return 'INVALID'
            if type(case['children']) is not dict or case['error'] is not None and type(case['error']) is not str:
                return 'INVALID'
            required = {'cleared-parent-death-signal':('worker',),
                        'setsid-descendant-escape':('worker','descendant'),
                        'inherited-stdin-writer':('worker','writer-holder')}[cid]
            if set(case['children']) != set(required):
                return 'FAIL'  # Well-formed but incomplete observation.
            expected_exited = {'cleared-parent-death-signal': {'worker':False},
                'setsid-descendant-escape': {'worker':True,'descendant':False},
                'inherited-stdin-writer': {'worker':False,'writer-holder':False}}[cid]
            for name, child in case['children'].items():
                if type(child) is not dict or set(child) != {'pid','proc_start_ticks',
                        'exit_observed_after_supervisor_death','cleanup_reaped'}:
                    return 'INVALID'
                if (type(child['pid']) is not int or child['pid'] <= 1
                        or type(child['proc_start_ticks']) is not int or child['proc_start_ticks'] <= 0
                        or type(child['exit_observed_after_supervisor_death']) is not bool
                        or type(child['cleanup_reaped']) is not bool):
                    return 'INVALID'
                if child['exit_observed_after_supervisor_death'] != expected_exited[name]:
                    return 'FAIL'
        observed = all(c['supervisor_sigkill_reaped'] and c['pidfd_pinned_before_supervisor_kill']
                       and c['expected_negative_control'] and c['expected_observation_matched']
                       and c['error'] is None and all(ch['cleanup_reaped'] for ch in c['children'].values())
                       for c in v['cases'])
        return 'OBSERVED_NEGATIVE_CONTROLS_UNATTESTED' if observed and v['verdict'] == 'NEGATIVE_CONTROLS_OBSERVED' else 'FAIL'
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError, UnicodeError):
        return 'INVALID'


if __name__ == '__main__':
    print(json.dumps(run_fault_matrix(), indent=2, sort_keys=True))
