from dataclasses import replace
from fractions import Fraction
import hashlib,json
import pytest
from cognitum.research.kan_trainable import Layer, Network
from cognitum.mel import admission as a, cooperation as g, exchange as x, native as n, engines as e
from cognitum.mel import polynomial_kan as p, polynomial_model as pm, model_reference as r, intent_reference as ir, verified_graph as vg, uncertainty_pb2 as wp
from cognitum.mel.engine_limits import HdcLimits
from cognitum.registry import Registry
from cognitum.runtime import Runtime
S=a.Scope('cog04c','work','owner','turn')
APP=p.Approval(p.export_checkpoint(Network((Layer('chebyshev',2,[[-1,1]],[[[.5,0,.5]]],[[1]],[0]),))),'square')
CLAMP=p.Approval(p.export_checkpoint(Network((Layer('spline_clamped',1,[[-1,-1,0,1,1]],[[[-.5,0,.5]]],[[1]],[0]),))),'clamp')
TOL=1e-8;ARGS={'points':[[.5]],'order':2}
def raw(args=ARGS):return r.canonical(dict(tool=pm.PUBLIC,arguments=args))
def allowed(app=APP,tol=TOL):return r.Allowed((p.OP,),tolerance=tol,polynomial_approval=app)
def intent(args=ARGS,component=0,threshold=.25,app=APP,tol=TOL):return ir.Intent(S,p.OP,r.canonical(args),float(threshold),app.checkpoint.identity,component,tol)
def test_model_feedback(tmp_path):
    with r.ReferenceTurn(S,allowed()) as t:
        schema=t.schemas();assert len(schema)==1 and schema[0]['function']['name']==pm.PUBLIC
        assert set(schema[0]['function']['parameters']['properties'])=={'points','order'}
        result=t.dispatch(raw());assert result['ok'],result
        v=result['result'];assert v['component_shapes']==[[1,1],[1,1,1],[1,1,1,1]] and v['values']==[.25,1.,2.]
        assert v['intervals']==[dict(lower=z,upper=z) for z in v['values']] and v['absolute_error_upper']==[0.]*3
        assert len(t.host._seen)==1 and not t.dispatch(raw())['ok']
        assert v['result_sha256']==hashlib.sha256(t.last_receipt.result_frame).hexdigest()
        retained={'request.pb':t.last_call.wire,'result.pb':t.last_receipt.result_frame,'feedback.json':r.canonical(result).encode('ascii'),'audit.json':r.canonical(t.audit).encode('ascii'),'schema.json':r.canonical(schema).encode('ascii')}
        for name,data in retained.items():(tmp_path/name).write_bytes(data)
        (tmp_path/'model_summary.json').write_text(json.dumps(dict(real_worker=True,fresh_gguf_inference=False,values=v['values'],checkpoint_sha256=v['checkpoint_sha256'],sha256={name:hashlib.sha256(data).hexdigest() for name,data in retained.items()}),indent=2))
@pytest.mark.parametrize('app,points,order,component,threshold,decision',[(APP,[[.5]],0,0,.25,'above'),(APP,[[.5]],1,1,1.,'above'),(APP,[[.5]],2,2,3.,'below'),(CLAMP,[[.2]],1,1,.5,'above'),(APP,[[.1]],0,0,.010000000000000002,'uncertain')])
def test_bound_publication(app,points,order,component,threshold,decision):
    args=dict(points=points,order=order)
    with ir.BoundTurn(intent(args,component,threshold,app),allowed(app)) as t:
        z=t.dispatch(raw(args));assert z['ok'],z
        v=t.publish(r.canonical({'answer':decision}));assert v['ok'],(z,v)
        assert v['answer']==decision and v['source']=='model_verified' and t.worker_calls==1
        assert not t.publish('{"answer":"above"}')['ok']
