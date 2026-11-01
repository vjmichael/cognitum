"""P3 isolated worker deadline, authorization and concurrency regression."""
import threading
import time
from cognitum.contracts import Manifest, Operation, Shape, HostContext, Request
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_worker import WarmSingleUsePool


class SlowPure:
    def health(self): return True
    def self_test(self): return True
    def manifest(self):
        return Manifest('slow_pure', '0.1.0', (
            Operation('slow.wait', 'slow', Shape((('duration_ms',10),)), Shape((('value',20),))),
        ))

    def handle(self, operation, payload):
        time.sleep(int(payload['duration_ms']) / 1000)
        return {'value': 'done'}


def slow_setup():
    registry=Registry();registry.install(SlowPure,enabled=True);registry.nominate('slow','slow_pure')
    pool=WarmSingleUsePool(SlowPure)
    return Runtime(registry,warm_pool=pool),pool


def test_true_timeout_kills_a_warm_single_use_worker():
    runtime,pool=slow_setup()
    try:
        pool.start();assert pool.wait_ready(10)
        begin=time.perf_counter()
        response=runtime.call(Request('time-1','corr','slow.wait',{'duration_ms':'800'},timeout_ms=20), HostContext('local','local-user'))
        elapsed=time.perf_counter()-begin
        assert response.execution_status=='timed_out'
        assert response.result is None
        assert elapsed<0.7
        assert pool.hits==1
    finally: pool.close()


def test_close_during_active_warm_request_discards_late_response():
    runtime,pool=slow_setup()
    pool.start();assert pool.wait_ready(10)
    result=[]
    def run():
        result.append(runtime.call(Request('task-2','corr','slow.wait',{'duration_ms':'500'},timeout_ms=2000),HostContext('local','local-user')))
    thread=threading.Thread(target=run)
    thread.start()
    deadline=time.monotonic()+2
    while time.monotonic()<deadline and pool.hits==0:time.sleep(0.005)
    assert pool.hits==1
    pool.close()
    thread.join(3)
    assert not thread.is_alive()
    assert result and result[0].result is None
    assert result[0].execution_status!='completed'


def test_concurrent_requests_one_standby_other_cold():
    reg=Registry();reg.install(Calculator,enabled=True);reg.nominate('calc','reference_calc')
    pool=WarmSingleUsePool(Calculator)
    runtime=Runtime(reg,warm_pool=pool)
    try:
        pool.start();assert pool.wait_ready(10)
        gate=threading.Barrier(3)
        results=[]
        def run(i):
            gate.wait()
            results.append(runtime.call(Request(f'concurrent-{i}','same','calc.rational',{'expression':f'{i}+10'},timeout_ms=4000),HostContext('local','local-user')))
        threads=[threading.Thread(target=run,args=(i,)) for i in (1,2)]
        for thread in threads:thread.start()
        gate.wait()
        for thread in threads:thread.join(6)
        assert not any(t.is_alive() for t in threads)
        assert sorted(r.result['value'] for r in results)==['11','12']
        assert pool.hits>=1
        assert pool.misses<=1
    finally:pool.close()
