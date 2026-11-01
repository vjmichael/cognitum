"""Process-local budget across normal, batch, and warm-overflow cold workers.

This is admission control, *not* a security sandbox. The reservation remains
held until a worker has been reaped, not merely until its result is received.
"""
from __future__ import annotations

from threading import Lock

MAX_COLD_WORKERS = 8


class _ColdBudget:
    def __init__(self):
        self._lock = Lock()
        self._active = 0
        self._peak = 0
        self._denials = 0

    def acquire(self):
        with self._lock:
            if self._active >= MAX_COLD_WORKERS:
                self._denials += 1
                return False
            self._active += 1
            self._peak = max(self._peak, self._active)
            return True

    def release(self):
        with self._lock:
            if not self._active:
                raise RuntimeError('COLD_BUDGET_UNDERFLOW')
            self._active -= 1

    def snapshot(self):
        with self._lock:
            return {'active': self._active, 'peak': self._peak,
                    'limit': MAX_COLD_WORKERS, 'denials': self._denials}


_BUDGET = _ColdBudget()


def reserve_cold():
    return _BUDGET.acquire()


def release_cold():
    _BUDGET.release()


def global_cold_budget_snapshot():
    return _BUDGET.snapshot()
