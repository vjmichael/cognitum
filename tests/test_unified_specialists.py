"""Cognitum one-wheel specialist acceptance: real P1 C08/C09 and SSM scan."""
import base64, hashlib, json
from pathlib import Path
import pytest
from cognitum.specialists.ssm import DiagonalSSM,InvalidSSM,scan_request
from cognitum.plugins.specialists import Specialists
from cognitum.research.kan_optional import ResearchPolicy
from cognitum.proto import research_optional_pb2 as pb
from test_research_optional import kan_artifact
from cognitum.contracts import Request,HostContext
from cognitum.registry import Registry
from cognitum.runtime import Runtime


def params():
    return {'a':[.5,.25],'b':[[1.,0.],[0.,1.]],'c':[[1.,1.]],'d':[[0.,0.]]}


def request(inputs=None, initial_state=None):
    return {'parameters':params(),'inputs':inputs if inputs is not None else [[2.,4.],[2.,4.]],'initial_state':initial_state}


def b64(data):return base64.b64encode(data).decode('ascii')


def hdc_frame():
    req=pb.HdcQuery(schema_version=1,source_snapshot_id='v1',index_snapshot_id='v1',role='owns',entity='ship',top_k=2)
    req.records.add(candidate_id='r1',role='owns',entity='ship')
    req.records.add(candidate_id='r2',role='owns',entity='station')
    return req.SerializeToString(deterministic=True)


def kan_frame(checkpoint):
    return pb.KanRequest(schema_version=1,feature_values=['0'],checkpoint_sha256=hashlib.sha256(checkpoint).hexdigest()).SerializeToString(deterministic=True)


def test_ssm_reference_arithmetic():
    r=scan_request(request())
    assert r['outputs']==[[6.,],[8.,]] or r['outputs']==[[6.,],[8.5]]
    assert r['final_state']==[3.,5.]
    assert 'NOT_CAUSAL' in r['limitation']


def test_ssm_chunked_matches_whole():
    inp=[[0.1,0.2],[0.2,0.4],[0.3,0.1],[1.2,-.3]]
    full=scan_request(request(inp))
    first=scan_request(request(inp[:2]))
    last=scan_request(request(inp[2:],first['final_state']))
    assert full['outputs']==first['outputs']+last['outputs']
    assert full['final_state']==last['final_state']


def test_ssm_stable_zero_decay():
    q={'parameters':{'a':[0.],'b':[[1.]],'c':[[1.]],'d':[[0.]]},'inputs':[[1],[3]],'initial_state':[999.]}
    assert scan_request(q)['outputs']==[[1.],[3.]]


@pytest.mark.parametrize('mutant',[
    lambda q:q.update({'bad':'x'}),
    lambda q:q.update({'initial_state':[0]}),
    lambda q:q['parameters'].update({'a':[1.01,0.5]}),
    lambda q:q['parameters'].update({'a':[-0.01,0.5]}),
    lambda q:q['parameters'].update({'a':[float('nan'),0.5]}),
    lambda q:q['parameters'].update({'a':[True,False]}),
    lambda q:q['parameters'].update({'b':[[1,2],[1]]}),
    lambda q:q['parameters'].update({'c':[[1,1,1]]}),
    lambda q:q['parameters'].update({'d':[[0]]}),
    lambda q:q.update({'inputs':[]}),
    lambda q:q.update({'inputs':[[0,0]]*65}),
    lambda q:q.update({'inputs':[['X',2]]}),
    lambda q:q.update({'inputs':[[1001,0]]}),
    lambda q:q['parameters'].update({'x':[1]}),
])
def test_ssm_rejects_invalid(mutant):
    q=request()
    mutant(q)
    with pytest.raises(InvalidSSM):scan_request(q)


def test_ssm_overflow_fail_closed():
    q={'parameters':{'a':[1.], 'b':[[1000.]], 'c':[[1.]],'d':[[0.]]},'inputs':[[1000.],[1000.]],'initial_state':None}
    with pytest.raises(InvalidSSM,match='OVERFLOW'):scan_request(q)


def test_ssm_rejects_malformed_json():
    obj=Specialists()
    with pytest.raises(ValueError):obj.handle('specialist.ssm',{'request_json':'{"parameters": NaN}'})
    with pytest.raises(ValueError):obj.handle('specialist.ssm',{'request_json':'[1,2]'})


