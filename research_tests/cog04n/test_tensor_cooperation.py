from dataclasses import replace
from fractions import Fraction as Q
from threading import Thread, Event
from time import sleep
import pytest
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import tensor_cooperation as n,tensor_field as f,tensor_field_pb2 as pb
from research_tests.cog04m.test_tensor_field import examples
S=n.Scope('session','workspace','subject','turn');OTHER=replace(S,subject='other')
def setup(cp,*,limits=n.Limits(),coop=True):
    r=Registry()
    for op,name,plugin in [(n.TENSOR,n.TNAME,n.TensorPlugin),(n.SYMBOLIC,n.SNAME,n.SymbolicPlugin)]:
        r.install(plugin,enabled=True);r.nominate(op,name)
    rt=Runtime(r);a=n.Admission(rt,S.session,enabled=True,reviewed=n.selection());pin=a.approve(S,n.Approval(cp,'review'))
    return a,a.issue(S,pin,limits,cooperative=coop),rt

def request(cp,rank,*,id='request',turn='turn',operation=pb.POINT):
    return f.make_request(cp,operation,(.5,)*rank if operation==pb.POINT else (0,)*rank,derivative=(0,)*rank if operation==pb.POINT else (),upper=(1,)*rank if operation==pb.BOX_INTEGRAL else (),request_id=id,correlation_id=turn)
@pytest.fixture(params=examples(),ids=['xy','xt','xyt'])
def field(request):
    mod,p,m=request.param;return f.export(p,m,mod.assess(p,m)),3 if mod is f.l else 2
@pytest.fixture
def xy():
    mod,p,m=examples()[0];return f.export(p,m,mod.assess(p,m))

def test_actual_tensor_dispatch(field):
    cp,rank=field;a,t,rt=setup(cp);q=request(cp,rank);r=a.call(S,t,q)
    assert n.replay_receipt(cp,q,r,S) and len(rt.trace.events)==1 and rt.trace.events[0]['execution_status']=='completed'
    assert Q(pb.Result.FromString(r.result).exact_value)>0
    with pytest.raises(ValueError):a.call(S,t,q)

def test_actual_symbolic_cooperation(field):
    cp,rank=field;a,t,rt=setup(cp);r=a.residual(S,t,(.375,)*rank,request_id='plan')
    assert n.replay_residual(cp,r,S) and Q(r.exact_residual)==0
    assert len(rt.trace.events)==len(r.field_receipts)+1 and rt.trace.events[-1]['operation']==n.SYMBOLIC
    assert all(x['execution_status']=='completed' for x in rt.trace.events)

def test_integral_receipt(field):
    cp,rank=field;a,t,rt=setup(cp);q=request(cp,rank,operation=pb.BOX_INTEGRAL);r=a.call(S,t,q)
    assert n.replay_receipt(cp,q,r,S) and Q(pb.Result.FromString(r.result).exact_value)>0

def test_default_disabled(xy):
    a=n.Admission(Runtime(Registry()),S.session)
    with pytest.raises(ValueError):a.approve(S,n.Approval(xy,'review'))
    with pytest.raises(ValueError):n.Admission(Runtime(Registry()),S.session,enabled=True)

@pytest.mark.parametrize('case',['scope','turn','token','checkpoint','descriptor','unknown-wire','revoked','closed','disabled-route','replacement','expired','revoke-checkpoint','call-budget','work-budget','request-budget','result-budget','noncooperative','unapproved'],ids=str)
def test_refusals(xy,case):
    limits=n.Limits(calls=1) if case=='call-budget' else n.Limits(work=1) if case=='work-budget' else n.Limits(request_bytes=1) if case=='request-budget' else n.Limits(result_bytes=1) if case=='result-budget' else n.Limits()
    a,t,rt=setup(xy,limits=limits,coop=case!='noncooperative');s=S;q=request(xy,2)
    if case=='scope':s=OTHER
    if case=='turn':q=request(xy,2,turn='different')
    if case=='token':t=b'x'*32
    if case in ('checkpoint','descriptor','unknown-wire'):
        m=pb.Request.FromString(q)
        if case=='checkpoint':m.checkpoint_sha256=b'x'*32
        if case=='descriptor':m.descriptor_sha256=b'x'*32
        q=f.wire(m)+(b'\xf8\x07\x01' if case=='unknown-wire' else b'')
    if case=='revoked':a.revoke(S,t)
    if case=='closed':a.close()
    if case=='disabled-route':rt.registry.enable(n.TNAME,False)
    if case=='replacement':rt.registry.install(n.TensorPlugin,enabled=True)
    if case=='expired':t=a.issue(S,f.digest(xy).hex(),ttl_ms=1);sleep(.01)
    if case=='revoke-checkpoint':
        a.revoke_checkpoint(S,f.digest(xy).hex())
        with pytest.raises(ValueError):a.issue(S,f.digest(xy).hex())
        with pytest.raises(ValueError):a.approve(S,n.Approval(xy,'again'))
    if case=='call-budget':a.call(S,t,q);q=request(xy,2,id='second')
    with pytest.raises(ValueError):
        if case=='unapproved':a.issue(S,'0'*64)
        elif case=='noncooperative':a.residual(s,t,(.5,.5),request_id='plan')
        else:a.call(s,t,q)
    assert len(rt.trace.events)==(1 if case in ('call-budget','result-budget') else 0)

