"""Opt-in *same trusted task* batching of standalone G25 research reports.

One newly spawned and bounded child per batch; no process persists across
conversation tasks. The child is the existing pinned G25 research host, not
an alternative estimator. A failed/partial/cancelled batch yields NO reports.

This is NOT an authentication, grant, OS sandbox, Lu integration, or production
permission layer. Caller must independently validate the user/task scope.
Windows descendant containment is NOT proved: do not enable there.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import threading
import time

if __package__:
    from .g25_cancellable_supervisor import (
        HOST, MAX_WORKER_OUTPUT, RE_ID, canonical,
        safe_worker_environment, verify_response, verify_source,
    )
else:
    from g25_cancellable_supervisor import (
        HOST, MAX_WORKER_OUTPUT, RE_ID, canonical,
        safe_worker_environment, verify_response, verify_source,
    )

MAX_BATCH_ITEMS = 16
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_BATCH_OUTPUT_BYTES = 16 * MAX_WORKER_OUTPUT
DEFAULT_DEADLINE = 20.0


class InvalidBatch(ValueError):
    pass


class WorkerOutputOverflow(RuntimeError):
    pass


def bounded_exchange(proc, payload: bytes, event: threading.Event,
                     deadline: float, output_cap: int) -> bytes:
    """POSIX-only nonblocking pipe exchange, with strict parent output budget.

    Unlike subprocess.communicate(), output never grows unbounded if a buggy
    or hostile worker emits unlimited stdout. Select timeouts also observe
    in-flight cancellation even if the worker never closes a pipe.
    """
    assert os.name == 'posix' and proc.stdin is not None and proc.stdout is not None
    selector = selectors.DefaultSelector()
    sink = bytearray()
    pos = 0
    end = time.monotonic() + deadline
    try:
        os.set_blocking(proc.stdin.fileno(), False)
        os.set_blocking(proc.stdout.fileno(), False)
        selector.register(proc.stdin, selectors.EVENT_WRITE)
        selector.register(proc.stdout, selectors.EVENT_READ)
        while selector.get_map():
            if event.is_set():
                raise RuntimeError('BATCH_CANCELLED')
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args,deadline)
            for ready,_ in selector.select(min(remaining, 0.1)):
                if ready.fileobj is proc.stdin:
                    try:
                        n = os.write(proc.stdin.fileno(),payload[pos:pos+65536])
                    except BrokenPipeError:
                        n = 0
                    pos += n
                    if n == 0 or pos >= len(payload):
                        selector.unregister(proc.stdin)
                        proc.stdin.close()
                else:
                    chunk = os.read(proc.stdout.fileno(),min(65536,output_cap+1-len(sink)))
                    if not chunk:
                        selector.unregister(proc.stdout)
                        proc.stdout.close()
                    else:
                        sink.extend(chunk)
                        if len(sink) > output_cap:
                            raise WorkerOutputOverflow('WORKER_OUTPUT_BUDGET')
        remaining=end-time.monotonic()
        if remaining<=0:
            raise subprocess.TimeoutExpired(proc.args,deadline)
        proc.wait(timeout=remaining)
        return bytes(sink)
    finally:
        selector.close()


class TaskBatch:
    """Task-scoped optimization of existing separate-worker semantics.

    Only one active task per instance; each task ID can execute once. The
    research-host source guard is verified before dispatch and after execution.
    Cancellation is externally signalled by cancel(task_id), never via an
    untrusted JSON control embedded in the reports. No cached worker or grants.
    """

    def __init__(self, *, research_opt_in: bool = False, deadline=DEFAULT_DEADLINE,
                 worker_path: Path = HOST, _test_worker: bool = False, _test_env: dict | None = None):
        if research_opt_in is not True:
            raise PermissionError('RESEARCH_BATCH_DISABLED')
        if os.name != 'posix':
            raise RuntimeError('PLATFORM_DESCENDANT_CONTAINMENT_UNVERIFIED')
        if not 0.05 <= deadline <= DEFAULT_DEADLINE:
            raise InvalidBatch('INVALID_DEADLINE')
        if not _test_worker and (Path(worker_path) != HOST or not verify_source()):
            raise RuntimeError('FROZEN_RESEARCH_SOURCE_MISMATCH')
        self.worker_path = Path(worker_path)
        self.deadline = float(deadline)
        self._test_worker = _test_worker
        self._test_env = _test_env or {}
        self._mu = threading.RLock()
        self._active = None
        self._seen = set()
        self._closed = False

    @staticmethod
    def _preflight(task_id, requests):
        if type(task_id) is not str or RE_ID.fullmatch(task_id) is None:
            raise InvalidBatch('INVALID_TASK_ID')
        if type(requests) not in (list, tuple) or not 1 <= len(requests) <= MAX_BATCH_ITEMS:
            raise InvalidBatch('INVALID_BATCH_SIZE')
        frames = []
        ids = set()
        total = 0
        for req in requests:
            if type(req) is not dict or set(req) - {
                'schema_version','request_id','action','counts','observations',
                'gamma','assumption_evidence',
            }:
                raise InvalidBatch('INVALID_REQUEST_FIELDS')
            rid = req.get('request_id')
            if type(rid) is not str or RE_ID.fullmatch(rid) is None or rid in ids:
                raise InvalidBatch('DUPLICATE_OR_INVALID_REQUEST_ID')
            if (type(req.get('schema_version')) is not int or req['schema_version'] != 1
                or req.get('action') != 'c14.g25.sensitivity.report'
                or ('counts' in req) == ('observations' in req)
                or 'gamma' not in req or 'assumption_evidence' not in req):
                raise InvalidBatch('INVALID_RESEARCH_REQUEST')
            try:
                raw = canonical(req).encode('utf-8')
            except (ValueError, TypeError, OverflowError) as exc:
                raise InvalidBatch('NONCANONICAL_REQUEST') from exc
            if len(raw) > 1024 * 1024:
                raise InvalidBatch('REQUEST_SIZE_EXCEEDED')
            total += len(raw) + 1
            if total > MAX_INPUT_BYTES:
                raise InvalidBatch('BATCH_SIZE_EXCEEDED')
            ids.add(rid)
            frames.append((rid, raw))
        return frames

    @staticmethod
    def _reap(proc):
        if proc is None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        for pipe in (proc.stdin, proc.stdout):
            if pipe is not None and not pipe.closed:
                pipe.close()

    @staticmethod
    def _answer(task_id, status, *, responses=None, code=None, elapsed_ms=None):
        return {
            'schema_version':1, 'task_id':task_id, 'status':status,
            'responses':responses if status == 'completed' else None,
            'error_code':code, 'elapsed_ms':elapsed_ms,
            'research_only':True, 'automatic_causal_certification':False,
            'production_estimator_promotion':False,
        }

    def execute(self, task_id, requests):
        frames = self._preflight(task_id, requests)
        started = time.perf_counter()
        with self._mu:
            if self._closed:
                raise InvalidBatch('SUPERVISOR_CLOSED')
            if self._active is not None:
                raise InvalidBatch('ANOTHER_TASK_ACTIVE')
            if task_id in self._seen:
                raise InvalidBatch('REPLAYED_TASK_ID')
            self._seen.add(task_id)
            event = threading.Event()
            self._active = {'id':task_id,'event':event,'proc':None}
        proc = None
        responses = None
        code = None
        try:
            with self._mu:
                if event.is_set():
                    code = 'CANCELLED_BEFORE_LAUNCH'
                else:
                    # POSIX-only new process group. No worker reuse across tasks.
                    proc = subprocess.Popen([sys.executable,str(self.worker_path),'--research-only'],
                        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                        env=safe_worker_environment(self._test_env),shell=False,start_new_session=True)
                    self._active['proc'] = proc
            if proc is not None:
                payload = b''.join(raw+b'\n' for _,raw in frames)
                output = bounded_exchange(proc,payload,event,self.deadline,len(frames)*MAX_WORKER_OUTPUT)
                if event.is_set():
                    code = 'CANCELLED'
                elif proc.returncode != 0:
                    code = 'WORKER_EXIT_NONZERO'
                elif len(output) > MAX_BATCH_OUTPUT_BYTES or output.count(b'\n') != len(frames) or not output.endswith(b'\n'):
                    code = 'INVALID_BATCH_FRAME_COUNT'
                else:
                    tentative = []
                    for line, (rid,raw) in zip(output.splitlines(),frames):
                        response = verify_response(line+b'\n',rid,raw)
                        if response is None or response['host_status'] not in ('completed','refused'):
                            code = 'INVALID_OR_UNSAFE_REPORT'
                            tentative = []
                            break
                        tentative.append(response)
                    if code is None:
                        if not self._test_worker and not verify_source():
                            code = 'FROZEN_SOURCE_CHANGED_DURING_EXECUTION'
                        else:
                            responses = tentative
        except subprocess.TimeoutExpired:
            code = 'WORKER_TIMEOUT'
        except WorkerOutputOverflow:
            code = 'WORKER_OUTPUT_BUDGET'
        except (OSError,ValueError,TypeError):
            code = 'WORKER_FAILURE'
        finally:
            self._reap(proc)
            with self._mu:
                # Cancellation wins any in-flight race prior to final publish.
                if event.is_set():
                    code = 'CANCELLED'
                    responses = None
                if self._active is not None and self._active['id'] == task_id:
                    self._active = None
        elapsed = round((time.perf_counter()-started)*1000,3)
        if code is not None:
            return self._answer(task_id,'cancelled' if code.startswith('CANCELLED') else 'failed',
                                code=code,elapsed_ms=elapsed)
        return self._answer(task_id,'completed',responses=responses,elapsed_ms=elapsed)

    def cancel(self, task_id):
        proc = None
        with self._mu:
            if self._active is None or self._active['id'] != task_id:
                return False
            self._active['event'].set()
            proc = self._active['proc']
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid,signal.SIGKILL)
            except (ProcessLookupError,PermissionError):
                pass
        return True

    def close(self):
        with self._mu:
            self._closed = True
            current = self._active['id'] if self._active else None
        if current is not None:
            self.cancel(current)
