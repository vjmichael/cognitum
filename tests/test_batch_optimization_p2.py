"""P2 in-Cognitum generic *pure* batch worker admission and lifecycle tests."""
import pytest
from dataclasses import replace
from cognitum.contracts import HostContext, Request
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.plugins.calculator import Calculator


def setup():
    reg=Registry()
    reg.install(Calculator,enabled=True)
    reg.nominate('calc','reference_calc')
    return Runtime(reg)


def requests(n=4, *, expression='1/3*3', **kwargs):
    return [Request(f'B{i}','one-turn','calc.rational',{'expression':expression},
                    timeout_ms=5000,**kwargs) for i in range(n)]


def test_opt_in_required_and_existing_call_unaffected():
    rt=setup()
    with pytest.raises(PermissionError,match='BATCH_DEFAULT_DISABLED'):
        rt.call_batch(requests(),HostContext('local','local-user'))
    r=rt.call(requests(1)[0],HostContext('local','local-user'))
    assert r.execution_status=='completed' and r.result=={'value':'1'}


@pytest.mark.parametrize('n',[1,2,4,8,16])
def test_valid_batch_is_exactly_equal_to_reference_calculator(n):
    rt=setup()
    rs=rt.call_batch(requests(n),HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert len(rs)==n
    assert all(x.execution_status=='completed' and x.result=={'value':'1'} for x in rs)
    assert all(x.assurance=='exact_arithmetic' for x in rs)
    assert len(rt.trace.events)==n
    assert all(x.error is None for x in rs)


def test_invalid_input_in_second_slot_disposes_all_partial_results():
    rt=setup()
    reqs=requests(3)
    reqs[1].payload['expression']='1/0'
    res=rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert len(res)==3
    assert all(x.execution_status=='invalid_input' and x.result is None for x in res)


def test_preflight_refuses_inconsistent_context_without_any_invocation():
    rt=setup()
    reqs=requests(2)
    reqs[1]=replace(reqs[1],correlation_id='other-turn')
    with pytest.raises(ValueError,match='BATCH_CROSSES_CONTEXT_OR_OPERATION'):
        rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert len(rt.trace.events)==0


def test_preflight_forged_workspace_and_subject():
    rt=setup()
    reqs=requests(2)
    reqs[1]=replace(reqs[1],workspace_id='other')
    with pytest.raises(ValueError,match='BATCH_CROSSES_CONTEXT_OR_OPERATION'):
        rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    reqs=requests(2,subject_id='other-user')
    with pytest.raises(PermissionError,match='identity_scope_mismatch'):
        rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert len(rt.trace.events)==0


def test_same_request_id_rejected():
    rt=setup(); reqs=requests(2)
    reqs[1]=replace(reqs[1],request_id=reqs[0].request_id)
    with pytest.raises(ValueError,match='DUPLICATE_BATCH_REQUEST_ID'):
        rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert rt.trace.events==[]


@pytest.mark.parametrize('modifier',[
    lambda r: replace(r,dry_run=True),
    lambda r: replace(r,operation_schema_version='9.9.9'),
    lambda r: replace(r,payload={**r.payload,'irrelevant':'bad'}),
])
def test_bad_or_dry_run_never_spawns(modifier):
    rt=setup(); reqs=requests(2)
    reqs[1]=modifier(reqs[1])
    with pytest.raises((ValueError,PermissionError)):
        rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert rt.trace.events==[]


def test_timeout_fails_closed_without_partial_outputs():
    rt=setup()
    reqs=[Request('low','correlation','calc.rational',{'expression':'1+1'},timeout_ms=1),
          Request('high','correlation','calc.rational',{'expression':'2+2'},timeout_ms=1)]
    res=rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert len(res)==2
    assert all(x.result is None and x.execution_status=='timed_out' for x in res)
    assert len(rt.trace.events)==2


def test_effectful_plugin_not_allowed_even_if_installed():
    # This negative gate is about plugin metadata/effect, not worker OS isolation.
    from cognitum.contracts import Manifest,Operation,Shape,Effect
    class Dummy:
        def manifest(self):
            return Manifest('dummy','0.1.0',(Operation('write.dummy','write',
               Shape((('expression',50),)),Shape((('value',50),)),
               effects=(Effect('write_file','scope'),)),))
        def health(self):return True
        def self_test(self):return True
    rt=Runtime(Registry())
    rt.registry.install(Dummy,enabled=True)
    rt.registry.nominate('write','dummy')
    reqs=[Request('a','c','write.dummy',{'expression':'hi'}),
          Request('b','c','write.dummy',{'expression':'hi'})]
    with pytest.raises(PermissionError,match='BATCH_REQUIRES_PURE_DETERMINISTIC_PLUGIN'):
        rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)


def test_no_unbounded_batch():
    rt=setup()
    with pytest.raises(ValueError,match='INVALID_BATCH_SIZE'):
        rt.call_batch(requests(17),HostContext('local','local-user'),trusted_batch_opt_in=True)
    with pytest.raises(ValueError,match='INVALID_BATCH_SIZE'):
        rt.call_batch([],HostContext('local','local-user'),trusted_batch_opt_in=True)


def test_mutable_source_payload_is_snapshotted_before_worker(monkeypatch):
    from cognitum import runtime as runtime_mod
    rt=setup()
    reqs=requests(2)
    original=runtime_mod.execute_batch
    def altered_source_after_preflight(factory,pending,timeout):
        reqs[0].payload['expression']='3/0'
        # The child must receive only prevalidated copies, not live request dicts.
        return original(factory,pending,timeout)
    monkeypatch.setattr(runtime_mod,'execute_batch',altered_source_after_preflight)
    rs=rt.call_batch(reqs,HostContext('local','local-user'),trusted_batch_opt_in=True)
    assert all(x.execution_status=='completed' and x.result=={'value':'1'} for x in rs)