@pytest.mark.parametrize('bad',[{'points':[[.5]],'order':True},{'points':[[True]],'order':2},{'points':[[.5,.2]],'order':2},{'points':[[2.]],'order':2},{'points':[[.5]],'order':3},{'points':[[.5]],'order':2,'tolerance':0.},{'points':[[.5]],'order':2,'checkpoint':'evil'},{'points':[[.4]],'order':2},{'points':[[.5]],'order':0}])
def test_wrong_intent_no_worker(bad):
    with ir.BoundTurn(intent(),allowed()) as t:
        assert not t.dispatch(raw(bad))['ok'] and t.worker_calls==0 and not t.publish('{"answer":"above"}',host_fallback=True)['ok']
@pytest.mark.parametrize('change',['wrong_answer','revoked','checkpoint_revoked','receipt','tampered_result','close','intent_tolerance','signed_zero'])
def test_grounding_adversarial(change):
    if change=='intent_tolerance':
        with pytest.raises(ValueError):ir.BoundTurn(intent(tol=1e-7),allowed())
        return
    if change=='signed_zero':
        args=dict(points=[[0.]],order=0)
        with ir.BoundTurn(intent(args),allowed()) as t:
            assert not t.dispatch(raw(dict(points=[[-0.]],order=0)))['ok'] and t.worker_calls==0
        return
    with ir.BoundTurn(intent(),allowed()) as t:
        assert t.dispatch(raw())['ok']
        if change=='revoked':t.turn.host.revoke(S,t.turn.grants[pm.PUBLIC])
        elif change=='checkpoint_revoked':t.turn.host.revoke_checkpoint(S,APP.checkpoint.identity)
        elif change=='receipt':t.turn.last_receipt=replace(t.turn.last_receipt,request_sha256='0'*64)
        elif change=='tampered_result':
            rr=p.pb.Result.FromString(t.turn.last_receipt.result_frame);rr.components[0].observed=.5;rr.components[0].lower=.5;rr.components[0].upper=.5
            data=p.serialize(rr);t.turn.last_receipt=replace(t.turn.last_receipt,result_frame=data,result_sha256=hashlib.sha256(data).hexdigest())
        elif change=='close':t.close()
        assert not t.publish('{"answer":"below"}' if change=='wrong_answer' else '{"answer":"above"}',host_fallback=change!='wrong_answer')['ok']
def test_verified_fallback():
    with ir.BoundTurn(intent(),allowed()) as t:
        assert t.dispatch(raw())['ok'];v=t.publish('{"answer":"below"}',host_fallback=True)
        assert v['ok'] and v['answer']=='above' and v['source']=='host_verified_fallback'
def create_host(model=False):
    reg=Registry();reg.install(n.NativeVFAPlugin,enabled=True);reg.install(e.EnginePlugin,enabled=True);reg.install(p.PolynomialPlugin,enabled=True)
    for op in n.OP:reg.nominate(op,n.NAME)
    for op in e.OPERATIONS:reg.nominate(op,e.NAME)
    reg.nominate(p.OP,p.NAME)
    return a.Admission(Runtime(reg),S.session,enable_engines=True,enable_model_codecs=True,enable_polynomial_kan=True,enable_polynomial_model_codecs=model)
def approve(h,app):h.approve_polynomial_checkpoint(S,app.checkpoint.wire,expected_sha256=app.checkpoint.identity,review_id=app.review_id)
def test_host_codec():
    h=create_host(True);approve(h,APP);route=next(v for v in a.routes(include_engines=True,include_polynomial_kan=True) if v.operation==p.OP)
    token=h.issue(S,route,p.Limits(timeout_ms=10000),checkpoint_sha256=APP.checkpoint.identity,model_codec=True,model_tolerance=TOL)
    try:
        offer=h.discover_model(S,token);assert not offer['execution_authorized'] and offer['checkpoint_sha256']==APP.checkpoint.identity
        with pytest.raises(ValueError):h.discover_model(replace(S,subject='other'),token)
        with pytest.raises(ValueError):h.execute_model(S,token,'bad',pm.PUBLIC,'0'*64,r.canonical(ARGS),timeout_ms=9000)
        wrong=pm.bind(APP,1e-7,r.canonical(ARGS),'wrong',S.turn)
        assert h.execute(S,token,'wrong',wrong.wire,timeout_ms=9000).status=='invalid_input' and not h._seen
        answer=h.execute_model(S,token,'good',pm.PUBLIC,offer['codec_sha256'],r.canonical(ARGS),timeout_ms=9000)
        assert answer['ok'] and answer['result']['values']==[.25,1.,2.]
    finally:h.close()
