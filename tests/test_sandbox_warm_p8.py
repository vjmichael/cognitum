"""P8 kernel-backed standby acceptance, not a production-untrusted-code claim."""
from __future__ import annotations
import base64
import json
import os
import subprocess
import threading
import time

import pytest

from cognitum.contracts import HostContext, Request
from cognitum.plugins.calculator import Calculator
from cognitum.plugins.specialists import Specialists
from cognitum.proto import research_optional_pb2 as pb
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.sandbox_linux import LinuxNamespaceExecutor
from cognitum.sandbox_warm_pool import LinuxSandboxWarmPool, _read_ready, _reap, _WarmSlot
from cognitum.warm_pool import WarmCappedPool, global_warm_budget_snapshot
from cognitum.warm_host import TrustedWarmMaintenance


def reg(factory=Calculator):
    registry=Registry()
    manifest=registry.install(factory,enabled=True)
    for operation in manifest.operations:
        registry.nominate(operation.slot,manifest.name)
    return registry


def calc(expr='4*8', num='p8',timeout=5000):
    return Request(num,'same','calc.rational',{'expression':expr},timeout_ms=timeout)


def pool(factory=Calculator, **kw):
    executor=LinuxNamespaceExecutor()
    return LinuxSandboxWarmPool(executor,factory,**kw)


def checked_no_warm_leak():
    assert global_warm_budget_snapshot()['reserved'] == 0


def test_readiness_requires_kernel_isolation_proof():
    exe=LinuxNamespaceExecutor()
    p,tmp=exe._launch_contained(warm_provider='calculator')
    slot=_WarmSlot(p,tmp,time.monotonic())
    try:
        assert _read_ready(p,10)
        raw=b'{"kind":"test_probe","operation":"probe.isolation","payload":{}}\n'
        status,proof=exe._exchange(p,raw,5)
        assert status=='ok'
        assert proof['isolation_preflight'] is True
        assert proof['code_writable'] is False
        assert proof['host_mnt_visible'] is False
        assert proof['host_etc_visible'] is False
        assert proof['network_reachable'] is False
        assert proof['no_capabilities'] is True
        assert proof['no_new_privileges'] is True
        assert proof['aws_key_visible'] is False
        assert proof['inside_pid']==1
    finally:_reap(slot)


def test_default_two_in_real_namespaces_and_exact_response():
    p=pool()
    try:
        p.start();assert p.wait_ready(10)
        assert p.snapshot()['idle']==2
        r=Runtime(reg(),sandbox_executor=p.executor,warm_pool=p).call(calc(),HostContext('local','local-user'))
        assert r.execution_status=='completed' and r.result=={'value':'32'}
        assert p.snapshot()['hits']==1
        assert p.wait_ready(10,minimum=2)
    finally:p.close()
    checked_no_warm_leak()


def test_pool_uses_p7_only_on_readiness_miss(monkeypatch):
    p=pool()
    try:
        r=Runtime(reg(),sandbox_executor=p.executor,warm_pool=p).call(calc('3+4'),HostContext('local','local-user'))
        assert r.execution_status=='completed' and r.result=={'value':'7'}
        assert p.snapshot()['misses']==1
        assert p.wait_ready(10,minimum=2)
        # Every miss uses P7 namespace cold executor, not multiprocessing.
        assert p.executor.test_probe('probe.isolation')[0]=='ok'
    finally:p.close()
    checked_no_warm_leak()


def test_old_unsandboxed_pool_cannot_enter_sandbox_runtime():
    with pytest.raises(ValueError,match='WARM_POOL_NOT_CONTAINED'):
        Runtime(reg(),sandbox_executor=LinuxNamespaceExecutor(),warm_pool=object())
    p=pool()
    try:
        with pytest.raises(ValueError,match='WARM_POOL_NOT_CONTAINED'):
            Runtime(reg(),sandbox_executor=LinuxNamespaceExecutor(),warm_pool=p)
    finally:p.close()


def test_auth_denial_does_not_consume_worker():
    p=pool()
    try:
        p.start();assert p.wait_ready(10)
        rt=Runtime(reg(),sandbox_executor=p.executor,warm_pool=p)
        denied=rt.call(calc(),HostContext('wrong','user'))
        assert denied.execution_status=='denied' and p.snapshot()['hits']==0
        accepted=rt.call(calc(),HostContext('local','local-user'))
        assert accepted.result=={'value':'32'} and p.snapshot()['hits']==1
    finally:p.close()


def test_no_effectful_or_forged_factory():
    p=pool()
    try:
        fake=type('Calculator',(),{'__module__':'cognitum.plugins.calculator'})
        assert p.execute(fake,'calc.rational',{'expression':'2'},5000)==('unavailable',None)
        assert p.execute(Calculator,'other',{},5000)==('unavailable',None)
        with pytest.raises(PermissionError,match='UNREVIEWED_WARM_FACTORY'):
            LinuxSandboxWarmPool(LinuxNamespaceExecutor(),fake)
    finally:p.close()


