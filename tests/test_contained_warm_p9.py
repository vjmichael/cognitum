"""P9 real Linux namespace and lifecycle acceptance; no production sandbox claim."""
import threading
import time
import pytest
from cognitum.contained_warm_fleet import ContainedWarmFleet
from cognitum.sandbox_linux import LinuxNamespaceExecutor
from cognitum.sandbox_warm_pool import LinuxSandboxWarmPool
from cognitum.plugins.calculator import Calculator
from cognitum.plugins.specialists import Specialists
from cognitum.warm_pool import global_warm_budget_snapshot


def mk(factory=Calculator,**kw):
    return LinuxSandboxWarmPool(LinuxNamespaceExecutor(),factory,**kw)


def assert_clean():
    assert global_warm_budget_snapshot()['reserved']==0


def test_host_standby_two_total_one_per_provider_and_p7_proof():
    a,b=mk(Calculator),mk(Specialists)
    f=ContainedWarmFleet((a,b))
    try:
        f.start()
        assert a.wait_ready(12,minimum=1) and b.wait_ready(12,minimum=1)
        s=f.snapshot()
        assert s['allocation']=={'calculator':1,'specialists':1}
        assert s['warm_budget']['reserved']==2
        assert a.executor.test_probe('probe.isolation')[1]['inside_pid']==1
    finally:f.close()
    assert_clean()


def test_stale_worker_is_recycled_during_idle_maintenance():
    p=mk(target_ready=1,max_idle_s=1)
    try:
        p.start();assert p.wait_ready(10)
        old=p._idle[0].process.pid
        time.sleep(1.08)
        p.maintain()
        assert p.wait_ready(10,minimum=1)
        assert p._idle[0].process.pid!=old
        s=p.snapshot()
        assert s['expired_reaped']>=1
        assert s['global_warm_budget']['reserved']==1
        assert p.execute(Calculator,'calc.rational',{'expression':'4*8'},5000)==('ok',{'value':'32'})
    finally:p.close()
    assert_clean()


def test_exited_idle_worker_replaced_without_cold_first_request():
    p=mk(target_ready=1)
    try:
        p.start();assert p.wait_ready(10)
        proc=p._idle[0].process
        proc.kill();proc.wait(timeout=4)
        p.maintain()
        assert p.wait_ready(10,minimum=1)
        assert p.snapshot()['crashed_reaped']>=1
        assert p.execute(Calculator,'calc.rational',{'expression':'6*6'},5000)==('ok',{'value':'36'})
    finally:p.close()
    assert_clean()


def test_fleet_grows_after_miss_and_respects_four_global():
    a,b=mk(Calculator),mk(Specialists)
    f=ContainedWarmFleet((a,b))
    try:
        f.start();assert a.wait_ready(10,minimum=1) and b.wait_ready(10,minimum=1)
        # Consume one calculator without waiting for its replacement, causing
        # a second real operation to use P7's contained cold path.
        original=a.executor._exchange
        gate=threading.Event()
        def slow(proc,raw,timeout):
            gate.set(); time.sleep(.3)
            return original(proc,raw,timeout)
        a.executor._exchange=slow
        result=[]
        t=threading.Thread(target=lambda:result.append(a.execute(Calculator,'calc.rational',{'expression':'1+1'},5000)))
        t.start();assert gate.wait(5)
        second=a.execute(Calculator,'calc.rational',{'expression':'2+2'},5000)
        t.join(10)
        assert second==('ok',{'value':'4'}) and result==[('ok',{'value':'2'})]
        assert a.snapshot()['misses']>=1
        f.maintain()
        assert f.snapshot()['allocation']=={'calculator':2,'specialists':1}
        assert a.wait_ready(10,minimum=2)
        # Subsequent pressure signal through the same observed-miss counter
        # is handled by the trusted allocator; all reservations stay bounded.
        a.misses+=1  # host policy branch; first miss above was a real worker
        f.maintain()
        assert f.snapshot()['allocation']=={'calculator':3,'specialists':1}
        assert f.snapshot()['warm_budget']['reserved']<=4
        assert a.wait_ready(10,minimum=3)
    finally:f.close()
    assert_clean()


def test_pressure_reclaims_idle_and_relaxation_restores_default():
    a,b=mk(Calculator),mk(Specialists)
    f=ContainedWarmFleet((a,b))
    try:
        f.start();assert a.wait_ready(10,minimum=1) and b.wait_ready(10,minimum=1)
        a.misses+=1;f.maintain() # Test-only demand injection for policy unit branch.
        assert a.wait_ready(10,minimum=2)
        assert f.snapshot()['warm_budget']['reserved']==3
        f.maintain(pressure=True)
        assert f.snapshot()['allocation']=={'calculator':1,'specialists':1}
        assert f.snapshot()['warm_budget']['reserved']==2
        f.maintain(pressure=False)
        assert f.snapshot()['allocation']=={'calculator':1,'specialists':1}
    finally:f.close()
    assert_clean()


