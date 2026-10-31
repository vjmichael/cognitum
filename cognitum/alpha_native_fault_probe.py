"""P50: measure the *actual*, fixed-function Cognitum alpha native worker.

This is a local integration test, NOT P46, Lu authority or sandbox certification.
The target worker is the existing cognitum.alpha_native_worker module, unchanged.
No LLM-repair utilities are introduced.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import sys
import time

from .alpha_native import MAX_FRAME, _parse, make_call
from .proto import alpha_native_pb2 as proto
from .proto.capability_pb2 import CalculateRationalResult

SCHEMA = 'cognitum.alpha-native-native-fault.v1'
TIMEOUT = 5.0
ROOT = Path(__file__).resolve().parent.parent
WORKER = ROOT / 'cognitum' / 'alpha_native_worker.py'


def _spawn():
    # The command is constant and uses no shell. Never use for arbitrary modules.
    return subprocess.Popen([sys.executable, '-m', 'cognitum.alpha_native_worker'],
                            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True, bufsize=0)


def _done(p: subprocess.Popen[bytes], frame: bytes) -> tuple[int, bytes, bytes, bool]:
    try:
        output, stderr = p.communicate(frame, timeout=TIMEOUT)
        return p.returncode, output, stderr, p.poll() is not None
    finally:
        if p.poll() is None:
            p.kill()
            p.communicate(timeout=TIMEOUT)


def _case(case_id: str, check):
    try:
        pid, code, observed, reaped, detail = check()
        return {'id': case_id, 'observed': bool(observed), 'worker_pid': pid,
                'exit_code': code, 'reaped': bool(reaped), 'detail': detail,
                'outcome': 'PASS' if observed and reaped else 'FAIL'}
    except Exception as exc:  # Probe failures must be reflected as failures.
        return {'id': case_id, 'observed': False, 'worker_pid': 0,
                'exit_code': None, 'reaped': False, 'detail': type(exc).__name__,
                'outcome': 'FAIL'}


def _ordinary(frame: bytes, *, expect: int, validate_reply=False):
    p = _spawn()
    code, output, stderr, reaped = _done(p, frame)
    good = code == expect and not stderr
    if validate_reply and good:
        if len(output) < 4:
            good = False
        else:
            declared = struct.unpack('>I', output[:4])[0]
            if declared != len(output)-4:
                good = False
            else:
                reply = _parse(proto.Reply, output[4:], 16384)
                good = (reply.version == 1 and reply.request_id == 'p50'
                        and reply.status == proto.Reply.COMPLETED
                        and not reply.error_code and not reply.lu_integrated
                        and not reply.os_isolation_verified
                        and CalculateRationalResult.FromString(reply.result_payload).value == '1/2')
    if not validate_reply and output:
        good = False
    return p.pid, code, good, reaped, ('typed-reply' if validate_reply else 'denied')


def _blocked_cancel():
    p = _spawn()
    try:
        assert p.stdin is not None
        # Worker has read the size, but has not received the claimed payload.
        p.stdin.write(struct.pack('>I', 100) + b'ab')
        p.stdin.flush()
        time.sleep(0.15)
        was_blocked = p.poll() is None
        os.killpg(p.pid, signal.SIGKILL)
        p.wait(timeout=TIMEOUT)
        return p.pid, p.returncode, was_blocked and p.returncode == -signal.SIGKILL, True, 'blocked-read-cancelled'
    finally:
        if p.poll() is None: os.killpg(p.pid, signal.SIGKILL)
        try: p.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=TIMEOUT)
        for s in (p.stdin, p.stdout, p.stderr):
            if s: s.close()


_PARENTHOLDER = r'''
import os, struct, subprocess, sys, time
p = subprocess.Popen([sys.executable, '-m', 'cognitum.alpha_native_worker'],
                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, bufsize=0)
print('CHILD', p.pid, flush=True)
p.stdin.write(struct.pack('>I', 100)+b'ab'); p.stdin.flush()
print('PARTIAL', flush=True)
time.sleep(100)
'''


def _supervisor_death_eof():
    # The adopted worker should get EOF and exit 2 after its parent dies.
    # No parent-death signal is claimed: this relies on closing the pipe.
    if not sys.platform.startswith('linux') or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('Linux pidfd parent crash probe required')
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise RuntimeError('PR_SET_CHILD_SUBREAPER failed')
    parent = subprocess.Popen([sys.executable, '-u', '-c', _PARENTHOLDER], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, start_new_session=True, bufsize=0)
    child = 0
    pidfd = None
    child_reaped = False
    try:
        assert parent.stdout is not None
        # Fixed two-line handshake with bounded blocking; actual worker is not modified.
        for expected in ('CHILD', 'PARTIAL'):
            ready, _, _ = select.select([parent.stdout], [], [], TIMEOUT)
            if not ready:
                raise RuntimeError('parent did not become ready')
            line = parent.stdout.readline(80).decode().strip()
            if expected == 'CHILD':
                if not line.startswith('CHILD ') or not line[6:].isdigit():
                    raise RuntimeError('missing worker pid')
                child = int(line[6:])
                pidfd = os.pidfd_open(child)
            elif line != expected:
                raise RuntimeError('missing partial handshake')
        time.sleep(.15)
        os.killpg(parent.pid, signal.SIGKILL)
        parent.wait(timeout=TIMEOUT)
        # Actual worker loses its last stdin writer, sees EOF, returns code 2.
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            try: waited, status = os.waitpid(child, os.WNOHANG)
            except ChildProcessError: return child, None, False, False, 'worker not adopted'
            if waited == child:
                child_reaped = True
                code = os.waitstatus_to_exitcode(status)
                return child, code, code == 2, True, 'parent-killed-worker-eof-denial'
            time.sleep(.02)
        return child, None, False, False, 'worker did not exit on eof'
    finally:
        if parent.poll() is None:
            try: os.killpg(parent.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        parent.wait(timeout=TIMEOUT)
        if pidfd is not None:
            # Stable kernel process handle avoids a recycled-PID cleanup race.
            if not child_reaped:
                poll = select.poll(); poll.register(pidfd, select.POLLIN | select.POLLHUP)
                if not poll.poll(0):
                    try: signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except ProcessLookupError: pass
                # Reap if adopted, even on a failed observation.
                try: os.waitpid(child, 0)
                except ChildProcessError: pass
            os.close(pidfd)
        for s in (parent.stdout, parent.stderr):
            if s: s.close()


def run_fault_matrix(*, include_crash=True):
    call = make_call('p50', '1/3 + 1/6')
    wire = struct.pack('>I', len(call)) + call
    bad_operation = proto.Call.FromString(call)
    bad_operation.operation = 'shell.run'
    bad_wire = bad_operation.SerializeToString(deterministic=True)
    cases = [
        _case('actual-valid-protobuf', lambda: _ordinary(wire, expect=0, validate_reply=True)),
        _case('actual-oversize-frame', lambda: _ordinary(struct.pack('>I', MAX_FRAME+1), expect=2)),
        _case('actual-truncated-frame', lambda: _ordinary(struct.pack('>I', len(call)) + call[:-1], expect=2)),
        _case('actual-extra-byte', lambda: _ordinary(wire+b'X', expect=2)),
        _case('actual-disallowed-operation', lambda: _ordinary(struct.pack('>I', len(bad_wire)) + bad_wire, expect=2)),
        _case('actual-blocked-input-cancel', _blocked_cancel),
    ]
    if include_crash and sys.platform.startswith('linux'):
        cases.append(_case('actual-supervisor-death-eof', _supervisor_death_eof))
    return {
        'schema': SCHEMA, 'platform': sys.platform,
        'worker_sha256': hashlib.sha256(WORKER.read_bytes()).hexdigest(),
        'worker_git_blob_sha': _git_blob(WORKER.read_bytes()),
        'target': 'cognitum.alpha_native_worker',
        'admission_assurance': 'NONE: direct fixed worker executable, no authenticated Lu host',
        'cases': cases,
        'status': 'PASS' if all(c['outcome'] == 'PASS' for c in cases) else 'FAIL',
        'qualification': 'actual worker executable and framing only; not P46 or sandbox attestation',
    }


def _git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


if __name__ == '__main__':
    print(json.dumps(run_fault_matrix(), sort_keys=True, indent=2))