def test_specialists_hdc_and_ssm_in_same_bundled_package():
    p=pool(Specialists)
    try:
        p.start();assert p.wait_ready(12)
        rt=Runtime(reg(Specialists),sandbox_executor=p.executor,warm_pool=p)
        state={'parameters':{'a':[0.5],'b':[[1]],'c':[[1]],'d':[[0]]},
               'inputs':[[2],[2]],'initial_state':None}
        req=Request('ssm','same','specialist.ssm',{'request_json':json.dumps(state)},timeout_ms=7000)
        out=rt.call(req,HostContext('local','local-user',allow_research=True))
        assert out.execution_status=='completed'
        assert json.loads(out.result['result_json'])['outputs']==[[2.0],[3.0]]
        q=pb.HdcQuery(schema_version=1,source_snapshot_id='snap',index_snapshot_id='snap',role='owns',entity='ship',top_k=1)
        e=q.records.add();e.candidate_id='a';e.role='owns';e.entity='ship'
        req=Request('hdc','same','specialist.hdc',{'frame_b64':base64.b64encode(q.SerializeToString(deterministic=True)).decode()},timeout_ms=7000)
        out=rt.call(req,HostContext('local','local-user',allow_research=True))
        assert out.execution_status=='completed'
        assert out.result['status']=='candidates_only'
        assert p.hits>=2
    finally:p.close()
    checked_no_warm_leak()


def test_unapproved_kan_never_runs_warm_or_cold():
    p=pool(Specialists)
    try:
        p.start();assert p.wait_ready(12)
        assert p.execute(Specialists,'specialist.kan',{'frame_b64':'YQ==','checkpoint_b64':'YQ=='},5000)==('unavailable',None)
        assert p.hits==0
    finally:p.close()


def test_strict_four_limit_across_two_provider_pools():
    a=pool(Calculator,target_ready=2)
    b=pool(Specialists,target_ready=2)
    try:
        a.start();b.start()
        assert a.wait_ready(15) and b.wait_ready(15)
        assert global_warm_budget_snapshot()['reserved']==4
        assert a.snapshot()['global_warm_budget']['reserved']==4
        assert b.snapshot()['global_warm_budget']['reserved']==4
    finally:a.close();b.close()
    checked_no_warm_leak()