def graph(app=APP,*,tol=TOL,threshold=.8,seed=(0.,.5,1.),budget=g.Budget(step_ms=10000)):
    f=n.gaussian([[0.]],[[.5]],[1.],constant=0.,axes=[('x','1')],domain=[(-1.,1.)],output_unit='1')
    return g.Plan('polygraph',S,(g.Query('query','probe',('candidate','probe','probe')),g.Threshold('probe','vfa',threshold,'1'),g.Vfa('vfa','poly',f),g.PolynomialKan('poly','seed',app,('x',),('x',),tol),g.Threshold('candidate','base',threshold,'1'),g.Vfa('base','seed',f),g.Seed('seed',n.points(f,[[z] for z in seed]))),budget)
def setup(plan,wrong_pin=False):
    h=create_host();tokens=[];seen=set()
    for v in plan.nodes:
        op=g._op(v)
        if op is None:continue
        route=next(q for q in a.routes(include_engines=True,include_polynomial_kan=True) if q.operation==op);kw={}
        if op==p.OP:
            app=CLAMP if wrong_pin else v.approval
            if app.checkpoint.identity not in seen:approve(h,app);seen.add(app.checkpoint.identity)
            kw={'checkpoint_sha256':app.checkpoint.identity};limits=p.Limits(timeout_ms=10000)
        else:limits=a.Limits(timeout_ms=10000) if op in n.OP else HdcLimits(timeout_ms=10000)
        tokens.append((v.id,h.issue(S,route,limits,ttl_ms=60000,**kw)))
    return h,tuple(tokens)
TOLS=(('poly',(TOL,)),('vfa',(1e-8,)),('base',(1e-8,)))
def test_automatic_three_engine_graph(tmp_path):
    plan=graph();h,t=setup(plan)
    try:
        v=vg.execute_verified(h,plan,t,TOLS);assert v.status=='verified',v
        assert v.reserved_calls==4 and len(h._seen)==4
        records={z.node_id:z for z in v.outcome.nodes};poly=records['poly'];assert poly.output.message().body.origin==x.p.POLYNOMIAL_VALUES
        assert list(poly.output.message().body.samples.values)==[0.,.25,1.]
        assert poly.transfer.message().target_checkpoint_sha256.hex()==APP.checkpoint.identity and poly.output.message().body.transfer_sha256.hex()==poly.transfer_sha256
        nodes={z.node_id:z for z in wp.GraphWitness.FromString(v.witness).nodes}
        assert list(nodes['query'].best_index)==[1,2] and list(nodes['query'].hamming_distance)==[1,0,0]
        assert vg.replay(plan,v.outcome,TOLS,v.witness)
        retained={'graph_witness.pb':v.witness,'plan.material':g._validate(plan)[1]}
        for row in v.outcome.nodes:
            if row.worker:retained[row.node_id+'.result.pb']=row.worker.result_frame
            if row.transfer:retained[row.node_id+'.transfer.pb']=row.transfer.wire
            if row.output:retained[row.node_id+'.object.pb']=row.output.wire
        for name,data in retained.items():(tmp_path/name).write_bytes(data)
        (tmp_path/'summary.json').write_text(json.dumps(dict(calls=v.reserved_calls,distances=list(nodes['query'].hamming_distance),ties=list(nodes['query'].best_index),plan_sha256=plan.identity,source_origin='POLYNOMIAL_VALUES',witness_sha256=hashlib.sha256(v.witness).hexdigest(),sha256={name:hashlib.sha256(data).hexdigest() for name,data in retained.items()}),indent=2))
        for mut in (replace(poly,output=records['seed'].output),replace(poly,transfer_sha256='0'*64),replace(poly,worker=replace(poly.worker,result_sha256='0'*64))):
            forged=replace(v.outcome,nodes=tuple(mut if z.node_id=='poly' else z for z in v.outcome.nodes))
            with pytest.raises(ValueError):vg.replay(plan,forged,TOLS,v.witness)
    finally:h.close()
