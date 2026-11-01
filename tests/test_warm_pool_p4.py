"""P4 warm standby <=4 acceptance: concurrency, cancellation and cold overflow."""
from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time

import pytest

from cognitum.contracts import HostContext, Request
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_pool import WarmCappedPool, MAX_WARM_WORKERS
from tests.test_warm_worker_edge_p3 import SlowPure


def setup(factory=Calculator, *, target=4, max_warm=4):
    registry = Registry()
    registry.install(factory, enabled=True)
    name = factory().manifest().name
    slot = factory().manifest().operations[0].slot
    registry.nominate(slot, name)
    pool = WarmCappedPool(factory, target_ready=target, max_warm=max_warm)
    return Runtime(registry, warm_pool=pool), pool


def slow_req(i, duration='700', timeout=4000):
    return Request(f'p4-slow-{i}', 'one-task', 'slow.wait',
                   {'duration_ms': duration}, timeout_ms=timeout)


def calc_req(i, expression=None):
    return Request(f'p4-calc-{i}', 'same', 'calc.rational',
                   {'expression': expression or f'{i}+11'}, timeout_ms=4000)


@pytest.mark.parametrize('target,ceiling', [(0,4),(5,5),(4,5),(5,4),(1,0),(True,4),(2,False)])
def test_hard_maximum_never_above_four(target, ceiling):
    with pytest.raises(ValueError, match='WARM_WORKER_LIMIT'):
        WarmCappedPool(Calculator, target_ready=target, max_warm=ceiling)


def test_default_is_one_standby_and_no_spawn_before_explicit_start():
    pool = WarmCappedPool(Calculator)
    try:
        assert pool.snapshot()['warm_total'] == 0
        assert pool.target_ready == 1 and pool.max_warm == 4
        pool.start()
        assert pool.wait_ready(12)
        assert pool.snapshot()['idle'] == 1
    finally:
        pool.close()


def test_four_ready_standbys_and_unique_pids():
    _, pool = setup()
    try:
        pool.start()
        assert pool.wait_ready(15)
        with pool._cv:
            pids = [s.process.pid for s in pool._idle]
        assert len(pids) == len(set(pids)) == 4
        snapshot = pool.snapshot()
        assert snapshot['idle'] == 4 and snapshot['warm_total'] == 4
        assert snapshot['max_observed_warm'] <= MAX_WARM_WORKERS
    finally:
        pool.close()


def test_four_parallel_warm_and_fifth_cold_no_queue():
    runtime, pool = setup(SlowPure)
    try:
        pool.start()
        assert pool.wait_ready(15)
        barrier = threading.Barrier(6)
        def task(i):
            barrier.wait(timeout=5)
            return runtime.call(slow_req(i), HostContext('local', 'local-user'))
        with ThreadPoolExecutor(max_workers=5) as threads:
            futures = [threads.submit(task, i) for i in range(5)]
            barrier.wait(timeout=5)
            # Observe cap during the five concurrent calls.
            deadline = time.monotonic() + 5
            observed = []
            while time.monotonic() < deadline and sum([pool.hits,pool.misses]) < 5:
                observed.append(pool.snapshot()['warm_total'])
                time.sleep(0.01)
            outcomes = [f.result(timeout=12) for f in futures]
        assert all(r.execution_status == 'completed' and r.result == {'value':'done'} for r in outcomes)
        snap = pool.snapshot()
        assert snap['hits'] == 4, snap
        assert snap['misses'] == 1 and snap['cold_fallbacks'] == 1, snap
        assert max(observed, default=0) <= 4
        assert snap['max_observed_warm'] <= 4
        assert pool.wait_ready(15)
        assert pool.snapshot()['idle'] == 4
    finally:
        pool.close()


