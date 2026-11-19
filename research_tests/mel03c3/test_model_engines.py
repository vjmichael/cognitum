from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace, FrozenInstanceError
import hashlib
import json
from threading import Event
import pytest
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, engines as e, engines_pb2 as pb, model_engines as m
from cognitum.mel.engine_limits import HdcLimits, KanLimits

S=a.Scope('session','workspace','subject','turn')
B='hdc.bind';Q='hdc.query';K='kan.evaluate'

def route(op):return next(r for r in a.routes(include_engines=True) if r.operation==op)
def setup(**kw):
    r=Registry();r.install(e.EnginePlugin,enabled=True)
    for op in e.OPERATIONS:r.nominate(op,e.NAME)
    return r,a.Admission(Runtime(r),S.session,enable_engines=True,**kw)
@pytest.fixture
def host():return setup(enable_model_codecs=True)[1]
def layer(weight=2.):return pb.KanLayer(inputs=1,outputs=1,knots=3,basis=pb.RBF,grid=[-1.,0.,1.],coefficients=[0.,weight,0.],mask=[1.])
def checkpoint(weight=2.):return m.checkpoint_wire([layer(weight)])
def approve(h,wire=None,scope=S):
    wire=checkpoint() if wire is None else wire
    return h.approve_checkpoint(scope,wire,expected_sha256=hashlib.sha256(wire).hexdigest(),review_id='review-1')
def grant(h,op,*,scope=S,pin=None,limits=None):
    if op==K and pin is None:pin=approve(h,scope=scope)
    return h.issue(scope,route(op),limits or (KanLimits if op==K else HdcLimits)(timeout_ms=8000),ttl_ms=20000,model_codec=True,checkpoint_sha256=pin)
def args(op):return {B:dict(left='101',right='110'),Q:dict(probe='101',candidates=['101','101','110']),K:dict(points=[[0.],[.5]])}[op]
def run(h,t,op,raw=None,*,scope=S,rid='call',codec=None,name=None,timeout=8000):
    return h.execute_model(scope,t,rid,name or m.public_name(op),codec or m.descriptor(op)[0],json.dumps(args(op)) if raw is None else raw,timeout_ms=timeout)

@pytest.mark.parametrize('op',[B,Q,K])
def test_real_model_boundary_worker(host,op):
    t=grant(host,op);offer=host.discover_model(S,t);out=run(host,t,op)
    assert out['ok'] and out['codec_sha256']==offer['codec_sha256'] and len(out['result_sha256'])==64
    assert offer['tool_schema']['function']['parameters']['additionalProperties'] is False
    assert not offer['execution_authorized'] and not offer['model_advertised'] and t.hex() not in json.dumps(offer)
    r=out['result'];assert r['kernel_git_blob']==e.kernel(op)
    if op==B:assert r['bits']=='011' and r['assurance']=='exact_arithmetic'
    elif op==Q:assert r['hamming_distance']==[0,0,2] and r['best_index']==[0,1]
    else:
        import math
        assert [row[0] for row in r['values']]==pytest.approx([2.,2*math.exp(-.25)],abs=3e-7)
        assert r['checkpoint_sha256']==offer['checkpoint_sha256'] and r['assurance']=='numerical'
    assert run(host,t,op)['error']['code']=='replay_denied'
    with pytest.raises(ValueError):host.discover_model(S,t)

def test_disabled_by_default():
    r,h=setup();t=h.issue(S,route(B),HdcLimits())
    with pytest.raises(ValueError):h.discover_model(S,t)
    with pytest.raises(ValueError):run(h,t,B)
    with pytest.raises(ValueError):grant(h,B)
    with pytest.raises(ValueError):approve(h)
    with pytest.raises(ValueError):a.Admission(Runtime(r),S.session,enable_model_codecs=True)

@pytest.mark.parametrize('op',[B,Q,K])
def test_explicit_grant_only(host,op):
    t=host.issue(S,route(op),(KanLimits if op==K else HdcLimits)())
    with pytest.raises(ValueError):host.discover_model(S,t)
    with pytest.raises(ValueError):run(host,t,op)

@pytest.mark.parametrize('field',['session','workspace','subject','turn'])
def test_owner_scope(host,field):
    t=grant(host,K);other=replace(S,**{field:'wrong'})
    with pytest.raises(ValueError):host.discover_model(other,t)
    with pytest.raises(ValueError):run(host,t,K,scope=other)