@pytest.mark.parametrize('case',['unguarded','wrong_pin','wrong_axes','budget','cancel','tolerance','schema','missing_grant'])
def test_graph_refusal(case):
    plan=graph()
    if case=='wrong_axes':plan=replace(plan,nodes=tuple(replace(z,input_axes=('bad',)) if z.id=='poly' else z for z in plan.nodes))
    if case=='budget':plan=replace(plan,budget=replace(plan.budget,work=1))
    h,t=setup(plan,wrong_pin=case=='wrong_pin')
    try:
        if case in ('unguarded','schema','missing_grant'):
            with pytest.raises(ValueError):
                if case=='unguarded':g.execute(h,plan,t)
                elif case=='schema':vg.execute_verified(h,plan,t,TOLS[:-1])
                else:vg.execute_verified(h,plan,t[:-1],TOLS)
            assert not h._seen;return
        handle=g.Cancellation()
        if case=='cancel':handle.cancel()
        if case=='tolerance':
            plan=graph(seed=(.1,.5,1.));v=vg.execute_verified(h,plan,t,(('poly',(0.,)),*TOLS[1:]))
        else:v=vg.execute_verified(h,plan,t,TOLS,cancellation=handle)
        assert v.status!='verified' and v.outcome is None and v.witness is None and all(rid!='polygraph:query' for _,rid in h._seen)
    finally:h.close()
def test_uncertain_threshold():
    f=n.gaussian([],[],[],constant=1.,axes=[('x','1')],domain=[(-1,1)],output_unit='1');threshold=.010000000000000002
    plan=g.Plan('ambig',S,(g.Seed('seed',n.points(f,[[.1]])),g.PolynomialKan('poly','seed',APP,('x',),('x',),TOL),g.Threshold('bits','poly',threshold,'1'),g.Lift('lift','bits',1,1),g.Vfa('next','lift',n.gaussian([],[],[],constant=1.,axes=[('bit0','1')],domain=[(-1,2)],output_unit='1'))),g.Budget(step_ms=10000))
    h,t=setup(plan)
    try:
        v=vg.execute_verified(h,plan,t,(('poly',(TOL,)),('next',(0.,))))
        if v.status=='verified':
            node=next(z for z in wp.GraphWitness.FromString(v.witness).nodes if z.node_id=='bits');assert node.verified_packed_bits==bytes([int(Fraction(.1)**2>=Fraction(threshold))])
        else:assert v.status=='verification_refused' and v.reserved_calls==1 and v.witness is None and v.outcome is None
    finally:h.close()

def test_closed_result_schema():
    # Independently validated with jsonschema in local preflight; the hosted
    # test checks this closed profile without introducing a runtime dependency.
    schema=pm.descriptor()[1];ok,err=schema['result_schema']['oneOf']
    assert ok['additionalProperties'] is False and err['additionalProperties'] is False
    result_schema=ok['properties']['result'];assert result_schema['additionalProperties'] is False
    with r.ReferenceTurn(S,allowed()) as t:
        good=t.dispatch(raw());assert good['ok']
        assert set(good)==set(ok['required']) and set(good['result'])==set(result_schema['required'])
        assert result_schema['properties']['assurance']['const']==good['result']['assurance']
        assert 'approval' not in result_schema['properties']

