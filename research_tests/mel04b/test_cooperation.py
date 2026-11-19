from dataclasses import replace, FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import math
import pytest
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.mel import admission as a, native as n, engines as e, engines_pb2 as ep
from cognitum.mel import model_engines as m, cooperation as g, exchange as x
from cognitum.mel.engine_limits import HdcLimits, KanLimits

S=a.Scope('graph-session','workspace','owner','turn')

def fixture_plan(id='graph',budget=g.Budget(step_ms=5000)):
    f=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('x','1')],domain=[(-3,3)],output_unit='1')
    ck=m.Checkpoint(m.checkpoint_wire([ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,2.,0.],mask=[1.])]))
    approval=m.Approval(ck,'review')
    # intentionally unordered; ordered duplicate query edges preserve ties.
    nodes=(g.Query('query','probe',('candidate','probe','probe')),g.Threshold('probe','vfa',.5,'1'),g.Vfa('vfa','kan',f),g.Kan('kan','seed',approval,('x',),('x',)),g.Threshold('candidate','base',.5,'1'),g.Vfa('base','seed',f),g.Seed('seed',n.points(f,[[0.],[.5],[1.]])))
    return g.Plan(id,S,nodes,budget)


def setup(plan,*,pin=True,limits=None):
    r=Registry();r.install(n.NativeVFAPlugin,enabled=True);r.install(e.EnginePlugin,enabled=True)
    for op in n.OP:r.nominate(op,n.NAME)
    for op in e.OPERATIONS:r.nominate(op,e.NAME)
    h=a.Admission(Runtime(r),S.session,enable_engines=True,enable_model_codecs=True);grants=[];approved=set()
    for v in plan.nodes:
        op=g._op(v)
        if op is None:continue
        route=next(q for q in a.routes(include_engines=True) if q.operation==op);kwargs={}
        if type(v) is g.Kan and pin:
            c=v.approval.checkpoint
            if c.identity not in approved:h.approve_checkpoint(S,c.wire,expected_sha256=c.identity,review_id=v.approval.review_id);approved.add(c.identity)
            kwargs=dict(model_codec=True,checkpoint_sha256=c.identity)
        profile=(limits or {}).get(v.id,a.Limits(timeout_ms=5000) if op.startswith('vfa') else KanLimits(timeout_ms=5000) if op.startswith('kan') else HdcLimits(timeout_ms=5000))
        grants.append((v.id,h.issue(S,route,profile,ttl_ms=60000,**kwargs)))
    return h,tuple(grants)


def byid(result):return {v.node_id:v for v in result.nodes}
def no_payload(result):assert all(v.worker is None and v.transfer is None and v.output is None for v in result.nodes)


def test_worker_graph_all_three_engines():
    p=fixture_plan();h,t=setup(p);o=g.execute(h,p,t);r=byid(o)
    assert o.status=='completed' and o.plan_sha256==p.identity and o.scope==S and o.reserved_calls==4
    assert [v.node_id for v in o.nodes]==['seed','kan','vfa','probe','base','candidate','query']
    k=list(r['kan'].output.message().body.samples.values);v=list(r['vfa'].output.message().body.samples.values)
    assert max(abs(y-2*math.exp(-z*z)) for y,z in zip(k,(0,.5,1)))<3e-7
    assert max(abs(y-math.exp(-.5*z*z)) for y,z in zip(v,k))<5e-13
    assert r['vfa'].output.message().body.transfer_sha256.hex()==r['vfa'].transfer_sha256
    assert r['kan'].transfer.message().source_sha256==[r['seed'].output.message().content_sha256]
    q=ep.EngineResult.FromString(r['query'].worker.result_frame).query
    assert list(q.hamming_distance)==[2,0,0] and list(q.best_index)==[1,2] and r['query'].lossy_history
    assert r['probe'].lossy_history and not r['vfa'].lossy_history
    assert len(h._seen)==4 and all(z.calls_left==0 for z in h._grants.values())
    assert o.charged_work<=p.budget.work and o.reserved_bytes<=p.budget.bytes