@pytest.mark.parametrize('raw',['{"left":"1","right":"1","grant":true}','{"left":"1","left":"0","right":"1"}', '{"left":true,"right":"1"}','{"left":"0b1","right":"1"}','{"left":"01","right":"1"}', '{"left":"","right":""}', json.dumps(dict(left='1'*1025,right='1'*1025)), '[]','{}',' '*65537],ids=['extra','duplicate','bool','bit-format','dimension','empty','large-vector','array','missing','byte-budget'])
def test_bind_bad_json(host,raw):
    t=grant(host,B)
    with pytest.raises(ValueError):run(host,t,B,raw)
    assert not host._seen

@pytest.mark.parametrize('raw',[json.dumps(dict(probe='1',candidates=['1']*9)), '{"probe":"1","candidates":[]}', '{"probe":"1","candidates":["00"]}', '{"probe":"1","candidates":[1]}'],ids=['candidate-limit','empty','dimension','type'])
def test_query_bad_json(host,raw):
    t=grant(host,Q)
    with pytest.raises(ValueError):run(host,t,Q,raw)
    assert not host._seen

@pytest.mark.parametrize('raw',['{"points":[[0]],"checkpoint":"fake"}','{"points":[[0]],"layers":[]}','{"points":[[0]],"path":"model.npz"}','{"points":[[0]],"approval":true}','{"points":[[true]]}','{"points":[[NaN]]}','{"points":[[2]]}','{"points":[[0,0]]}','{"points":[]}',json.dumps(dict(points=[[0]]*17))],ids=['checkpoint','weights','path','approval','bool','nan','domain','dimension','empty','rows'])
def test_kan_bad_json(host,raw):
    t=grant(host,K)
    with pytest.raises(ValueError):run(host,t,K,raw)
    assert not host._seen

def test_checkpoint_exact_pin_and_snapshot(host):
    l=layer();wire=m.checkpoint_wire([l]);digest=approve(host,wire);l.coefficients[1]=99
    cp=m.Checkpoint(wire);copy=cp.message();copy.layers[0].coefficients[1]=99
    assert cp.identity==digest and cp.message().layers[0].coefficients[1]==2
    with pytest.raises(FrozenInstanceError):cp.wire=b'other'
    with pytest.raises(ValueError):host.approve_checkpoint(S,wire,expected_sha256='0'*64,review_id='review')
    with pytest.raises(ValueError):approve(host,wire)
    assert run(host,grant(host,K,pin=digest),K)['result']['values'][0]==[2.]

@pytest.mark.parametrize('case',['unknown','coordinates','rows','empty','bad-grid','nan','bad-mask','oversized','bad-review'])
def test_checkpoint_bad_profile(host,case):
    b=pb.KanInput(layers=[layer()]);review='review'
    if case=='coordinates':b.coordinates.append(0)
    elif case=='rows':b.rows=1
    elif case=='empty':b.ClearField('layers')
    elif case=='bad-grid':b.layers[0].grid[1]=-1
    elif case=='nan':b.layers[0].coefficients[0]=float('nan')
    elif case=='bad-mask':b.layers[0].mask[0]=.5
    elif case=='bad-review':review=''
    wire=m.serialize(b)
    if case=='unknown':wire+=b'\x98\x06\x01'
    if case=='oversized':wire=b'x'*(m.MAX_CHECKPOINT_BYTES+1)
    with pytest.raises(ValueError):host.approve_checkpoint(S,wire,expected_sha256=hashlib.sha256(wire).hexdigest(),review_id=review)
    assert not host._checkpoints

def test_unapproved_or_other_scope_checkpoint(host):
    p=approve(host)
    for scope,pin in [(S,'0'*64),(replace(S,turn='other'),p)]:
        with pytest.raises(ValueError):grant(host,K,pin=pin,scope=scope)
    with pytest.raises(ValueError):host.issue(S,route(K),KanLimits(),model_codec=True)
    with pytest.raises(ValueError):host.issue(S,route(B),HdcLimits(),model_codec=True,checkpoint_sha256=p)

def test_raw_frame_substitution_denied(host):
    t=grant(host,K);c=e.make_call(K,pb.KanInput(layers=[layer(99)],rows=1,coordinates=[0]),'call',S.turn)
    assert host.execute(S,t,'call',c.wire,timeout_ms=8000).status=='invalid_input'
    assert run(host,t,K)['result']['values'][0]==[2.]

def test_raw_model_subset_enforced(host):
    t=grant(host,B);v=pb.BinaryVector(dimension=1025,bits=bytes(129));c=e.make_call(B,pb.BindInput(left=v,right=v),'call',S.turn)
    assert host.execute(S,t,'call',c.wire,timeout_ms=8000).status=='invalid_input'