def test_clamped_graph_uses_same_executor():
    plan=graph(CLAMP,seed=(-.5,0.,.5));h,t=setup(plan)
    try:
        result=vg.execute_verified(h,plan,t,TOLS);assert result.status=='verified',result
        nodes={z.node_id:z for z in result.outcome.nodes}
        assert list(nodes['poly'].output.message().body.samples.values)==[-.25,0.,.25]
        assert vg.replay(plan,result.outcome,TOLS,result.witness)
    finally:h.close()

def test_review_identity_not_substituted():
    plan=graph();h,t=setup(plan)
    changed=replace(plan,nodes=tuple(replace(z,approval=replace(z.approval,review_id='unreviewed')) if z.id=='poly' else z for z in plan.nodes))
    assert plan.identity!=changed.identity
    try:
        res=vg.execute_verified(h,changed,t,TOLS);assert res.status=='denied' and res.outcome is None and not h._seen
    finally:h.close()

def test_uncertain_vfa_to_polynomial_to_bits_refusal():
    # VFA output ideal in [1-2^-256,1], observation rounds to 1.
    # Pass it through identity KAN; outward enclosures must never promote
    # uncertainty into exact binary truth at the threshold.
    f=n.gaussian([[0.]],[[1.]],[-1.],constant=1.,axes=[('x','1')],domain=[(-2000.,2000.)],output_unit='1')
    ident=p.Approval(p.export_checkpoint(Network((Layer('chebyshev',1,[[-1,1]],[[[0,1]]],[[1]],[0]),))),'identity')
    nxt=n.gaussian([],[],[],constant=1.,axes=[('bit0','1')],domain=[(-1.,2.)],output_unit='1')
    plan=g.Plan('uncertain',S,(g.Seed('seed',n.points(f,[[1000.]])),g.Vfa('vfa','seed',f),g.PolynomialKan('poly','vfa',ident,('value',),('value',),TOL),g.Threshold('bit','poly',1.,'1'),g.Lift('lift','bit',1,1),g.Vfa('end','lift',nxt)),g.Budget(step_ms=10000))
    h,t=setup(plan)
    try:
        result=vg.execute_verified(h,plan,t,(('vfa',(1e-8,)),('poly',(TOL,)),('end',(0.,))))
        assert result.status=='verification_refused' and result.outcome is None and result.witness is None
        assert result.reserved_calls==2 and (S,'uncertain:end') not in h._seen
        assert len(h._seen)==2
    finally:h.close()

def test_legacy_catalog_unchanged():
    from research_tests.mel04b.test_cooperation import fixture_plan
    assert fixture_plan().identity=='8ca773577fab4f2a5619d6467b8abc89f900390fb227d48cf4d6ccc51908557f'
    assert p.OP not in r.OPS and pm.PUBLIC not in r.NAMES.values()
    assert all(v.operation!=p.OP for v in a.routes(include_engines=True))
    with r.ReferenceTurn(S,r.Allowed(('hdc.bind',))) as t:
        assert [v['function']['name'] for v in t.schemas()]==['mel_hdc_bind']
        assert not t.dispatch(raw())['ok'] and not t.host._seen


def test_live_generation_grammar_all_six_routes():
    from tools.mel06a.schema_grammar import request_grammar
    from research_tests.mel06a.test_reference import APP as LEGACY
    with r.ReferenceTurn(S,r.Allowed(r.ALL_OPS,LEGACY,TOL,APP)) as t:
        grammar=request_grammar(t.schemas())
        assert all(r.name_for(op) in grammar for op in r.ALL_OPS)
        assert '"0" | "1" | "2"' in grammar and 'refuse' in grammar
        assert APP.checkpoint.identity not in grammar and '0.5' not in grammar
    with r.ReferenceTurn(S,allowed()) as t:
        offers=t.schemas();offers[0]['function']['parameters']['properties']['order']['maximum']=3
        with pytest.raises(ValueError):request_grammar(offers)