def test_bind_lift_vfa_loss_free():
    p0=fixture_plan();f=next(v.function for v in p0.nodes if type(v) is g.Vfa)
    c=e.make_call('hdc.bind',ep.BindInput(left=ep.BinaryVector(dimension=3,bits=b'\x05'),right=ep.BinaryVector(dimension=3,bits=b'\x03')),'bindgraph:bind',S.turn)
    f=n.gaussian([[0]],[[1]],[1],constant=0,axes=[('bit0','1')],domain=[(-1,2)],output_unit='1')
    p=g.Plan('bindgraph',S,(g.Bind('bind',c),g.Lift('lift','bind',3,1),g.Vfa('eval','lift',f)),g.Budget(step_ms=5000));h,t=setup(p);o=g.execute(h,p,t);r=byid(o)
    assert o.status=='completed' and r['bind'].output.message().body.bits.packed_bits==b'\x06'
    assert list(r['lift'].output.message().body.samples.values)==[0,1,1] and not r['eval'].lossy_history


def test_threshold_lift_loss_propagation():
    p0=fixture_plan();s=next(v for v in p0.nodes if type(v) is g.Seed)
    f=n.gaussian([],[],[],constant=1,axes=[('bit0','1')],domain=[(-1,2)],output_unit='1')
    p=g.Plan('loss',S,(s,g.Threshold('bits',s.id,.5,'1'),g.Lift('lift','bits',3,1),g.Vfa('v','lift',f)),g.Budget(step_ms=5000));h,t=setup(p);o=g.execute(h,p,t);r=byid(o)
    assert o.status=='completed' and r['v'].lossy_history and r['v'].output.message().body.lossy_history


@pytest.mark.parametrize('case',['empty','list','duplicate','missing','cycle','terminal','wrong_kind','unknown','bad_id','too_many','edges','no_calls','call_limit','bad_seed','bad_kan','bad_threshold','bad_lift','wrong_bind_scope','wrong_bind_id','material'])
def test_static_refusals(case):
    p=fixture_plan();nodes=list(p.nodes);budget=p.budget;seed=nodes[-1];f=nodes[2].function
    if case=='empty':nodes=[]
    elif case=='list':
        with pytest.raises(ValueError):replace(p,nodes=nodes)
        return
    elif case=='duplicate':nodes.append(seed)
    elif case=='missing':nodes[2]=replace(nodes[2],parent='missing')
    elif case=='cycle':nodes[3]=replace(nodes[3],parent='vfa')
    elif case=='terminal':nodes[2]=replace(nodes[2],parent='query')
    elif case=='wrong_kind':nodes[2]=replace(nodes[2],parent='probe')
    elif case=='unknown':nodes[2]=object()
    elif case=='bad_id':nodes[2]=replace(nodes[2],id='bad id')
    elif case=='too_many':nodes+= [replace(seed,id='a'),replace(seed,id='b')]
    elif case=='edges':nodes[0]=replace(nodes[0],candidates=('probe',)*16)
    elif case=='no_calls':nodes=[seed]
    elif case=='call_limit':budget=replace(budget,calls=3)
    elif case=='bad_seed':nodes[-1]=replace(seed,points=f)
    elif case=='bad_kan':nodes[3]=replace(nodes[3],input_axes=('x','x'))
    elif case=='bad_threshold':nodes[1]=replace(nodes[1],at_least=float('nan'))
    elif case=='bad_lift':nodes[2]=g.Lift('vfa','probe',True,1)
    elif case in ('wrong_bind_scope','wrong_bind_id'):
        c=e.make_call('hdc.bind',ep.BindInput(left=ep.BinaryVector(dimension=1,bits=b'\x00'),right=ep.BinaryVector(dimension=1,bits=b'\x01')),'graph:b' if case=='wrong_bind_scope' else 'other','other' if case=='wrong_bind_scope' else S.turn)
        nodes=[g.Bind('b',c)]
    else:budget=replace(budget,bytes=1)
    with pytest.raises(ValueError):replace(p,nodes=tuple(nodes),budget=budget)


@pytest.mark.parametrize('field,value',[('work',0),('work',g.MAX_WORK+1),('bytes',True),('bytes',g.MAX_BYTES+1),('calls',9),('time_ms',0),('time_ms',30001),('step_ms',10001)])
def test_invalid_budget(field,value):
    with pytest.raises(ValueError):replace(g.Budget(),**{field:value})


def test_plan_identity_changes_and_immutability():
    p=fixture_plan();assert p.identity==fixture_plan().identity
    assert p.identity!=replace(p,budget=replace(p.budget,work=p.budget.work-1)).identity
    assert p.identity!=replace(p,scope=replace(S,turn='other')).identity
    assert p.identity!=replace(p,nodes=tuple(reversed(p.nodes))).identity
    assert p.identity!=replace(p,nodes=(replace(p.nodes[0],candidates=('probe','candidate','probe')),)+p.nodes[1:]).identity
    with pytest.raises(FrozenInstanceError):p.id='x'


