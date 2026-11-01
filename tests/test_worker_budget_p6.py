"""P6: one cold-worker budget across standalone, batch, and warm overflow."""
from __future__ import annotations

import time

import pytest

from cognitum.worker_budget import (
    MAX_COLD_WORKERS, global_cold_budget_snapshot, reserve_cold, release_cold,
)
from cognitum.worker import execute, execute_batch
from cognitum.plugins.calculator import Calculator
from cognitum.contracts import Request, HostContext
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_pool import WarmCappedPool, global_warm_budget_snapshot
from tests.test_warm_worker_edge_p3 import SlowPure


def test_global_cold_budget_has_bounded_reservations():
    assert global_cold_budget_snapshot()['active'] == 0
    slots = 0
    try:
        for _ in range(MAX_COLD_WORKERS):
            assert reserve_cold()
            slots += 1
        assert not reserve_cold()
        snap = global_cold_budget_snapshot()
        assert snap['active'] == snap['limit'] == MAX_COLD_WORKERS
        assert snap['peak'] <= MAX_COLD_WORKERS
    finally:
        for _ in range(slots):
            release_cold()
    assert global_cold_budget_snapshot()['active'] == 0


def test_direct_and_batch_share_the_same_global_cold_capacity():
    slots=0
    try:
        for _ in range(MAX_COLD_WORKERS):
            assert reserve_cold()
            slots += 1
        status, value = execute(Calculator, 'calc.rational', {'expression': '2+2'}, 2000)
        assert (status,value)==('overloaded',None)
        status, value = execute_batch(Calculator, [('calc.rational',{'expression':'2+2'})],2000)
        assert (status,value)==('overloaded',None)
        registry=Registry();registry.install(Calculator,enabled=True);registry.nominate('calc','reference_calc')
        runtime=Runtime(registry)
        out=runtime.call(Request('p6-overloaded','p6','calc.rational',{'expression':'2+2'}),HostContext('local','local-user'))
        assert out.execution_status=='error' and out.error=='worker_capacity_exhausted' and out.result is None
        request=Request('p6-batch-overloaded','p6','calc.rational',{'expression':'2+2'})
        batched=runtime.call_batch([request],HostContext('local','local-user'),trusted_batch_opt_in=True)
        assert len(batched)==1 and batched[0].execution_status=='error' and batched[0].error=='worker_capacity_exhausted'
    finally:
        for _ in range(slots):release_cold()
    assert global_cold_budget_snapshot()['active']==0


def test_pool_cold_overflow_respects_direct_worker_global_capacity():
    pool=WarmCappedPool(Calculator)
    slots=0
    try:
        for _ in range(MAX_COLD_WORKERS):
            assert reserve_cold();slots += 1
        # No pool.start(): the first request cannot claim a warm worker.
        status, data=pool.execute(Calculator,'calc.rational',{'expression':'1+1'},2000)
        assert (status,data)==('overloaded',None)
        assert pool.snapshot()['cold_active']==0
        assert global_cold_budget_snapshot()['active']==MAX_COLD_WORKERS
        assert global_warm_budget_snapshot()['reserved']<=4
    finally:
        for _ in range(slots):release_cold()
        pool.close()
    assert global_cold_budget_snapshot()['active']==0
    assert global_warm_budget_snapshot()['reserved']==0


def test_cold_timed_out_process_releases_reservation():
    status, value=execute(SlowPure,'slow.wait',{'duration_ms':'500'}, 50)
    assert (status,value)==('timed_out',None)
    assert global_cold_budget_snapshot()['active']==0


def test_normal_worker_remains_unchanged_when_capacity_available():
    status, value=execute(Calculator,'calc.rational',{'expression':'5*5'}, 3500)
    assert (status,value)==('ok',{'value':'25'})
    assert global_cold_budget_snapshot()['active']==0


def test_batch_worker_releases_reservation_after_success():
    status, results=execute_batch(Calculator, [('calc.rational',{'expression':'1+1'}),('calc.rational',{'expression':'2+2'})],3500)
    assert status=='ok' and results==[{'value':'2'},{'value':'4'}]
    assert global_cold_budget_snapshot()['active']==0


def test_budget_underflow_never_silently_ignores_double_release():
    assert global_cold_budget_snapshot()['active']==0
    with pytest.raises(RuntimeError,match='COLD_BUDGET_UNDERFLOW'):
        release_cold()


def test_ten_simultaneous_cold_calls_never_spawn_more_than_eight():
    """Real spawned children: overload is rejected without waiting for a slot."""
    import concurrent.futures
    import threading
    barrier = threading.Barrier(11)
    results = []
    def run(i):
        barrier.wait(timeout=8)
        return execute(SlowPure, 'slow.wait', {'duration_ms': '900'}, 4000)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(run,i) for i in range(10)]
        barrier.wait(timeout=8)
        results = [future.result(timeout=8) for future in futures]
    successful = sum(status=='ok' for status,_ in results)
    overloaded = sum(status=='overloaded' for status,_ in results)
    assert successful==MAX_COLD_WORKERS and overloaded==2, results
    assert all(value=={'value':'done'} if status=='ok' else value is None
               for status,value in results)
    snap = global_cold_budget_snapshot()
    assert snap['peak'] <= MAX_COLD_WORKERS
    assert snap['active'] == 0