def test_more_than_four_requests_cold_fallback_preserves_results():
    runtime, pool = setup(target=4)
    try:
        pool.start()
        assert pool.wait_ready(15)
        # Brief calculations can finish before all threads have started; no
        # assertion about distribution, only correct results and global cap.
        def task(i):
            return runtime.call(calc_req(i), HostContext('local','local-user'))
        with ThreadPoolExecutor(max_workers=12) as threads:
            result = list(threads.map(task, range(12)))
        assert all(r.result == {'value': str(i+11)} for i,r in enumerate(result))
        assert pool.snapshot()['max_observed_warm'] <= 4
    finally: pool.close()


def test_replenishment_does_not_reuse_completed_worker_pid():
    runtime, pool=setup()
    try:
        pool.start(); assert pool.wait_ready(15)
        with pool._cv:
            old = {s.process.pid for s in pool._idle}
        first=runtime.call(calc_req(0), HostContext('local','local-user'))
        assert first.execution_status=='completed'
        assert pool.wait_ready(15)
        with pool._cv:
            new = {s.process.pid for s in pool._idle}
        assert len(new) == 4 and len(new-old)==1
        assert pool.snapshot()['warm_total']==4
    finally: pool.close()


def test_short_deadline_without_late_response():
    runtime, pool=setup(SlowPure)
    try:
        pool.start(); assert pool.wait_ready(15)
        outcome=runtime.call(slow_req(1,duration='800',timeout=20),HostContext('local','local-user'))
        assert outcome.execution_status == 'timed_out'
        assert outcome.result is None
        assert pool.wait_ready(15)
    finally: pool.close()


def test_close_during_four_busy_workers_refuses_all_late_results():
    runtime, pool=setup(SlowPure)
    pool.start(); assert pool.wait_ready(15)
    results=[]
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures=[executor.submit(runtime.call,slow_req(i,duration='1500'),HostContext('local','local-user')) for i in range(4)]
            deadline=time.monotonic()+5
            while pool.snapshot()['hits'] < 4 and time.monotonic()<deadline:
                time.sleep(0.01)
            assert pool.snapshot()['hits']==4
            pool.close()
            results=[f.result(timeout=6) for f in futures]
        assert all(r.result is None and r.execution_status != 'completed' for r in results)
    finally: pool.close()


def test_cold_fallback_when_start_not_yet_ready():
    runtime, pool=setup()
    try:
        result=runtime.call(calc_req(3),HostContext('local','local-user'))
        assert result.result=={'value':'14'}
        assert pool.snapshot()['misses']==1
        assert pool.wait_ready(15)
    finally: pool.close()


def test_unapproved_operation_rejected_without_consuming_worker():
    runtime,pool=setup()
    try:
        pool.start();assert pool.wait_ready(15)
        denied = runtime.call(calc_req(1),HostContext('wrong','identity'))
        assert denied.execution_status=='denied'
        assert pool.snapshot()['hits']==0
        with pytest.raises(PermissionError,match='WARM_OPERATION_NOT_DECLARED'):
            pool.execute(Calculator,'fake.op',{},2000)
        assert pool.snapshot()['idle']==4
    finally:pool.close()


def test_expired_workers_reaped_before_replacements_spawned():
    runtime,pool=setup(target=4)
    pool.max_idle_s=1
    try:
        pool.start();assert pool.wait_ready(15)
        with pool._cv:
            old_pids=[s.process.pid for s in pool._idle]
        time.sleep(1.15)
        result=runtime.call(calc_req(1),HostContext('local','local-user'))
        assert result.result=={'value':'12'}
        assert pool.snapshot()['max_observed_warm'] <= 4
        assert pool.wait_ready(15)
        with pool._cv:
            new_pids=[s.process.pid for s in pool._idle]
        assert not (set(old_pids) & set(new_pids))
    finally:pool.close()


def test_malformed_or_oversize_message_rejected_before_worker_claim():
    _,pool=setup()
    try:
        pool.start();assert pool.wait_ready(15)
        with pytest.raises(ValueError,match='WARM_REQUEST_TOO_LARGE'):
            pool.execute(Calculator,'calc.rational',{'expression':'X'*70000},2000)
        assert pool.snapshot()['hits']==0
    finally:pool.close()


