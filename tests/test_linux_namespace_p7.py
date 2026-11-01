"""P7 OS containment gates executed with REAL Linux kernel namespaces.

These tests require a developer host that permits unprivileged user namespaces.
They must not be counted as PASSED if the launcher is unavailable.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time

import pytest

from cognitum.contracts import HostContext, Request
from cognitum.plugins.calculator import Calculator
from cognitum.plugins.specialists import Specialists
from cognitum.proto import research_optional_pb2 as pb
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.sandbox_linux import LinuxNamespaceExecutor, ContainmentUnavailable
from cognitum import worker_budget


@pytest.fixture(scope='module')
def sandbox():
    if sys.platform != 'linux':
        pytest.skip('Linux-only OS test, not a Windows pass')
    value = LinuxNamespaceExecutor()
    status, report = value.test_probe('probe.isolation',timeout_ms=8000)
    # A failed namespace launch is a GATE FAILURE, not an automatic skip.
    assert status == 'ok', f'namespace containment unavailable: {status}'
    assert report['isolation_preflight'] is True
    return value


def make_runtime(factory=Calculator, *, executor=None):
    registry = Registry()
    manifest = registry.install(factory, enabled=True)
    registry.nominate(manifest.operations[0].slot, manifest.name)
    return Runtime(registry, sandbox_executor=executor)


def test_kernel_namespace_and_read_only_roots(sandbox):
    status, result = sandbox.test_probe('probe.isolation',timeout_ms=5000)
    assert status == 'ok'
    assert result == {
        'isolation_preflight': True,
        'host_etc_visible': False,
        'code_writable': False,
        'network_reachable': False,
        'inside_pid': 1,
        'host_mnt_visible': False,
        'no_capabilities': True,
        'no_new_privileges': True,
        'code_read_only': True,
        'stdlib_read_only': True,
        'aws_key_visible': False,
    }


def test_host_environment_scrubbed(sandbox, monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'fake-test-secret-never-inherit')
    status, result = sandbox.test_probe('probe.isolation',timeout_ms=5000)
    assert status == 'ok' and result['aws_key_visible'] is False


def test_real_sandbox_calc(sandbox):
    runtime = make_runtime(executor=sandbox)
    r = runtime.call(Request('p7calc','c1','calc.rational',{'expression':'1/2+1/4'},timeout_ms=5000),HostContext('local','local-user'))
    assert r.execution_status == 'completed'
    assert r.result == {'value':'3/4'}
    assert r.assurance == 'exact_arithmetic'


@pytest.mark.parametrize('expression', ['0.1+0.2','2**10','14/7+3/5','0/1','(3+5)*2'])
def test_real_sandbox_calc_matches_pure_reference(sandbox,expression):
    from cognitum.plugins.calculator import calculate
    status,out=sandbox.execute(Calculator,'calc.rational',{'expression':expression},timeout_ms=5000)
    assert status=='ok' and out=={'value':calculate(expression)}


def test_invalid_operation_returns_no_computed_answer(sandbox):
    status,out=sandbox.execute(Calculator,'calc.rational',{'expression':'1/0'},timeout_ms=5000)
    assert status=='invalid_input' and out is None


def test_host_authorization_before_worker_launch(sandbox,monkeypatch):
    runtime=make_runtime(executor=sandbox)
    touched=[]
    def should_not_spawn(*args,**kwargs):
        touched.append(True)
        raise AssertionError('denied request launched sandbox')
    monkeypatch.setattr(sandbox,'execute',should_not_spawn)
    r=runtime.call(Request('p7denied','c1','calc.rational',{'expression':'2+2'},timeout_ms=5000),HostContext('bad','bad'))
    assert r.execution_status=='denied' and r.result is None and not touched


def test_research_optin_and_ssm_in_sandbox(sandbox):
    runtime=make_runtime(Specialists,executor=sandbox)
    payload={'request_json':json.dumps({'parameters':{'a':[0.5],'b':[[1]],'c':[[1]],'d':[[0]]},
                                       'inputs':[[2],[2]],'initial_state':None})}
    r=Request('p7ssm','ctx','specialist.ssm',payload,timeout_ms=8000)
    # Specialist registry is research only; test must explicitly authorize research.
    from dataclasses import replace
    context=HostContext('local','local-user',allow_research=True)
    no_optin=runtime.call(r,HostContext('local','local-user'))
    assert no_optin.execution_status=='unavailable'
    status=runtime.call(r,context)
    assert status.execution_status=='unavailable'  # Not selected until nominated.
    runtime.registry.nominate('ssm','cognitum_specialists')
    yes=runtime.call(r,context)
    assert yes.execution_status=='completed'
    actual=json.loads(yes.result['result_json'])
    assert actual['outputs']==[[2.0],[3.0]]
    assert 'NOT_TRAINED' in yes.result['limitations']


def test_hdc_proto_roundtrip_sandbox(sandbox):
    q=pb.HdcQuery(schema_version=1,source_snapshot_id='snap1',index_snapshot_id='snap1',role='owns',entity='ship',top_k=1)
    e=q.records.add();e.candidate_id='c1';e.role='owns';e.entity='ship'
    raw=q.SerializeToString(deterministic=True)
    status,out=sandbox.execute(Specialists,'specialist.hdc',{'frame_b64':base64.b64encode(raw).decode()},timeout_ms=8000)
    assert status=='ok'
    proto=pb.HdcCandidates.FromString(base64.b64decode(json.loads(out['result_json'])['protobuf_b64']))
    assert list(proto.candidate_ids)==['c1']
    assert out['status']=='candidates_only'


def test_kan_fails_closed_without_trusted_checkpoint(sandbox):
    status,out=sandbox.execute(Specialists,'specialist.kan',{'frame_b64':'YQ==','checkpoint_b64':'YQ=='},timeout_ms=5000)
    assert status=='unavailable' and out is None


def test_fake_factory_never_admitted(sandbox):
    Fake=type('Calculator',(),{'__module__':'cognitum.plugins.calculator'})
    status,out=sandbox.execute(Fake,'calc.rational',{'expression':'2+2'},timeout_ms=5000)
    assert status=='unavailable' and out is None


def test_unsupported_operation_and_batch_cannot_bypass(sandbox):
    r=make_runtime(executor=sandbox)
    status,out=sandbox.execute(Calculator,'forged.operation',{'expression':'2+2'},timeout_ms=5000)
    assert status=='unavailable' and out is None
    with pytest.raises(PermissionError,match='SANDBOX_BATCH_NOT_IMPLEMENTED'):
        r.call_batch([],HostContext('local','local-user'),trusted_batch_opt_in=True)


def test_sandbox_runtime_cannot_reuse_unsandboxed_warm_pool(sandbox):
    with pytest.raises(ValueError,match='WARM_POOL_NOT_CONTAINED'):
        Runtime(Registry(),warm_pool=object(),sandbox_executor=sandbox)


def test_namespace_launch_failure_does_not_use_unsandboxed_worker(sandbox,monkeypatch):
    executor=LinuxNamespaceExecutor()
    executor._entry=executor.source_dir/'no-such-launch-file.sh'
    runtime=make_runtime(executor=executor)
    result=runtime.call(Request('p7missing','ctx','calc.rational',{'expression':'2+2'},timeout_ms=5000),HostContext('local','local-user'))
    assert result.execution_status=='unavailable'
    assert result.result is None


def test_budget_exhaustion_cannot_start_any_sandbox(sandbox, monkeypatch):
    monkeypatch.setattr(worker_budget,'reserve_cold',lambda:False)
    status,result=sandbox.execute(Calculator,'calc.rational',{'expression':'1+1'},timeout_ms=5000)
    assert status=='overloaded' and result is None


def test_timeout_forcibly_terminates_running_sandbox(sandbox):
    before=time.monotonic()
    status,result=sandbox.test_probe('probe.stall',timeout_ms=500)
    elapsed=time.monotonic()-before
    assert status=='timed_out' and result is None
    assert elapsed<2.0


def test_bounded_output_kills_flooding_sandbox(sandbox):
    status,result=sandbox.test_probe('probe.flood',timeout_ms=3000)
    assert status=='error' and result is None


def _grandchildren():
    output=subprocess.run(['ps','-eww','-o','pid,ppid,args'],capture_output=True,text=True,timeout=5,check=True).stdout
    return [line for line in output.splitlines() if '--cognitum-p7-grandchild-containment-probe' in line
            and '/runtime/bin/python3' in line]


def test_namespace_pid1_exit_kills_escaped_process_group_descendant(sandbox):
    # Child is started in a separate session to test the PID-namespace cleanup,
    # not just killpg; no persistent child is allowed after the deadline.
    assert not _grandchildren(), 'orphan inherited from an earlier test'
    status,result=sandbox.test_probe('probe.child',timeout_ms=1000)
    assert status=='timed_out' and result is None
    for i in range(30):
        if not _grandchildren():
            break
        time.sleep(.05)
    assert not _grandchildren(), 'namespace cleanup left a grandchild alive'


def test_descendant_actually_launches_before_timeout_then_is_reaped(sandbox):
    # Stronger witness than a post-timeout orphan check: observe the spawned
    # descendant while the sandbox is alive, then prove it disappears.
    import threading
    output=[]
    assert not _grandchildren()
    thread=threading.Thread(target=lambda:output.append(sandbox.test_probe('probe.child',timeout_ms=2400)))
    thread.start()
    witnessed=False
    deadline=time.monotonic()+1.9
    while time.monotonic()<deadline:
        if _grandchildren():
            witnessed=True
            break
        time.sleep(.025)
    thread.join(4)
    assert not thread.is_alive()
    assert witnessed, 'descendant was never observed; cleanup claim unverified'
    assert output==[('timed_out',None)]
    for _ in range(25):
        if not _grandchildren():break
        time.sleep(.04)
    assert not _grandchildren()


def test_invalid_and_oversize_frames_fail_before_launch(sandbox):
    status,result=sandbox.execute(Calculator,'calc.rational',{'expression':'A'*(300000)},timeout_ms=5000)
    assert status=='invalid_input' and result is None
    status,result=sandbox.execute(Calculator,'calc.rational',{'expression':float('nan')},timeout_ms=5000)
    assert status=='invalid_input' and result is None


def test_existing_default_path_still_available_when_no_sandbox_selected():
    runtime=make_runtime()
    assert runtime.sandbox_executor is None


def test_linux_typed_executor_does_not_expose_arbitrary_module_import(sandbox):
    class Bad:
        __module__='os'
    status,result=sandbox.execute(Bad,'calc.rational',{'expression':'2+2'},timeout_ms=5000)
    assert status=='unavailable' and result is None