def test_one_provider_pressure_can_drop_to_minimum_one():
    a=mk(Calculator)
    f=ContainedWarmFleet((a,))
    try:
        f.start();assert a.wait_ready(10,minimum=2)
        f.maintain(pressure=True)
        assert f.snapshot()['allocation']=={'calculator':1}
        assert f.snapshot()['warm_budget']['reserved']==1
        f.maintain(pressure=False)
        assert f.snapshot()['allocation']=={'calculator':2}
        assert a.wait_ready(10,minimum=2)
    finally:f.close()
    assert_clean()


def test_quiet_reclaims_extra_capacity():
    a=mk(Calculator)
    f=ContainedWarmFleet((a,),quiet_s=1)
    try:
        f.start();assert a.wait_ready(10,minimum=2)
        a.misses+=1;f.maintain();assert f.snapshot()['allocation']=={'calculator':3}
        time.sleep(1.08)
        f.maintain()
        assert f.snapshot()['allocation']=={'calculator':2}
        assert f.snapshot()['warm_budget']['reserved']<=2
    finally:f.close()
    assert_clean()


def test_invalid_fleet_and_rejections_fail_closed():
    a=mk()
    assert_clean()
    with pytest.raises(ValueError,match='DUPLICATE_FLEET_PROVIDER'):
        ContainedWarmFleet((a,a))
    with pytest.raises(TypeError,match='FLEET_REQUIRES_P7'):
        ContainedWarmFleet((object(),))
    f=ContainedWarmFleet((a,))
    try:
        with pytest.raises(RuntimeError,match='FLEET_NOT_STARTED'):
            f.maintain()
        f.start()
        with pytest.raises(TypeError,match='HOST_PRESSURE'):
            f.maintain(pressure='yes')
    finally:f.close()
    assert_clean()


def test_mixed_runtime_soak_authorized_hdc_ssm_calc_and_pressure():
    """A genuine mixed-operation pass, not just global-budget counter tests."""
    import base64
    import json
    from concurrent.futures import ThreadPoolExecutor
    from cognitum.contracts import HostContext, Request
    from cognitum.proto import research_optional_pb2 as pb
    from cognitum.registry import Registry
    from cognitum.runtime import Runtime

    def runtime(factory, executor, warm):
        r=Registry()
        manifest=r.install(factory,enabled=True)
        for operation in manifest.operations:r.nominate(operation.slot,manifest.name)
        return Runtime(r,sandbox_executor=executor,warm_pool=warm)

    a,b=mk(Calculator),mk(Specialists)
    f=ContainedWarmFleet((a,b))
    try:
        f.start()
        assert a.wait_ready(10,minimum=1) and b.wait_ready(10,minimum=1)
        calc_rt=runtime(Calculator,a.executor,a)
        spec_rt=runtime(Specialists,b.executor,b)
        ctx=HostContext('local','local-user',allow_research=True)
        q=pb.HdcQuery(schema_version=1,source_snapshot_id='snap',index_snapshot_id='snap',
                      role='owns',entity='ship',top_k=1)
        record=q.records.add();record.candidate_id='a';record.role='owns';record.entity='ship'
        hdc={'frame_b64':base64.b64encode(q.SerializeToString(deterministic=True)).decode()}
        ssm={'request_json':json.dumps({'parameters':{'a':[.5],'b':[[1]],'c':[[1]],'d':[[0]]},
                                        'inputs':[[2],[2]],'initial_state':None})}
        tasks=[]
        for j in range(12):
            tasks.append((calc_rt,Request(f'calc-{j}','same','calc.rational',
                                          {'expression':f'{j}+11'},timeout_ms=7000),'calc',j))
            tasks.append((spec_rt,Request(f'ssm-{j}','same','specialist.ssm',ssm,
                                          timeout_ms=7000),'ssm',j))
            tasks.append((spec_rt,Request(f'hdc-{j}','same','specialist.hdc',hdc,
                                          timeout_ms=7000),'hdc',j))
        with ThreadPoolExecutor(max_workers=4) as executor:
            for offset in range(0,len(tasks),6):
                pending=tasks[offset:offset+6]
                futures=[executor.submit(rt.call,req,ctx) for rt,req,_,_ in pending]
                for (_,_,kind,j),future in zip(pending,futures):
                    reply=future.result(timeout=12)
                    assert reply.execution_status=='completed',(kind,j,reply.error)
                    if kind=='calc': assert reply.result=={'value':str(j+11)}
                    if kind=='ssm':
                        assert json.loads(reply.result['result_json'])['outputs']==[[2.0],[3.0]]
                    if kind=='hdc':assert reply.result['status']=='candidates_only'
                f.maintain(pressure=offset in (12,24))
                assert f.snapshot()['warm_budget']['reserved']<=4
        assert f.snapshot()['warm_budget']['reserved']<=4
        assert a.snapshot()['hits']+b.snapshot()['hits']>0
    finally:f.close()
    assert_clean()
