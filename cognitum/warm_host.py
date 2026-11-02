"""Explicit trusted host service for maintaining prewarmed Cognitum pools.

This is opt-in lifecycle orchestration. It never authorizes a request, runs a
scientific operation, or grants any process an OS sandbox. The embedding host
must create and own trusted pools and explicitly start/close this service.
"""
from __future__ import annotations

import threading
import time

from .warm_pool import WarmCappedPool, global_warm_budget_snapshot
from .sandbox_warm_pool import LinuxSandboxWarmPool
from .worker_budget import global_cold_budget_snapshot


class TrustedWarmMaintenance:
    """A small, bounded host-owned maintenance thread, NOT a model tool.

    Maintenance is deliberately outside the request critical path. On each
    periodic tick it calls the existing idle/pressure policy. close() stops
    ticks before disposing workers; no zombie maintenance thread survives.
    """

    def __init__(self, pools, *, interval_s=0.25):
        if type(pools) not in (tuple, list) or not 1 <= len(pools) <= 4:
            raise ValueError('INVALID_HOST_POOL_COUNT')
        if any(type(pool) not in (WarmCappedPool, LinuxSandboxWarmPool) for pool in pools):
            raise TypeError('TRUSTED_WARM_POOL_REQUIRED')
        if len({id(pool) for pool in pools}) != len(pools):
            raise ValueError('DUPLICATE_POOL')
        if type(interval_s) not in (float, int) or not 0.05 <= interval_s <= 60:
            raise ValueError('INVALID_MAINTENANCE_PERIOD')
        self._pools = tuple(pools)
        self._interval = float(interval_s)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._started = False
        self._closed = False
        self.ticks = 0
        self.failures = 0

    def start(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('HOST_MAINTENANCE_CLOSED')
            if self._started:
                return
            self._started = True
            for pool in self._pools:
                pool.start()
            self._thread = threading.Thread(target=self._loop,
                                            name='cognitum-trusted-maintenance', daemon=True)
            self._thread.start()

    def _loop(self):
        while not self._stop.wait(self._interval):
            for pool in self._pools:
                if self._stop.is_set():
                    return
                try:
                    pool.maintain()
                except Exception:
                    # A bad tick cannot mint authority or leak tool data. Record
                    # failure; isolate broken pools to host diagnostics.
                    with self._lock:
                        self.failures += 1
            with self._lock:
                self.ticks += 1

    def snapshot(self):
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            ticks = self.ticks
            failures = self.failures
            closed = self._closed
        return {'running': running, 'ticks': ticks, 'failures': failures,
                'closed': closed, 'warm': global_warm_budget_snapshot(),
                'cold': global_cold_budget_snapshot(),
                'pools': [p.snapshot() for p in self._pools]}

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(3.0, self._interval * 2))
        for pool in self._pools:
            pool.close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()