def test_revocation_all_pinned_grants(host):
    p=approve(host);t=grant(host,K,pin=p);u=grant(host,K,pin=p)
    assert not host.revoke_checkpoint(replace(S,turn='other'),p)
    assert host.revoke_checkpoint(S,p) and not host.revoke_checkpoint(S,p)
    for x in (t,u):
        with pytest.raises(ValueError):run(host,x,K)
    with pytest.raises(ValueError):grant(host,K,pin=p)
    with pytest.raises(ValueError):approve(host)

def test_checkpoint_capacity(host,monkeypatch):
    monkeypatch.setattr(m,'MAX_CHECKPOINTS',1);p=approve(host);host.revoke_checkpoint(S,p)
    with pytest.raises(ValueError):approve(host,checkpoint(3))

def test_model_descriptor_stale_and_wrong_route(host):
    t=grant(host,B)
    for kw in (dict(codec='0'*64),dict(name=m.public_name(Q))):
        with pytest.raises(ValueError):run(host,t,B,**kw)
    assert not host._seen
    assert run(host,t,B)['ok']

def test_resource_limit_and_cross_route_replay(host):
    t=grant(host,B,limits=HdcLimits(dimensions=2,timeout_ms=8000));assert run(host,t,B)['error']['code']=='resource_denied'
    t=grant(host,B);u=grant(host,Q);assert run(host,t,B)['ok']
    assert run(host,u,Q)['error']['code']=='replay_denied'

def test_checkpoint_revocation_inflight(monkeypatch):
    _,h=setup(enable_model_codecs=True);p=approve(h);t=grant(h,K,pin=p);orig=Runtime.call;ready=Event();release=Event()
    def delayed(*x,**kw):
        r=orig(*x,**kw);assert r.execution_status=='completed';ready.set();assert release.wait(5);return r
    monkeypatch.setattr(Runtime,'call',delayed)
    with ThreadPoolExecutor(1) as pool:
        f=pool.submit(run,h,t,K)
        try:assert ready.wait(8);assert h.revoke_checkpoint(S,p)
        finally:release.set()
        result=f.result(timeout=8)
    assert result['error']['code']=='revoked' and 'result' not in result and 'result_sha256' not in result

def test_corrupt_worker_result_denied(host,monkeypatch):
    t=grant(host,Q);orig=Runtime.call
    def corrupt(*args,**kw):
        r=orig(*args,**kw);assert r.execution_status=='completed'
        return replace(r,result={'frame':e.encode_carrier(b'\x98\x06\x01',e.MAX_RESULT)})
    monkeypatch.setattr(Runtime,'call',corrupt);assert run(host,t,Q)['error']['code']=='error'

def test_close_blocks_approval(host):
    host.close()
    with pytest.raises(ValueError):approve(host)

def test_registry_replacement_invalidates_model_schema():
    r,h=setup(enable_model_codecs=True);t=grant(h,B);r.enable(e.NAME,False);r.enable(e.NAME,True)
    with pytest.raises(ValueError):h.discover_model(S,t)
    assert run(h,t,B)['error']['code']=='unavailable'


def test_kan_domain_before_float32_rounding(host):
    t=grant(host,K)
    with pytest.raises(ValueError):run(host,t,K,'{"points":[[1.000000001]]}')
    assert run(host,t,K,'{"points":[[1.0]]}')['ok']


def test_approved_spline_checkpoint(host):
    l=pb.KanLayer(inputs=1,outputs=1,knots=4,basis=pb.BSPLINE,degree=1,grid=[-1.,0.,1.,2.],coefficients=[2.,0.],mask=[1.])
    p=approve(host,m.checkpoint_wire([l]));t=grant(host,K,pin=p)
    out=run(host,t,K,'{"points":[[-0.5],[0],[0.5]]}')
    assert out['ok'] and out['result']['values']==[[1.],[2.],[1.]]


def test_checkpoint_pin_separates_same_shape(host):
    p=approve(host);q=approve(host,checkpoint(3));t=grant(host,K,pin=p);u=grant(host,K,pin=q)
    assert p!=q and host.discover_model(S,t)['checkpoint_sha256']==p
    assert run(host,t,K)['result']['values'][0]==[2.]
    assert run(host,u,K,rid='other')['result']['values'][0]==[3.]


def test_model_codec_projection_and_binding_are_inert(host,monkeypatch):
    t=grant(host,K)
    def no_dispatch(*a,**kw):raise AssertionError('dispatch at discovery or bind')
    monkeypatch.setattr(Runtime,'call',no_dispatch)
    offer=host.discover_model(S,t);offer['tool_schema']['function']['parameters']['properties'].clear()
    assert host.discover_model(S,t)['tool_schema']['function']['parameters']['properties']
    c=m.bind(K,host._grants[t].checkpoint,'{"points":[[0]]}','call',S.turn)
    assert c.message.kan.layers[0].coefficients[1]==2 and not host._seen
