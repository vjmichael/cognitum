"""P4: bounded prewarmed one-shot workers for trusted deterministic pure plugins.

The cap applies to ALL warm-origin processes: idle + warming + executing.
Overflow always takes the unchanged disposable worker path; it never waits
for another warm process. This is not a sandbox or trusted OS security policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import multiprocessing as mp
import threading
import time

from .contracts import Manifest
from .worker import execute as cold_execute

MAX_WARM_WORKERS = 4
MAX_MESSAGE_BYTES = 65536


class _GlobalWarmBudget:
    """One host-process-wide cap shared by all P4 capability-specific pools."""
    def __init__(self):
        self._lock = threading.Lock()
        self._reserved = 0
        self._peak = 0

    def reserve(self):
        with self._lock:
            if self._reserved >= MAX_WARM_WORKERS:
                return False
            self._reserved += 1
            self._peak = max(self._peak, self._reserved)
            return True

    def release(self):
        with self._lock:
            if self._reserved == 0:
                raise RuntimeError('GLOBAL_WARM_BUDGET_UNDERFLOW')
            self._reserved -= 1

    def snapshot(self):
        with self._lock:
            return {'reserved': self._reserved, 'peak': self._peak,
                    'limit': MAX_WARM_WORKERS}


_GLOBAL_WARM_BUDGET = _GlobalWarmBudget()


def global_warm_budget_snapshot():
    """Host-facing diagnostic; total prewarmed slots across all P4 pools."""
    return _GLOBAL_WARM_BUDGET.snapshot()


@dataclass
class _Slot:
    process: object
    connection: object
    ready_at: float


def _worker_main(conn, factory):
    """One ready handshake and at most ONE call; bounded JSON, no pickle replies."""
    try:
        plugin = factory()
        conn.send_bytes(b'READY')
        raw = conn.recv_bytes(MAX_MESSAGE_BYTES)
        request = json.loads(raw)
        if type(request) is not dict or set(request) != {'operation', 'payload'}:
            return
        try:
            result = plugin.handle(request['operation'], request['payload'])
            reply = {'status': 'ok', 'result': result}
        except ValueError:
            reply = {'status': 'invalid_input', 'result': None}
        except BaseException:
            reply = {'status': 'error', 'result': None}
        try:
            data = json.dumps(reply, allow_nan=False, separators=(',', ':')).encode()
            if len(data) > MAX_MESSAGE_BYTES:
                data = b'{"status":"error","result":null}'
            conn.send_bytes(data)
        except (TypeError, ValueError, OverflowError):
            conn.send_bytes(b'{"status":"error","result":null}')
    except (EOFError, OSError, ValueError, TypeError):
        pass
    finally:
        conn.close()


def _stop_and_reap(proc, conn):
    try:
        conn.close()
    except (ValueError, OSError):
        pass
    try:
        if proc.pid is not None:
            if proc.is_alive():
                proc.terminate()
            proc.join(1.0)
            if proc.is_alive():
                proc.kill()
                proc.join(1.0)
            proc.close()
    except (AssertionError, OSError, ValueError):
        pass


class WarmCappedPool:
    """At most four prewarmed one-shot processes, including busy and warming.

    Defaults to a single standby to avoid wasted memory. Set target_ready=4
    to keep four workers ready at startup, or choose a lower target. Every
    successful warm call consumes its worker and replenishes asynchronously.
    Cold overflow can start other processes, but those do not count as prewarms.
    """

    def __init__(self, factory, *, target_ready=1, max_warm=4,
                 max_cold_inflight=8, warmup_timeout_s=10.0, max_idle_s=120.0):
        if type(target_ready) is not int or type(max_warm) is not int or not (1 <= target_ready <= max_warm <= MAX_WARM_WORKERS):
            raise ValueError('WARM_WORKER_LIMIT_MUST_BE_1_TO_4')
        if type(max_cold_inflight) is not int or not 1 <= max_cold_inflight <= 32:
            raise ValueError('INVALID_COLD_CONCURRENCY_LIMIT')
        if type(warmup_timeout_s) not in (int, float) or not 0.2 <= warmup_timeout_s <= 30:
            raise ValueError('INVALID_WARMUP_DEADLINE')
        if type(max_idle_s) not in (int, float) or not 1 <= max_idle_s <= 3600:
            raise ValueError('INVALID_IDLE_TTL')
        if not isinstance(factory, type):
            raise TypeError('TRUSTED_FACTORY_CLASS_REQUIRED')
        plugin = factory()
        manifest = plugin.manifest()
        if (not isinstance(manifest, Manifest) or not manifest.operations
                or plugin.health() is not True or plugin.self_test() is not True
                or any(op.effects or not op.deterministic for op in manifest.operations)):
            raise PermissionError('WARM_REQUIRES_TRUSTED_PURE_FACTORY')
        self.factory = factory
        self._operations = frozenset(op.name for op in manifest.operations)
        self.target_ready = target_ready
        self.max_warm = max_warm
        self.max_cold_inflight = max_cold_inflight
        self._cold_active = 0
        self.overload_refusals = 0
        self.warmup_timeout_s = float(warmup_timeout_s)
        self.max_idle_s = float(max_idle_s)
        self._ctx = mp.get_context('spawn')
        self._cv = threading.Condition(threading.RLock())
        self._idle: list[_Slot] = []
        self._busy: dict[object, object] = {}  # process -> connection
        self._warming = 0  # reservations acquired BEFORE starting a thread
        self._warming_processes: set[object] = set()
        self._threads: set[threading.Thread] = set()
        self._started = False
        self._closed = False
        self.hits = 0
        self.misses = 0
        self.cold_fallbacks = 0
        self.warm_started = 0
        self.warmup_failures = 0
        self.max_observed_warm = 0

    def _total_locked(self):
        # The warming process set is a subset of reserved warming slots.
        return len(self._idle) + len(self._busy) + self._warming

    def _fill_locked(self):
        """Reserve before spawn; never launch > max_warm even during bursts."""
        if self._closed or not self._started:
            return
        while (len(self._idle) + self._warming < self.target_ready
               and self._total_locked() < self.max_warm):
            # Reserve from the process-wide budget BEFORE any spawn. Other
            # pools for HDC/KAN/SSM must not create their own four each.
            if not _GLOBAL_WARM_BUDGET.reserve():
                break
            self._warming += 1
            self.max_observed_warm = max(self.max_observed_warm, self._total_locked())
            thread = threading.Thread(target=self._prepare, name='cognitum-warm-refill', daemon=True)
            self._threads.add(thread)
            try:
                thread.start()
            except RuntimeError:
                self._threads.discard(thread)
                self._warming -= 1
                _GLOBAL_WARM_BUDGET.release()
                self.warmup_failures += 1
                break

    def start(self):
        with self._cv:
            if self._closed:
                raise RuntimeError('POOL_CLOSED')
            self._started = True
            self._fill_locked()

    def _prepare(self):
        parent = child = proc = None
        ready = False
        try:
            parent, child = self._ctx.Pipe(duplex=True)
            proc = self._ctx.Process(target=_worker_main, args=(child, self.factory), daemon=True)
            with self._cv:
                if self._closed:
                    return
                self._warming_processes.add(proc)
            proc.start()
            child.close()
            child = None
            if parent.poll(self.warmup_timeout_s) and parent.recv_bytes(MAX_MESSAGE_BYTES) == b'READY':
                ready = proc.is_alive()
        except (AssertionError, EOFError, OSError, RuntimeError, ValueError):
            ready = False
        finally:
            with self._cv:
                self._warming -= 1
                if proc is not None:
                    self._warming_processes.discard(proc)
                if ready and not self._closed:
                    self._idle.append(_Slot(proc, parent, time.monotonic()))
                    self.warm_started += 1
                    proc = parent = None
                else:
                    _GLOBAL_WARM_BUDGET.release()  # reserved but never admitted ready
                    if not self._closed:
                        self.warmup_failures += 1
                self._threads.discard(threading.current_thread())
                self._cv.notify_all()
            if child is not None:
                child.close()
            if proc is not None and parent is not None:
                _stop_and_reap(proc, parent)
            elif parent is not None:
                parent.close()

    def wait_ready(self, seconds=12.0, *, minimum=None):
        if minimum is None:
            minimum = self.target_ready
        if type(minimum) is not int or minimum < 1 or minimum > self.max_warm:
            raise ValueError('INVALID_READY_TARGET')
        end = time.monotonic() + seconds
        with self._cv:
            while not self._closed and len(self._idle) < minimum:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    break
                self._cv.wait(remaining)
            return not self._closed and len(self._idle) >= minimum

    def snapshot(self):
        with self._cv:
            return dict(idle=len(self._idle), warming=self._warming,
                        busy=len(self._busy), warm_total=self._total_locked(),
                        max_warm=self.max_warm, target_ready=self.target_ready,
                        max_observed_warm=self.max_observed_warm,
                        global_warm_budget=_GLOBAL_WARM_BUDGET.snapshot(),
                        hits=self.hits, misses=self.misses,
                        cold_fallbacks=self.cold_fallbacks,
                        cold_active=self._cold_active,
                        max_cold_inflight=self.max_cold_inflight,
                        overload_refusals=self.overload_refusals,
                        warm_started=self.warm_started,
                        warmup_failures=self.warmup_failures, closed=self._closed)

    def execute(self, factory, operation, payload, timeout_ms):
        if factory is not self.factory:
            raise ValueError('WARM_FACTORY_MISMATCH')
        if operation not in self._operations:
            raise PermissionError('WARM_OPERATION_NOT_DECLARED')
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 10000:
            raise ValueError('INVALID_EXECUTION_DEADLINE')
        data = json.dumps({'operation': operation, 'payload': payload},
                          allow_nan=False, separators=(',', ':')).encode()
        if len(data) > MAX_MESSAGE_BYTES:
            raise ValueError('WARM_REQUEST_TOO_LARGE')
        expired = []
        with self._cv:
            if self._closed:
                raise RuntimeError('POOL_CLOSED')
            # A trusted first invocation may arrive before an explicit start.
            # Dispatch cold without delay, but begin standby preparation.
            self._started = True
            slot = None
            cold_denied = False
            while self._idle:
                candidate = self._idle.pop()
                if (time.monotonic() - candidate.ready_at > self.max_idle_s
                        or not candidate.process.is_alive()):
                    expired.append(candidate)
                else:
                    slot = candidate
                    break
            if slot is None:
                self.misses += 1
                if self._cold_active < self.max_cold_inflight:
                    self._cold_active += 1
                    self.cold_fallbacks += 1
                else:
                    self.overload_refusals += 1
                    cold_denied = True
            else:
                self._busy[slot.process] = slot.connection
                self.hits += 1
            if not expired:
                self._fill_locked()  # no physical stale workers outside accounting
        for stale in expired:
            _stop_and_reap(stale.process, stale.connection)
            _GLOBAL_WARM_BUDGET.release()
        if expired:
            with self._cv:
                self._fill_locked()  # replace only AFTER stale processes are reaped
        if slot is None:
            # A capacity refusal does not start any additional process.
            # Use the per-invocation admission decision, not current global
            # pressure, which can change while the caller cleans stale slots.
            if cold_denied:
                return 'error', None
            # Fallback keeps the P2 disposable-worker lifecycle, but a pool
            # shutdown must not release a late result to the caller.
            try:
                status, result = cold_execute(factory, operation, payload, timeout_ms)
                with self._cv:
                    if self._closed:
                        return 'error', None
                return status, result
            finally:
                with self._cv:
                    self._cold_active -= 1
                    self._cv.notify_all()
        try:
            slot.connection.send_bytes(data)
            if not slot.connection.poll(timeout_ms / 1000):
                return 'timed_out', None
            raw = slot.connection.recv_bytes(MAX_MESSAGE_BYTES)
            reply = json.loads(raw)
            with self._cv:
                if self._closed:
                    return 'error', None
            if (type(reply) is not dict or set(reply) != {'status', 'result'}
                    or reply['status'] not in ('ok', 'error', 'invalid_input')
                    or (reply['status'] != 'ok' and reply['result'] is not None)):
                return 'error', None
            return reply['status'], reply['result']
        except (OSError, EOFError, ValueError, TypeError, BrokenPipeError):
            return 'error', None
        finally:
            _stop_and_reap(slot.process, slot.connection)
            _GLOBAL_WARM_BUDGET.release()
            with self._cv:
                self._busy.pop(slot.process, None)
                self._fill_locked()
                self._cv.notify_all()

    def close(self):
        with self._cv:
            if self._closed:
                return
            self._closed = True
            idle = self._idle
            self._idle = []
            active = tuple(self._busy)
            warming = tuple(self._warming_processes)
            threads = tuple(self._threads)
            self._cv.notify_all()
        for slot in idle:
            _stop_and_reap(slot.process, slot.connection)
            _GLOBAL_WARM_BUDGET.release()
        # Active executions and warming helpers reap their own child handles.
        for proc in (*active, *warming):
            try:
                if proc.pid is not None and proc.is_alive():
                    proc.terminate()
            except (OSError, ValueError, AssertionError):
                pass
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(self.warmup_timeout_s + 1)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