@pytest.mark.parametrize('case',['missing','extra','duplicate','same_token','bad_token','list','bad_binding'])
def test_exact_grant_mapping(case):
    p=fixture_plan();h,t=setup(p)
    if case=='missing':t=t[:-1]
    elif case=='extra':t=t+(('seed',b'x'*32),)
    elif case=='duplicate':t=t[:-1]+(t[0],)
    elif case=='same_token':t=t[:-1]+((t[-1][0],t[0][1]),)
    elif case=='bad_token':t=t[:-1]+((t[-1][0],b'x'),)
    elif case=='list':t=list(t)
    else:t=t[:-1]+(t[-1][0],)
    with pytest.raises(ValueError):g.execute(h,p,t)
    assert not h._seen


@pytest.mark.parametrize('case',['foreign','revoked','unpinned','wrong_route','wrong_checkpoint'])
def test_kan_authority_refusal(case):
    p=fixture_plan();h,t=setup(p,pin=case!='unpinned');ts=dict(t)
    if case=='foreign':ts['kan']=b'x'*32
    elif case=='revoked':h.revoke(S,ts['kan'])
    elif case=='wrong_route':ts['kan'],ts['base']=ts['base'],ts['kan']
    elif case=='wrong_checkpoint':
        v=p.nodes[3];layer=v.approval.checkpoint.message().layers[0];layer.coefficients[1]=3
        c=m.Checkpoint(m.checkpoint_wire([layer]));p=replace(p,nodes=p.nodes[:3]+(replace(v,approval=m.Approval(c,'other')),)+p.nodes[4:])
    o=g.execute(h,p,tuple(ts.items()));r=byid(o)
    assert o.status=='denied' and r['kan'].status=='denied' and r['vfa'].status=='blocked_dependency' and r['base'].status=='not_run'
    no_payload(o);assert not h._seen


def test_checkpoint_revoked_before_execution():
    p=fixture_plan();h,t=setup(p);h.revoke_checkpoint(S,p.nodes[3].approval.checkpoint.identity);o=g.execute(h,p,t)
    assert o.status=='denied' and not h._seen;no_payload(o)


@pytest.mark.parametrize('kind',['work','bytes'])
def test_graph_budget_denies_before_call(kind,monkeypatch):
    p=fixture_plan();budget=replace(p.budget,**{kind:1 if kind=='work' else len(g._material(p))+g.x.MAX_OBJECT});p=replace(p,budget=budget)
    h,t=setup(p);monkeypatch.setattr(Runtime,'call',lambda *v,**kw:pytest.fail('unexpected dispatch'))
    o=g.execute(h,p,t);assert o.status=='resource_denied' and o.reserved_calls==0 and not h._seen;no_payload(o)


def test_cumulative_work_denial_after_first_worker():
    p=fixture_plan();h,t=setup(p);first=g.execute(h,p,t);assert first.status=='completed'
    # Measure actual accounting of prefix in a fresh session-local admission.
    p=replace(p,budget=replace(p.budget,work=first.charged_work-1));h,t=setup(p);o=g.execute(h,p,t)
    assert o.status=='resource_denied' and 1<=len(h._seen)<4 and o.charged_work<=p.budget.work;no_payload(o)


def test_per_grant_budget_not_overridden():
    p=fixture_plan();h,t=setup(p,limits={'kan':KanLimits(work=1,timeout_ms=5000)});o=g.execute(h,p,t)
    assert o.status=='resource_denied' and byid(o)['kan'].status=='resource_denied' and not h._seen;no_payload(o)


def test_invalid_dynamic_mapping_stops_downstream():
    p=fixture_plan();v=p.nodes[3];p=replace(p,nodes=p.nodes[:3]+(replace(v,input_axes=('other',)),)+p.nodes[4:]);h,t=setup(p);o=g.execute(h,p,t)
    assert o.status=='invalid_exchange' and byid(o)['vfa'].status=='blocked_dependency' and not h._seen;no_payload(o)


def test_replay_new_tokens_cannot_repeat_graph():
    p=fixture_plan();h,t=setup(p);assert g.execute(h,p,t).status=='completed'
    # Only replace first worker token with a new valid pinned grant, retaining other tokens.
    v=p.nodes[3];route=next(r for r in a.routes(include_engines=True) if r.operation=='kan.evaluate')
    token=h.issue(S,route,KanLimits(timeout_ms=5000),ttl_ms=60000,model_codec=True,checkpoint_sha256=v.approval.checkpoint.identity)
    o=g.execute(h,p,tuple((i,token if i=='kan' else t0) for i,t0 in t));assert o.status=='replay_denied';no_payload(o)