@pytest.fixture(scope='module')
def receipt():
    mod,p,m=examples()[0];cp=f.export(p,m,mod.assess(p,m));a,t,_=setup(cp);q=request(cp,2);return cp,q,a.call(S,t,q)
@pytest.mark.parametrize('case',['result','scope','descriptor','request-id','request-digest','checkpoint','operation'],ids=str)
def test_receipt_tamper(receipt,case):
    xy,q,r=receipt
    if case=='result':
        m=pb.Result.FromString(r.result);m.exact_value='1';r=replace(r,result=f.wire(m))
    if case=='scope':r=replace(r,scope=OTHER)
    if case=='descriptor':r=replace(r,descriptor_sha256='0'*64)
    if case=='request-id':r=replace(r,request_id='other')
    if case=='request-digest':r=replace(r,request_sha256='0'*64)
    if case=='checkpoint':r=replace(r,checkpoint_sha256='0'*64)
    if case=='operation':r=replace(r,operation=n.SYMBOLIC)
    with pytest.raises(ValueError):n.replay_receipt(xy,q,r,S)

@pytest.fixture(scope='module')
def plan():
    mod,p,m=examples()[0];cp=f.export(p,m,mod.assess(p,m));a,t,_=setup(cp);return cp,a.residual(S,t,(.375,.375),request_id='plan')
@pytest.mark.parametrize('case',['sum','bound','point','order','duplicate','symbolic-input','symbolic-output','symbolic-scope','plan-id','symbolic-id','scope'],ids=str)
def test_cooperative_tamper(plan,case):
    xy,r=plan
    if case=='sum':r=replace(r,exact_residual='1')
    if case=='plan-id':r=replace(r,plan_id='other')
    if case=='symbolic-id':r=replace(r,symbolic_receipt=replace(r.symbolic_receipt,request_id='other'))
    if case=='scope':r=replace(r,scope=OTHER)
    if case=='bound':r=replace(r,certified_residual_upper='1')
    if case=='point':r=replace(r,point=(.5,.5))
    if case=='order':r=replace(r,requests=r.requests[::-1])
    if case=='duplicate':r=replace(r,field_receipts=(r.field_receipts[0],)*3)
    if case=='symbolic-input':r=replace(r,symbolic_request=r.symbolic_request+' ')
    if case=='symbolic-output':r=replace(r,symbolic_receipt=replace(r.symbolic_receipt,result=b'{}'))
    if case=='symbolic-scope':r=replace(r,symbolic_receipt=replace(r.symbolic_receipt,scope=OTHER))
    with pytest.raises(ValueError):n.replay_residual(xy,r,S)

@pytest.mark.parametrize('action',['cancel','revoke','close'],ids=str)
def test_interrupted_publication(xy,action,monkeypatch):
    a,t,rt=setup(xy);q=request(xy,2);enter=Event();release=Event();orig=rt.call;errors=[]
    def delayed(*args):
        result=orig(*args);enter.set();assert release.wait(5);return result
    monkeypatch.setattr(rt,'call',delayed)
    def run():
        try:a.call(S,t,q)
        except ValueError as exc:errors.append(str(exc))
    worker=Thread(target=run);worker.start();assert enter.wait(10)
    if action=='cancel':a.cancel(S,'request')
    if action=='revoke':a.revoke(S,t)
    if action=='close':a.close()
    release.set();worker.join(10);assert not worker.is_alive() and len(errors)==1 and not a.active
    assert rt.trace.events[0]['execution_status']=='completed'

def test_deadline_refusal(xy):
    a,t,rt=setup(xy,limits=n.Limits(timeout_ms=1))
    with pytest.raises(ValueError):a.call(S,t,request(xy,2))
    assert not a.active

def test_runtime_default_research_refusal(xy):
    from cognitum.contracts import Request,HostContext
    a,t,rt=setup(xy);q=request(xy,2)
    r=rt.call(Request('request','turn',n.TENSOR,{'checkpoint':f.carrier(xy),'request':f.carrier(q)},'workspace','subject'),HostContext('workspace','subject'))
    assert r.execution_status=='unavailable' and r.result is None

def test_symbolic_independent_oracle():
    s=f.canonical(dict(point=['1/2','1/4'],weights=['1','-2','3'],values=['3','2','1'],forcing=[[[0,0],'2'],[[1,2],'8']],inputs=['0'*64,'1'*64,'2'*64],request_id='test',turn='turn',checkpoint='0'*64)).decode()
    out=n.symbolic_compute(s);assert n.symbolic_replay(s,out)==Q(-1,4)
    with pytest.raises(ValueError):n.symbolic_replay(s,out.replace('"residual":"-1/4"','"residual":"0"'))


def test_preflight_budget(xy):
    a,t,rt=setup(xy,limits=n.Limits(calls=3))
    with pytest.raises(ValueError):a.residual(S,t,(.5,.5),request_id='plan')
    assert not rt.trace.events

def test_plan_replay_rejected(xy):
    a,t,rt=setup(xy);r=a.residual(S,t,(.5,.5),request_id='plan');assert n.replay_residual(xy,r,S)
    with pytest.raises(ValueError):a.residual(S,t,(.5,.5),request_id='plan')
    assert len(rt.trace.events)==4
