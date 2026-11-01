"""Independent P3 opt-in warm standby lifecycle and fail-closed gates."""
import os
import time
import threading
from dataclasses import replace

import pytest

from cognitum.contracts import Request, HostContext, Manifest, Operation, Shape, Effect
from cognitum.plugins.calculator import Calculator
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.warm_worker import WarmSingleUsePool


def setup():
    registry = Registry()
    registry.install(Calculator, enabled=True)
    registry.nominate('calc', 'reference_calc')
    pool = WarmSingleUsePool(Calculator)
    runtime = Runtime(registry, warm_pool=pool)
    return pool, runtime


def req(value='2+3*4', *, request_id='warm-1', timeout=4000):
    return Request(request_id, 'one-turn', 'calc.rational',
                   {'expression': value}, timeout_ms=timeout)


def test_idle_standby_ready_then_first_operation_succeeds():
    pool, runtime = setup()
    try:
        pool.start()
        assert pool.wait_ready(10), 'spawn / import not ready'
        r = runtime.call(req(), HostContext('local', 'local-user'))
        assert r.execution_status == 'completed'
        assert r.result == {'value': '14'}
        assert pool.hits == 1 and pool.misses == 0
    finally:
        pool.close()


def test_single_use_does_not_keep_previous_task_worker_alive():
    pool, runtime = setup()
    try:
        pool.start()
        assert pool.wait_ready(10)
        with pool._lock:
            first = pool._slot.process
            pid = first.pid
        r = runtime.call(req(), HostContext('local', 'local-user'))
        assert r.execution_status == 'completed'
        assert not first.is_alive() if not first._closed else True
        assert pid != os.getpid()
        assert pool.wait_ready(10)
        with pool._lock:
            assert pool._slot.process.pid != pid
        r2=runtime.call(req('7/3+1/3',request_id='warm-2'), HostContext('local','local-user'))
        assert r2.result == {'value':'8/3'}
        assert pool.hits == 2
    finally:
        pool.close()


def test_rejected_input_remains_failed_and_replacement_can_work():
    pool, runtime = setup()
    try:
        pool.start()
        assert pool.wait_ready(10)
        bad=runtime.call(req('1/0'), HostContext('local','local-user'))
        assert bad.execution_status == 'invalid_input'
        assert bad.result is None
        assert pool.wait_ready(10)
        good=runtime.call(req('8+2',request_id='warm-next'), HostContext('local','local-user'))
        assert good.result == {'value':'10'}
    finally:
        pool.close()


def test_single_call_default_never_allocates_pool():
    registry=Registry();registry.install(Calculator,enabled=True);registry.nominate('calc','reference_calc')
    runtime=Runtime(registry)
    assert runtime.warm_pool is None
    r=runtime.call(req(),HostContext('local','local-user'))
    assert r.execution_status=='completed' and r.result=={'value':'14'}


def test_no_execute_before_host_authorization():
    pool, runtime=setup()
    try:
        pool.start()
        assert pool.wait_ready(10)
        denied=runtime.call(req(),HostContext('other','user'))
        assert denied.execution_status == 'denied'
        assert pool.hits == 0
        allowed=runtime.call(req(),HostContext('local','local-user'))
        assert allowed.execution_status == 'completed' and pool.hits == 1
    finally:
        pool.close()


def test_pool_refuses_forged_factory_and_undeclared_operation():
    pool,runtime=setup()
    try:
        with pytest.raises(ValueError,match='WARM_FACTORY_MISMATCH'):
            pool.execute(object,'calc.rational',{'expression':'1'},3000)
        with pytest.raises(PermissionError,match='WARM_OPERATION_NOT_DECLARED'):
            pool.execute(Calculator,'execute.other',{'expression':'1'},3000)
    finally:
        pool.close()


def test_no_effectful_factory_admitted():
    class Effectful:
        def manifest(self):
            return Manifest('example','0.1.0',(
                Operation('evil.op','test',Shape((('expression',50),)),Shape((('value',50),)),
                          effects=(Effect('write_file','scope'),)),))
    with pytest.raises(PermissionError,match='WARM_REQUIRES_TRUSTED_PURE_FACTORY'):
        WarmSingleUsePool(Effectful)


def test_caller_payload_mutation_after_validation_not_sent(monkeypatch):
    pool,rt=setup()
    request=req('1+1')
    try:
        pool.start();assert pool.wait_ready(10)
        original=pool.execute
        def tamper(factory,op,payload,deadline):
            request.payload['expression']='1/0'
            return original(factory,op,payload,deadline)
        monkeypatch.setattr(pool,'execute',tamper)
        result=rt.call(request,HostContext('local','local-user'))
        assert result.execution_status=='completed' and result.result=={'value':'2'}
    finally:
        pool.close()


def test_close_stops_idle_worker_and_rejects_more_work():
    pool,rt=setup()
    pool.start();assert pool.wait_ready(10)
    with pool._lock: pid=pool._slot.process.pid
    pool.close();pool.close()
    with pytest.raises(RuntimeError,match='POOL_CLOSED'):
        pool.execute(Calculator,'calc.rational',{'expression':'1+1'},3000)
    if os.name=='posix':
        with pytest.raises(ProcessLookupError):os.kill(pid,0)


def test_very_short_deadline_does_not_publish_late_result():
    pool,rt=setup()
    try:
        pool.start();assert pool.wait_ready(10)
        result=rt.call(req('1+1',timeout=1),HostContext('local','local-user'))
        assert result.execution_status in ('completed','timed_out')
        if result.execution_status=='timed_out':
            assert result.result is None
    finally:pool.close()


def test_readiness_miss_falls_back_to_existing_disposable_worker():
    pool,rt=setup()  # No pool.start() until first call.
    try:
        result=rt.call(req('3*3'),HostContext('local','local-user'))
        assert result.result=={'value':'9'} and pool.misses==1
    finally:pool.close()


def test_no_cross_task_python_instance_reuse():
    pool,rt=setup()
    try:
        pool.start();assert pool.wait_ready(10)
        x=rt.call(req('1000-1'),HostContext('local','local-user'))
        assert pool.wait_ready(10)
        y=rt.call(req('1+1',request_id='warm-after'),HostContext('local','local-user'))
        assert x.result=={'value':'999'} and y.result=={'value':'2'}
        assert pool.hits==2
    finally:pool.close()
