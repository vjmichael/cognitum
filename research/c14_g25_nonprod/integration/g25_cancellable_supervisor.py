#!/usr/bin/env python3
"""Standalone opt-in G25 research supervisor, NOT a Lu/Core/prod runtime.

Protocol v2: bounded JSONL controls on stdin, JSONL events on stdout.
One active job at a time, each in a new process group/session on POSIX.
Cancellation only yields 'cancelled' after worker reaping and group kill.
Per-request child is the *unchanged* G25 research host; no arbitrary path IPC.

Linux POSIX tree containment is tested; Windows descendant containment is
NOT established by CREATE_NEW_PROCESS_GROUP and remains an open gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from threading import Event, Lock, Thread

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'integration' / 'c14_research_host.py'
GUARD = ROOT / 'tools' / 'g25_release_guard.py'
BASELINE = ROOT / 'baseline' / 'g25i_core.py'
FROZEN_SHA256 = {
    HOST: '74a717da88139c1a894e7d754a1dc702f5e328337ee2109017313c6a3aa2681c',
    GUARD: '3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c',
    BASELINE: 'f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4',
}
VERSION = 2
MAX_LINE = 1024 * 1024
MAX_WORKER_OUTPUT = 65536
MAX_COMMANDS = 2000
WORKER_TIMEOUT = 16
RE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def pairs_unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate_json_key')
        out[key] = value
    return out


def reject_constant(_):
    raise ValueError('invalid_json_constant')


def parse_control(raw: bytes):
    value = json.loads(raw, object_pairs_hook=pairs_unique, parse_constant=reject_constant)
    if type(value) is not dict or type(value.get('protocol_version')) is not int or value['protocol_version'] != VERSION:
        raise ValueError('invalid_protocol_version')
    kind = value.get('type')
    expected = {'protocol_version', 'type', 'request_id'}
    if kind == 'run':
        expected.add('request')
    elif kind != 'cancel':
        raise ValueError('invalid_command')
    if set(value) != expected:
        raise ValueError('invalid_command_fields')
    ident = value['request_id']
    if type(ident) is not str or RE_ID.fullmatch(ident) is None:
        raise ValueError('invalid_request_id')
    if kind == 'run':
        request = value['request']
        if type(request) is not dict or request.get('request_id') != ident:
            raise ValueError('mismatched_nested_request_id')
        if set(request) - {'schema_version','request_id','action','counts','observations','gamma','assumption_evidence'}:
            raise ValueError('unknown_request_fields')
        if type(request.get('schema_version')) is not int or request['schema_version'] != 1:
            raise ValueError('invalid_nested_schema')
        if request.get('action') != 'c14.g25.sensitivity.report':
            raise ValueError('invalid_nested_action')
        if ('counts' in request) == ('observations' in request):
            raise ValueError('invalid_input_mode')
        if 'gamma' not in request or 'assumption_evidence' not in request:
            raise ValueError('missing_required_fields')
    return value


def verify_source():
    return all(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha
               for path, sha in FROZEN_SHA256.items())


def safe_worker_environment(extra=None):
    env = {
       'COGNITUM_G25_RESEARCH_OPT_IN': '1',
       'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
       'MKL_NUM_THREADS': '1', 'PYTHONNOUSERSITE': '1',
       'PYTHONIOENCODING': 'utf-8',
    }
    # Required for Python/Windows runtime discovery in an installed test environment.
    if os.name == 'nt':
        for key in ('SYSTEMROOT', 'WINDIR', 'PATH'):
            if key in os.environ: env[key] = os.environ[key]
    if extra: env.update(extra)  # Programmatic test harness only, never IPC.
    return env


def verify_response(data: bytes, ident: str, raw: bytes):
    if len(data) > MAX_WORKER_OUTPUT or not data.endswith(b'\n') or data.count(b'\n') != 1:
        return None
    try:
        r = json.loads(data, object_pairs_hook=pairs_unique, parse_constant=reject_constant)
        if type(r) is not dict or type(r.get('host_receipt_sha256')) is not str:
            return None
        expected = hashlib.sha256(canonical({k:v for k,v in r.items() if k!='host_receipt_sha256'}).encode()).hexdigest()
        if r['host_receipt_sha256'] != expected:
            return None
        if r.get('request_id') != ident or r.get('input_sha256') != hashlib.sha256(raw).hexdigest():
            return None
        if (r.get('schema_version') != 1 or r.get('research_only') is not True
                or r.get('automatic_causal_certification') is not False
                or r.get('production_estimator_promotion') is not False):
            return None
        if r.get('host_status') not in {'completed', 'refused', 'invalid_request', 'internal_failure'}:
            return None
        result = r.get('result')
        if r['host_status'] in {'completed', 'refused'}:
            if type(result) is not dict or (result.get('automatic_causal_certification') is not False
                    or result.get('production_estimator_promotion') is not False):
                return None
            if r['host_status'] == 'completed':
                if result.get('status') != 'conditional_sensitivity_report_only':
                    return None
                for field in ('identified_set_plugin', 'identified_set_outer95_conditional'):
                    interval = result.get(field)
                    if (type(interval) is not list or len(interval) != 2
                            or not all(type(v) in (int, float) and -1 <= v <= 1 for v in interval)
                            or interval[0] > interval[1]):
                        return None
            elif (result.get('identified_set_plugin') is not None
                  or result.get('identified_set_outer95_conditional') is not None
                  or result.get('status') not in {'blocked_missing_observed_arm',
                      'blocked_sparse_observed_arm', 'blocked_missing_assumption_evidence'}):
                return None
        elif result is not None:
            return None
        return r
    except (ValueError, TypeError, KeyError):
        return None


@dataclass
class Job:
    ident: str
    payload: bytes
    cancelled: bool = False
    proc: subprocess.Popen | None = None
    completed: Event = field(default_factory=Event)


class Supervisor:
    def __init__(self, *, sink=None, worker_path=HOST, verify_frozen=True, extra_worker_env=None, timeout=WORKER_TIMEOUT):
        # Custom worker paths are only available to trusted in-process tests.
        if verify_frozen and (worker_path != HOST or not verify_source()):
            raise RuntimeError('frozen_source_mismatch')
        self.worker_path = worker_path
        self.extra_worker_env = extra_worker_env or {}
        self.timeout = timeout
        self.sink = sink if sink is not None else sys.stdout
        self.mu = Lock()
        self.io_mu = Lock()
        self.active: Job | None = None
        self.seen: set[str] = set()
        self.threads: list[Thread] = []

    def emit(self, kind, ident, **values):
        obj = {'protocol_version': VERSION, 'event': kind, 'request_id': ident,
               'research_only': True, 'automatic_causal_certification': False,
               'production_estimator_promotion': False, **values}
        with self.io_mu:
            self.sink.write(canonical(obj) + '\n')
            self.sink.flush()
        return obj

    @staticmethod
    def terminate_tree(proc):
        if proc is None:
            return
        if os.name == 'posix':
            # Spawned by this supervisor in a unique new session/group.
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            except PermissionError: pass
        elif proc.poll() is None:
            proc.kill()  # NOT descendant-safe on Windows. Windows gate stays OPEN.
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

    def _work(self, job):
        response = None
        error = 'worker_failure'
        proc = None
        try:
            with self.mu:
                if not job.cancelled:
                    proc = subprocess.Popen([sys.executable, str(self.worker_path), '--research-only'],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        shell=False, env=safe_worker_environment(self.extra_worker_env),
                        start_new_session=(os.name=='posix'),
                        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0))
                    job.proc = proc
            if proc is not None:
                out, _ = proc.communicate(job.payload + b'\n', timeout=self.timeout)
                if proc.returncode == 0:
                    response = verify_response(out, job.ident, job.payload)
                    if response is None: error = 'invalid_worker_receipt'
                else:
                    error = 'worker_exit_nonzero'
        except subprocess.TimeoutExpired:
            error = 'worker_timeout'
        except Exception:
            error = 'worker_failure'
        finally:
            # Even on successful worker exit, remove any inherited-session descendants.
            if proc is not None:
                self.terminate_tree(proc)
                # communicate() does not close every pipe on every exceptional
                # path (notably TimeoutExpired); do not leak OS descriptors.
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
            with self.mu:
                if job.cancelled:
                    self.emit('cancelled', job.ident, response=None)
                elif response is not None:
                    self.emit('result', job.ident, response=response)
                else:
                    self.emit('failed', job.ident, code=error, response=None)
                if self.active is job:
                    self.active = None
            job.completed.set()

    def accept(self, raw):
        try:
            cmd = parse_control(raw)
        except (ValueError, TypeError, UnicodeDecodeError):
            return self.emit('rejected', None, code='invalid_control_frame')
        ident = cmd['request_id']
        with self.mu:
            if cmd['type'] == 'cancel':
                if self.active is None or self.active.ident != ident:
                    return self.emit('rejected', ident, code='unknown_or_completed_task')
                if self.active.cancelled:
                    return self.emit('rejected', ident, code='already_cancelling')
                self.active.cancelled = True
                proc = self.active.proc
                self.emit('cancellation_requested', ident)
                if proc is not None:
                    self.terminate_tree(proc)
                return None
            if ident in self.seen:
                return self.emit('rejected', ident, code='duplicate_task_id')
            if self.active is not None:
                return self.emit('rejected', ident, code='busy')
            payload = canonical(cmd['request']).encode()
            if len(payload) > MAX_LINE - 1:
                return self.emit('rejected', ident, code='oversized_request')
            job = Job(ident, payload)
            self.seen.add(ident)
            self.active = job
            self.emit('accepted', ident)
            thread = Thread(target=self._work, args=(job,), daemon=False)
            self.threads.append(thread)
            thread.start()
        return None

    def close(self):
        with self.mu:
            job = self.active
            if job is not None:
                job.cancelled = True
                if job.proc is not None:
                    self.terminate_tree(job.proc)
        if job is not None:
            job.completed.wait(timeout=self.timeout + 5)
        for thread in self.threads:
            thread.join(timeout=2)
        return not any(t.is_alive() for t in self.threads)

    def serve(self, source=None):
        stream = sys.stdin.buffer if source is None else source
        try:
            for _ in range(MAX_COMMANDS):
                line = stream.readline(MAX_LINE+1)
                if not line: return 0
                if len(line) > MAX_LINE:
                    self.emit('rejected', None, code='oversized_control_stream_closed')
                    return 65
                if not line.strip():
                    self.emit('rejected', None, code='blank_control')
                else:
                    self.accept(line.rstrip(b'\r\n'))
            return 69
        finally:
            if not self.close():
                self.emit('failed', None, code='supervisor_cleanup_incomplete', response=None)


def main():
    p = argparse.ArgumentParser(description='C14 G25 isolated research cancellation supervisor')
    p.add_argument('--research-only', action='store_true')
    args = p.parse_args()
    if not args.research_only or os.environ.get('COGNITUM_G25_RESEARCH_OPT_IN') != '1':
        print('research supervisor disabled', file=sys.stderr)
        return 78
    try: return Supervisor().serve()
    except Exception:
        print('research supervisor unavailable', file=sys.stderr)
        return 70


if __name__ == '__main__':
    raise SystemExit(main())