def test_pre_cancel_and_one_shot():
    p=fixture_plan();h,t=setup(p);c=g.Cancellation();assert c.cancel() and not c.cancel();o=g.execute(h,p,t,cancellation=c)
    assert o.status=='cancelled' and not h._seen and not c.cancel();no_payload(o)
    with pytest.raises(ValueError):g.execute(h,p,t,cancellation=c)


def test_inflight_cancel_real_worker(monkeypatch):
    p=fixture_plan();h,t=setup(p);c=g.Cancellation();ready=Event();release=Event();orig=Runtime.call
    def delayed(*args,**kw):
        r=orig(*args,**kw);assert r.execution_status=='completed';ready.set();assert release.wait(10);return r
    monkeypatch.setattr(Runtime,'call',delayed)
    with ThreadPoolExecutor(1) as pool:
        f=pool.submit(g.execute,h,p,t,cancellation=c)
        try:assert ready.wait(10);assert c.cancel()
        finally:release.set()
        o=f.result(timeout=10)
    assert o.status=='cancelled' and len(h._seen)==1 and not h._active;no_payload(o)


def test_graph_deadline_controlled_clock(monkeypatch):
    p=fixture_plan();h,t=setup(p);clock=[0];monkeypatch.setattr(g,'monotonic_ns',lambda:clock[0]);orig=Runtime.call
    def delayed(*args,**kw):
        result=orig(*args,**kw);clock[0]=p.budget.time_ms*1000000;return result
    monkeypatch.setattr(Runtime,'call',delayed);o=g.execute(h,p,t)
    assert o.status=='timed_out' and len(h._seen)==1;no_payload(o)


def test_wrong_worker_result_blocks_all(monkeypatch):
    p=fixture_plan();h,t=setup(p);orig=Runtime.call
    def altered(*args,**kw):return replace(orig(*args,**kw),correlation_id='wrong')
    monkeypatch.setattr(Runtime,'call',altered);o=g.execute(h,p,t)
    assert o.status=='error' and len(h._seen)==1 and byid(o)['vfa'].status=='blocked_dependency';no_payload(o)


def test_verify_transfer_called_before_dispatch(monkeypatch):
    p=fixture_plan();h,t=setup(p);monkeypatch.setattr(x,'verify_transfer',lambda *args,**kw:(_ for _ in ()).throw(ValueError('bad link')))
    o=g.execute(h,p,t);assert o.status=='invalid_exchange' and not h._seen;no_payload(o)


def test_byte_reservation_before_transfer_preparation(monkeypatch):
    p=fixture_plan();p=replace(p,budget=replace(p.budget,bytes=len(g._material(p))+g.x.MAX_OBJECT));h,t=setup(p)
    monkeypatch.setattr(x,'prepare_kan',lambda *v,**kw:pytest.fail('allocated unreserved transfer'))
    o=g.execute(h,p,t);assert o.status=='resource_denied' and o.reserved_calls==0 and not h._seen;no_payload(o)


def test_checkpoint_discovery_lock_wait_cancellation():
    p=fixture_plan();h,t=setup(p);c=g.Cancellation();started=Event();registry=h._runtime.registry
    # Keep the registry busy; cancel without waiting for the owner to release.
    def run():started.set();return g.execute(h,p,t,cancellation=c)
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            f=pool.submit(run);assert started.wait(5);assert c.cancel();o=f.result(timeout=5)
    assert o.status=='cancelled' and not h._seen;no_payload(o)


def test_checkpoint_discovery_lock_wait_deadline():
    p=fixture_plan(budget=g.Budget(time_ms=200,step_ms=100));h,t=setup(p);registry=h._runtime.registry
    with ThreadPoolExecutor(1) as pool:
        with registry.lock:
            o=pool.submit(g.execute,h,p,t).result(timeout=5)
    assert o.status=='timed_out' and not h._seen;no_payload(o)


def test_wrong_grant_owner_non_kan():
    p=fixture_plan();h,t=setup(p);p=replace(p,nodes=tuple(v for v in p.nodes if v.id not in ('query','probe','vfa','kan','candidate')));t=tuple((v,tok) for v,tok in t if v=='base');p=replace(p,scope=replace(S,subject='other'))
    o=g.execute(h,p,t);assert o.status=='denied' and not h._seen;no_payload(o)