def test_manifest_one_package_three_specialists_and_default_denial():
    registry=Registry(); m=registry.install(Specialists)
    assert m.track=='research'; assert m.maturity=='prototype'
    assert {op.name for op in m.operations}=={'specialist.hdc','specialist.kan','specialist.ssm'}
    for slot in ['hdc','kan','ssm']:
        registry.nominate(slot,'cognitum_specialists')
    obj=json.dumps(request())
    rt=Runtime(registry)
    d=rt.call(Request('r1','corr','specialist.ssm',{'request_json':obj}),HostContext('local','local-user',allow_research=True)).to_dict()
    assert d['execution_status']=='unavailable'
    registry.enable('cognitum_specialists',True)
    d=rt.call(Request('r2','corr','specialist.ssm',{'request_json':obj}),HostContext('local','local-user')).to_dict()
    assert d['execution_status']=='unavailable'


def test_direct_hdc_protobuf_uses_original_candidate_kernel():
    result=Specialists().handle('specialist.hdc',{'frame_b64':b64(hdc_frame())})
    got=pb.HdcCandidates.FromString(base64.b64decode(json.loads(result['result_json'])['protobuf_b64']))
    assert got.candidate_ids[0]=='r1'
    assert got.hamming_distance[0]==0
    assert result['status']=='candidates_only'


def test_direct_hdc_rejects_stale_snapshot():
    r=pb.HdcQuery.FromString(hdc_frame());r.index_snapshot_id='old'
    with pytest.raises(ValueError,match='STALE_INDEX'):
        Specialists().handle('specialist.hdc',{'frame_b64':b64(r.SerializeToString(deterministic=True))})


def test_kan_cannot_approve_itself(monkeypatch):
    checkpoint=kan_artifact();frame=kan_frame(checkpoint)
    monkeypatch.delenv('COGNITUM_TRUSTED_KAN_SHA256',raising=False)
    with pytest.raises(PermissionError):
        Specialists().handle('specialist.kan',{'frame_b64':b64(frame),'checkpoint_b64':b64(checkpoint)})


def test_kan_with_explicit_host_pin_and_unchanged_cpu_kernel(monkeypatch):
    checkpoint=kan_artifact();digest=hashlib.sha256(checkpoint).hexdigest()
    monkeypatch.setenv('COGNITUM_TRUSTED_KAN_SHA256',digest)
    out=Specialists().handle('specialist.kan',{'frame_b64':b64(kan_frame(checkpoint)),'checkpoint_b64':b64(checkpoint)})
    got=pb.KanPrediction.FromString(base64.b64decode(json.loads(out['result_json'])['protobuf_b64']))
    assert got.checkpoint_sha256==digest
    assert out['status']=='approximate'
    assert not got.uncertainty_calibrated


def test_kan_wrong_host_pin_refuses(monkeypatch):
    checkpoint=kan_artifact();monkeypatch.setenv('COGNITUM_TRUSTED_KAN_SHA256','0'*64)
    with pytest.raises(PermissionError):
        Specialists().handle('specialist.kan',{'frame_b64':b64(kan_frame(checkpoint)),'checkpoint_b64':b64(checkpoint)})


def test_single_runtime_ssm_full_worker_round_trip():
    registry=Registry();registry.install(Specialists,enabled=True);registry.nominate('ssm','cognitum_specialists')
    response=Runtime(registry).call(Request('r100','corr','specialist.ssm',{'request_json':json.dumps(request())},timeout_ms=5000),HostContext('local','local-user',allow_research=True)).to_dict()
    assert response['execution_status']=='completed',response
    assert response['result']['status']=='state_sequence_only'
    assert json.loads(response['result']['result_json'])['final_state']==[3.,5.]


def test_runtime_scope_denial():
    registry=Registry();registry.install(Specialists,enabled=True);registry.nominate('ssm','cognitum_specialists')
    rt=Runtime(registry)
    result=rt.call(Request('r101','corr','specialist.ssm',{'request_json':json.dumps(request())},workspace_id='another'),HostContext('local','local-user',allow_research=True))
    assert result.execution_status=='denied';assert result.result is None


def test_noncanonical_base64_rejected():
    with pytest.raises(ValueError):Specialists().handle('specialist.hdc',{'frame_b64':b64(hdc_frame())+'!'})


def test_ssm_rejects_huge_integer_and_duplicate_json():
    q=request(); q['inputs']=[[10**400,0]]
    with pytest.raises(InvalidSSM):scan_request(q)
    with pytest.raises(ValueError):Specialists().handle('specialist.ssm',{'request_json':'{"parameters":{},"parameters":{},"inputs":[],"initial_state":null}'})
