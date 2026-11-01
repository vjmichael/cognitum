"""Optional single-use prewarmed Python worker for trusted, pure operations.

NOT an OS sandbox or a secure arbitrary-code host. A worker is used for ONE
request and reaped; at most one IDLE worker is retained. Prewarming prepares
an already-trusted factory (and imports) without any user task data. The normal
Runtime.call/worker.execute path remains the fallback and default.
"""
from __future__ import annotations

import multiprocessing as mp
import threading
import time
from dataclasses import dataclass

from .worker import execute as cold_execute


@dataclass
class _Slot:
    process: object
    conn: object
    ready_at: float


def _single_use_ready_worker(connection, factory):
    """One factory instance, one operation, one result, then unconditional exit."""
    try:
        plugin = factory()  # Import and prepare trusted provider before READY.
        connection.send(("READY", None))
        try:
            call = connection.recv()
        except (EOFError, OSError):
            return
        if type(call) is not tuple or len(call) != 2:
            return
        operation, payload = call
        try:
            result = plugin.handle(operation, payload)
            connection.send(("ok", result))
        except ValueError:
            connection.send(("invalid_input", None))
        except BaseException:
            connection.send(("error", None))
    except BaseException:
        # A failed initializer never becomes available to the trusted host.
        try:
            connection.send(("ERROR", None))
        except (OSError, EOFError, BrokenPipeError):
            pass
    finally:
        connection.close()


class WarmSingleUsePool:
    """One idle, one-shot, opt-in prewarm slot for a trusted factory.

    Calling start() during application/session initialization hides spawn and
    import cost from later tool latency. execute() never waits for a worker to
    become ready: a cold, disposable worker handles a miss. After a warm hit,
    an asynchronous replacement is scheduled for *subsequent* work.
    """

    def __init__(self, factory, *, warmup_timeout_s=10.0, max_idle_s=120.0):
        if not isinstance(warmup_timeout_s, (int, float)) or not 0.2 <= warmup_timeout_s <= 30:
            raise ValueError("INVALID_WARMUP_DEADLINE")
        if not isinstance(max_idle_s, (int, float)) or not 1 <= max_idle_s <= 3600:
            raise ValueError("INVALID_IDLE_TTL")
        # This is a performance adapter for vetted, pure built-ins ONLY.
        # A factory which declares any effectful/nondeterministic operation
        # cannot be prewarmed even if the caller invokes this object directly.
        from .contracts import Manifest
        if not isinstance(factory, type):
            raise TypeError("TRUSTED_FACTORY_CLASS_REQUIRED")
        manifest = factory().manifest()
        if (not isinstance(manifest, Manifest) or not manifest.operations
                or any(op.effects or not op.deterministic for op in manifest.operations)):
            raise PermissionError("WARM_REQUIRES_TRUSTED_PURE_FACTORY")
        self._operations = frozenset(op.name for op in manifest.operations)
        self.factory = factory
        self.warmup_timeout_s = float(warmup_timeout_s)
        self.max_idle_s = float(max_idle_s)
        self._ctx = mp.get_context("spawn")
        self._lock = threading.RLock()
        self._ready = threading.Event()
        self._ready.set()  # No prewarm in progress; close() must not block.
        self._slot = None
        self._warming = False
        self._closed = False
        self._active = set()
        self.hits = 0
        self.misses = 0
        self.startup_failures = 0
        self.last_warmup_ms = None

    def start(self):
        """Nonblocking prewarm; idempotent. Explicit host opt-in required."""
        with self._lock:
            if self._closed:
                raise RuntimeError("POOL_CLOSED")
            if self._warming or self._slot is not None:
                return
            self._warming = True
            self._ready.clear()
        threading.Thread(target=self._prepare, name="cognitum-prewarm", daemon=True).start()

    @staticmethod
    def _reap(process, conn):
        try:
            conn.close()
        except (OSError, ValueError):
            pass
        try:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(1.0)
                if process.is_alive():
                    process.kill()
                    process.join(1.0)
                process.close()
        except (OSError, ValueError, AssertionError):
            pass

    def _prepare(self):
        parent = child = proc = None
        started = time.perf_counter()
        usable = False
        try:
            parent, child = self._ctx.Pipe(duplex=True)
            proc = self._ctx.Process(target=_single_use_ready_worker,
                                     args=(child, self.factory), daemon=True)
            proc.start()
            child.close()
            child = None
            if parent.poll(self.warmup_timeout_s) and parent.recv() == ("READY", None):
                usable = proc.is_alive()
        except (OSError, EOFError, ValueError, AssertionError, TypeError):
            usable = False
        finally:
            with self._lock:
                self._warming = False
                if usable and not self._closed and self._slot is None:
                    self._slot = _Slot(proc, parent, time.monotonic())
                    self.last_warmup_ms = (time.perf_counter() - started) * 1000
                    parent = proc = None  # Ownership moves into the standby slot.
                else:
                    self.startup_failures += int(not self._closed)
                self._ready.set()
            if child is not None:
                child.close()
            if proc is not None and parent is not None:
                self._reap(proc, parent)
            elif parent is not None:
                parent.close()

    def wait_ready(self, seconds=12.0):
        """For explicit prewarm acceptance; not used by request dispatch."""
        self._ready.wait(seconds)
        with self._lock:
            return self._slot is not None and self._slot.process.is_alive()

    def execute(self, factory, operation, payload, timeout_ms):
        """Consume one ready worker or fail over to existing disposable execute."""
        if factory is not self.factory:
            raise ValueError("WARM_FACTORY_MISMATCH")
        if operation not in self._operations:
            raise PermissionError("WARM_OPERATION_NOT_DECLARED")
        with self._lock:
            if self._closed:
                raise RuntimeError("POOL_CLOSED")
            slot = self._slot
            self._slot = None
            if slot and (time.monotonic() - slot.ready_at > self.max_idle_s
                         or not slot.process.is_alive()):
                self._reap(slot.process, slot.conn)
                slot = None
            if slot:
                self.hits += 1
                self._active.add(slot.process)
            else:
                self.misses += 1
        self.start()  # Spawn replacement asynchronously; never block current request.
        if slot is None:
            return cold_execute(factory, operation, payload, timeout_ms)
        try:
            slot.conn.send((operation, payload))
            if not slot.conn.poll(timeout_ms / 1000):
                return "timed_out", None
            status, result = slot.conn.recv()
            with self._lock:
                if self._closed:  # A revoked/shutdown pool cannot publish late work.
                    return "error", None
            if status not in ("ok", "invalid_input", "error"):
                return "error", None
            return status, result
        except (OSError, EOFError, TypeError, ValueError, BrokenPipeError):
            return "error", None
        finally:
            self._reap(slot.process, slot.conn)
            with self._lock:
                self._active.discard(slot.process)

    def close(self):
        """Dispose unused worker and terminate any in-flight work; idempotent."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            slot = self._slot
            self._slot = None
            active = tuple(self._active)
        if slot is not None:
            self._reap(slot.process, slot.conn)
        # Active processes are shared with their execution callers; avoid
        # calling process.close from two threads. Terminate only; caller reaps.
        for process in active:
            try:
                if process.is_alive():
                    process.terminate()
            except (OSError, ValueError, AssertionError):
                pass
        self._ready.wait(self.warmup_timeout_s + 1.0)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()