def test_fifth_concurrent_request_executes_in_cold_sandbox(monkeypatch):
    p=pool(target_ready=4)
    try:
        p.start();assert p.wait_ready(15,minimum=4)
        original=p.executor._exchange
        def slow_first(proc,raw,timeout):
            time.sleep(.25)
            return original(proc,raw,timeout)
        monkeypatch.setattr(p.executor,'_exchange',slow_first)
        barrier=threading.Barrier(6)
        results=[]
        def run(i):
            barrier.wait()
            results.append(p.execute(Calculator,'calc.rational',{'expression':f'{i}+10'},7000))
        threads=[threading.Thread(target=run,args=(i,)) for i in range(5)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join(12)
        assert all(not t.is_alive() for t in threads)
        assert sorted(v['value'] for status,v in results if status=='ok')==['10','11','12','13','14']
        assert p.snapshot()['hits']==4
        assert p.snapshot()['misses']==1
        assert p.snapshot()['peak_warm']<=4
    finally:p.close()
    checked_no_warm_leak()


def test_kernel_timeout_reaps_preloaded_worker():
    exe=LinuxNamespaceExecutor()
    proc,root=exe._launch_contained(warm_provider='calculator')
    slot=_WarmSlot(proc,root,time.monotonic())
    try:
        assert _read_ready(proc,10)
        result=exe._exchange(proc,b'{"kind":"test_probe","operation":"probe.stall","payload":{}}\n',.5)
        assert result==('timed_out',None)
    finally:_reap(slot)
    assert proc.poll() is not None


def _children():
    listing=subprocess.run(['ps','-eww','-o','args'],capture_output=True,text=True,timeout=4).stdout
    return [x for x in listing.splitlines() if '/runtime/bin/python3' in x and
            '--cognitum-p7-grandchild-containment-probe' in x]


def test_warm_kernel_pid_namespace_reaps_escaped_session_descendant():
    exe=LinuxNamespaceExecutor()
    proc,root=exe._launch_contained(warm_provider='calculator')
    slot=_WarmSlot(proc,root,time.monotonic())
    assert not _children()
    try:
        assert _read_ready(proc,10)
        results=[]
        thread=threading.Thread(target=lambda:results.append(exe._exchange(proc,
            b'{"kind":"test_probe","operation":"probe.child","payload":{}}\n',1.6)))
        thread.start()
        witnessed=False
        end=time.monotonic()+1.25
        while time.monotonic()<end:
            if _children():
                witnessed=True;break
            time.sleep(.025)
        thread.join(4)
        assert not thread.is_alive()
        assert witnessed, 'descendant not observed; no cleanup proof'
        assert results==[('timed_out',None)]
    finally:_reap(slot)
    for i in range(30):
        if not _children():break
        time.sleep(.04)
    assert not _children()


def test_maintenance_downshift_and_restore():
    p=pool(idle_downshift_s=1)
    try:
        with TrustedWarmMaintenance([p],interval_s=.1) as host:
            assert p.wait_ready(12)
            end=time.monotonic()+7
            while time.monotonic()<end and p.snapshot()['target_ready']!=1:time.sleep(.1)
            assert p.snapshot()['target_ready']==1
            out=p.execute(Calculator,'calc.rational',{'expression':'4*4'},5000)
            assert out==('ok',{'value':'16'})
            assert p.snapshot()['target_ready']==2
            assert p.wait_ready(10,minimum=2)
            assert host.snapshot()['ticks']>0
    finally:p.close()
    checked_no_warm_leak()


def test_close_during_inflight_prevents_result_publication(monkeypatch):
    p=pool(target_ready=1)
    try:
        p.start();assert p.wait_ready(10)
        original=p.executor._exchange
        entered=threading.Event()
        def slow(proc,raw,timeout):
            entered.set()
            time.sleep(.4)
            return original(proc,raw,timeout)
        monkeypatch.setattr(p.executor,'_exchange',slow)
        answer=[]
        t=threading.Thread(target=lambda:answer.append(p.execute(Calculator,'calc.rational',{'expression':'2+3'},4000)))
        t.start();assert entered.wait(2)
        p.close();t.join(5)
        assert not t.is_alive()
        assert answer[0][0]!='ok' and answer[0][1] is None
    finally:p.close()
    checked_no_warm_leak()


def test_fail_closed_no_p7_namespace_launch_not_unsandboxed():
    p=pool(target_ready=1)
    p.executor._entry=p.executor.source_dir/'nonexistent-script'
    try:
        p.start()
        assert not p.wait_ready(1,minimum=1)
        status,result=p.execute(Calculator,'calc.rational',{'expression':'2+3'},600)
        assert status=='unavailable' and result is None
        assert p.snapshot()['hits']==0
    finally:p.close()
    checked_no_warm_leak()


def test_expired_idle_worker_never_reused_but_cold_remains_contained():
    p=pool(target_ready=1,max_idle_s=1)
    try:
        p.start();assert p.wait_ready(10)
        time.sleep(1.05)
        result=p.execute(Calculator,'calc.rational',{'expression':'9*9'},5000)
        assert result==('ok',{'value':'81'})
        assert p.wait_ready(12)
    finally:p.close()
    checked_no_warm_leak()


def test_warm_frame_rejects_malformed_or_second_task():
    exe=LinuxNamespaceExecutor()
    proc,root=exe._launch_contained(warm_provider='calculator')
    slot=_WarmSlot(proc,root,time.monotonic())
    try:
        assert _read_ready(proc,10)
        result=exe._exchange(proc,b'{"kind":"cognitum","operation":"calc.rational","payload":{"expression":"2+2"},"operation":"calc.rational"}\n',5)
        assert result[0]=='invalid_input' and result[1] is None
        assert proc.poll() is not None  # single use, no leftover request loop
    finally:_reap(slot)


def test_missing_warm_child_fail_closed():
    p=pool(target_ready=1)
    p.executor.source_dir=p.executor.source_dir/'not-a-real-code-directory'
    try:
        p.start();assert not p.wait_ready(1,minimum=1)
        status,result=p.execute(Calculator,'calc.rational',{'expression':'2+2'},1000)
        assert status=='unavailable' and result is None
    finally:p.close()
    checked_no_warm_leak()


def test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold():
    from test_research_optional import kan_artifact
    import hashlib
    checkpoint=kan_artifact()
    digest=hashlib.sha256(checkpoint).hexdigest()
    frame=pb.KanRequest(schema_version=1,feature_values=['0'],checkpoint_sha256=digest).SerializeToString(deterministic=True)
    payload={'frame_b64':base64.b64encode(frame).decode(),
             'checkpoint_b64':base64.b64encode(checkpoint).decode()}
    exe=LinuxNamespaceExecutor(approved_kan_sha256=digest)
    p=LinuxSandboxWarmPool(exe,Specialists,target_ready=1)
    try:
        p.start();assert p.wait_ready(12)
        warm_status,warm_result=p.execute(Specialists,'specialist.kan',payload,7000)
        cold_status,cold_result=exe.execute(Specialists,'specialist.kan',payload,7000)
        assert warm_status==cold_status=='ok'
        assert warm_result==cold_result
        record=pb.KanPrediction.FromString(base64.b64decode(json.loads(warm_result['result_json'])['protobuf_b64']))
        assert record.checkpoint_sha256==digest
        assert not record.uncertainty_calibrated
    finally:p.close()
    checked_no_warm_leak()