def test_close_during_cold_overflow_discards_late_result():
    runtime,pool=setup(SlowPure,target=1)
    output=[]
    started=threading.Event()
    try:
        # No standby: request falls back to a disposable process, while
        # prewarming begins asynchronously in the background.
        def task():
            started.set()
            output.append(runtime.call(slow_req(10,duration='650'),HostContext('local','local-user')))
        thread=threading.Thread(target=task)
        thread.start()
        assert started.wait(2)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline and not pool.snapshot()['misses']:
            time.sleep(.01)
        assert pool.snapshot()['misses']==1
        pool.close()
        thread.join(6)
        assert not thread.is_alive()
        assert len(output)==1
        assert output[0].result is None
        assert output[0].execution_status!='completed'
    finally: pool.close()


def test_cold_overflow_has_separate_bounded_concurrency_limit():
    runtime,pool=setup(SlowPure, target=1)
    pool.max_cold_inflight=2
    try:
        pool.start(); assert pool.wait_ready(15)
        barrier=threading.Barrier(8)
        def launch(i):
            barrier.wait(timeout=5)
            return runtime.call(slow_req(100+i,duration='850'),HostContext('local','local-user'))
        with ThreadPoolExecutor(max_workers=7) as ex:
            futures=[ex.submit(launch,i) for i in range(7)]
            barrier.wait(timeout=5)
            outcomes=[f.result(timeout=10) for f in futures]
        assert sum(x.execution_status=='completed' for x in outcomes) == 3
        assert sum(x.execution_status!='completed' for x in outcomes) == 4
        assert pool.snapshot()['hits'] == 1
        assert pool.snapshot()['cold_fallbacks'] == 2
        assert pool.snapshot()['overload_refusals'] == 4
        assert pool.snapshot()['cold_active'] == 0
        assert pool.snapshot()['max_observed_warm'] <= 4
    finally: pool.close()


def test_four_process_global_budget_shared_across_two_capability_pools():
    from cognitum.warm_pool import global_warm_budget_snapshot
    p1=WarmCappedPool(Calculator,target_ready=3,max_warm=4)
    p2=WarmCappedPool(SlowPure,target_ready=3,max_warm=4)
    try:
        p1.start(); assert p1.wait_ready(15)
        p2.start(); assert p2.wait_ready(15,minimum=1)
        s1=p1.snapshot();s2=p2.snapshot()
        assert s1['idle']==3 and s2['idle']==1
        assert global_warm_budget_snapshot()['reserved']==4
        assert global_warm_budget_snapshot()['peak']<=4
        # Explicit refresh when a different provider releases capacity.
        p1.close()
        p2.start()
        assert p2.wait_ready(15,minimum=3)
        assert p2.snapshot()['idle']==3
        assert global_warm_budget_snapshot()['reserved']==3
    finally:
        p1.close();p2.close()
    assert global_warm_budget_snapshot()['reserved']==0


def test_parallel_pool_startups_share_global_ceiling_without_race():
    from cognitum.warm_pool import global_warm_budget_snapshot
    p1=WarmCappedPool(Calculator,target_ready=4,max_warm=4)
    p2=WarmCappedPool(SlowPure,target_ready=4,max_warm=4)
    try:
        barrier=threading.Barrier(3)
        def run(pool):
            barrier.wait(timeout=5)
            pool.start()
        with ThreadPoolExecutor(max_workers=2) as executor:
            a=executor.submit(run,p1);b=executor.submit(run,p2)
            barrier.wait(timeout=5)
            a.result(timeout=5);b.result(timeout=5)
        # Allow both sets of preparers to finish their bounded startup.
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            x=p1.snapshot();y=p2.snapshot()
            assert x['warm_total']+y['warm_total'] <=4
            assert global_warm_budget_snapshot()['reserved']<=4
            if x['warming']==y['warming']==0:
                break
            time.sleep(.01)
        assert p1.snapshot()['idle']+p2.snapshot()['idle']==4
        assert global_warm_budget_snapshot()['peak']<=4
    finally:p1.close();p2.close()
    assert global_warm_budget_snapshot()['reserved']==0
