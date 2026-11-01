"""P5: two default standbys, one minimum, four globally, adapt without unbounded spawn."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest
from cognitum.contracts import HostContext
from cognitum.plugins.calculator import Calculator
from cognitum.warm_pool import (WarmCappedPool, global_warm_budget_snapshot,
                                  DEFAULT_WARM_WORKERS, MIN_WARM_WORKERS,
                                  MAX_WARM_WORKERS)
from tests.test_warm_pool_p4 import setup, slow_req, calc_req
from tests.test_warm_worker_edge_p3 import SlowPure


def test_default_two_floor_one_ceiling_four():
    p=WarmCappedPool(Calculator)
    try:
        assert (MIN_WARM_WORKERS, DEFAULT_WARM_WORKERS, MAX_WARM_WORKERS)==(1,2,4)
        snap=p.snapshot()
        assert (snap['min_ready'],snap['target_ready'],snap['max_warm'])==(1,2,4)
        assert snap['warm_total']==0
        p.start()
        assert p.wait_ready(15)
        assert p.snapshot()['idle']==2
    finally: p.close()
    assert global_warm_budget_snapshot()['reserved']==0


@pytest.mark.parametrize('bad', [0,5,True,1.1,'2',None])
def test_trusted_capacity_rejects_out_of_range(bad):
    p=WarmCappedPool(Calculator)
    try:
        with pytest.raises(ValueError): p.set_target_ready(bad)
    finally:p.close()


def test_manual_memory_pressure_downshift_to_minimum_reaps_extra():
    p=WarmCappedPool(Calculator)
    try:
        p.start();assert p.wait_ready(15)
        with p._cv: discarded={s.process.pid for s in p._idle}
        result=p.set_target_ready(1)
        assert result['target_ready']==1
        assert result['idle']==1
        assert global_warm_budget_snapshot()['reserved']==1
        with p._cv: retained={s.process.pid for s in p._idle}
        assert len(discarded-retained)==1
        p.set_target_ready(4)
        assert p.wait_ready(15)
        assert p.snapshot()['idle']==4
        assert p.snapshot()['max_observed_warm']<=4
    finally:p.close()
    assert global_warm_budget_snapshot()['reserved']==0


def test_adaptive_pressure_grows_two_to_four_and_fifth_falls_cold():
    runtime,p=setup(SlowPure,target=2)
    try:
        p.start();assert p.wait_ready(15)
        barrier=threading.Barrier(6)
        def worker(i):
            barrier.wait(timeout=6)
            return runtime.call(slow_req(i,duration='650',timeout=4500),HostContext('local','local-user'))
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures=[executor.submit(worker,i) for i in range(5)]
            barrier.wait(timeout=6)
            results=[f.result(timeout=12) for f in futures]
        assert all(r.result=={'value':'done'} for r in results)
        snap=p.snapshot()
        assert 2 <= snap['target_ready']<=4 and snap['max_observed_warm']<=4
        assert snap['hits']>=2 and snap['misses']>=1
        assert snap['upshifts']>=1, snap
        assert snap['cold_active']==0
        assert global_warm_budget_snapshot()['reserved']<=4
    finally:p.close()
    assert global_warm_budget_snapshot()['reserved']==0


def test_idle_maintenance_decrements_to_one_and_new_request_restores_two():
    runtime,p=setup(target=4)
    try:
        p.start();assert p.wait_ready(15)
        for expected in (3,2,1):
            with p._cv:
                # Simulate a periodic host tick after the configured idle window.
                p._last_request_at=time.monotonic()-p.idle_downshift_s-5
                p._last_downshift_at=time.monotonic()-p.idle_downshift_s-5
            after=p.maintain()
            assert after['target_ready']==expected,after
            assert after['idle']==expected
            assert after['min_ready']==1
            assert after['warm_total']<=4
        p.maintain()
        assert p.snapshot()['target_ready']==1
        result=runtime.call(calc_req(150,'10+2'),HostContext('local','local-user'))
        assert result.result=={'value':'12'}
        assert p.snapshot()['target_ready']==4  # Baseline for explicit target=4.
        assert p.wait_ready(15)
    finally:p.close()
    assert global_warm_budget_snapshot()['reserved']==0


def test_default_two_returns_to_two_after_long_idle():
    runtime,p=setup(target=2)
    try:
        p.start();assert p.wait_ready(15)
        with p._cv:
            p._last_request_at=time.monotonic()-10000
            p._last_downshift_at=time.monotonic()-10000
        assert p.maintain()['target_ready']==1
        assert p.snapshot()['idle']==1
        result=runtime.call(calc_req(160,'2+2'),HostContext('local','local-user'))
        assert result.result=={'value':'4'}
        assert p.snapshot()['target_ready']==2
        assert p.wait_ready(15)
    finally:p.close()
    assert global_warm_budget_snapshot()['reserved']==0


def test_no_idle_downshift_without_trusted_host_maintenance_tick():
    p=WarmCappedPool(Calculator,idle_downshift_s=1)
    try:
        p.start();assert p.wait_ready(15)
        with p._cv:
            p._last_request_at=time.monotonic()-15
            p._last_downshift_at=time.monotonic()-15
        assert p.snapshot()['target_ready']==2
        assert p.maintain()['target_ready']==1
    finally:p.close()


def test_adaptive_off_maintains_configured_capacity_under_overflow():
    runtime,p=setup(SlowPure,target=2)
    p.adaptive=False
    try:
        p.start();assert p.wait_ready(15)
        barrier=threading.Barrier(4)
        def one(i):
            barrier.wait(timeout=5)
            return runtime.call(slow_req(i,duration='450'),HostContext('local','local-user'))
        with ThreadPoolExecutor(max_workers=3) as ex:
            f=[ex.submit(one,i) for i in range(3)]
            barrier.wait(timeout=5)
            assert all(x.result(timeout=10).execution_status=='completed' for x in f)
        assert p.snapshot()['target_ready']==2
        assert p.snapshot()['upshifts']==0
    finally:p.close()


def test_global_four_prewarms_shared_between_two_default_pools():
    p1=WarmCappedPool(Calculator)
    p2=WarmCappedPool(SlowPure)
    try:
        p1.start();p2.start()
        assert p1.wait_ready(15) and p2.wait_ready(15)
        assert p1.snapshot()['idle']==2 and p2.snapshot()['idle']==2
        assert global_warm_budget_snapshot()['reserved']==4
        p1.set_target_ready(4)
        # No allocation beyond the global cap while the second pool is active.
        assert p1.snapshot()['warm_total']==2
        p2.close()
        p1.start()
        assert p1.wait_ready(15,minimum=4)
        assert global_warm_budget_snapshot()['reserved']==4
    finally:
        p1.close();p2.close()
    assert global_warm_budget_snapshot()['reserved']==0


def test_invalid_adaptive_configuration_rejected():
    with pytest.raises(ValueError):WarmCappedPool(Calculator,adaptive='yes')
    with pytest.raises(ValueError):WarmCappedPool(Calculator,idle_downshift_s=0)
    with pytest.raises(ValueError):WarmCappedPool(Calculator,target_ready=2,min_ready=3)
