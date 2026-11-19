from dataclasses import replace
import json
import hashlib
import pytest
from cognitum.mel import model_reference as r, admission as a, model_engines as m, engines_pb2 as ep, native as n, exchange as x

S=a.Scope('s','w','u','t')
APP=m.Approval(m.Checkpoint(m.checkpoint_wire([ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,2.,0.],mask=[1.])])),'review')
VFA={'axes':[{'name':'x','unit':'1'}],'domain':[{'lower':-1,'upper':1}],'terms':[{'center':[0],'width':[1],'weight':2}],'constant':0,'output_unit':'1','points':[[.5]]}
ARG={'hdc.bind':{'left':'101','right':'110'},'hdc.query':{'probe':'101','candidates':['101','101','110']},'kan.evaluate':{'points':[[0.],[.5]]},'vfa.evaluate':VFA,'vfa.gradient':VFA}
def request(op):return json.dumps(dict(tool=r.NAMES[op],arguments=ARG[op]))
def setup(ops=r.OPS,tol=1e-5):return r.ReferenceTurn(S,r.Allowed(ops,APP if 'kan.evaluate' in ops else None,tol))

@pytest.mark.parametrize('op',r.OPS)
def test_real_scoped_workers(op):
    with setup() as t:
        out=t.dispatch(request(op));assert out['ok'],out
        assert len(t.host._seen)==1 and t.audit['operation']==op
        assert t.audit['result_sha256']==hashlib.sha256(bytes.fromhex(t.audit['result_hex'])).hexdigest()
        p=out['result']
        if op=='hdc.bind':assert p['bits']=='011'
        elif op=='hdc.query':assert p['hamming_distance']==[0,0,2] and p['best_index']==[0,1]
        else:
            assert p['assurance']=='represented_input_enclosure' and len(p['intervals'])==len(p['values'])
            assert all(b['lower']<=b['upper'] for b in p['intervals'])
        assert t.dispatch(request(op))==r.refusal('turn_attempt_limit')

@pytest.mark.parametrize('raw',[ '{"tool":"mel_hdc_bind","arguments":{"left":"1","right":"1"},"grant":true}', '{"tool":"mel_hdc_bind","tool":"mel_hdc_query","arguments":{}}','{"tool":"mel_hdc_bind","arguments":{"left":"1","left":"0","right":"1"}}','{"tool":"mel_hdc_bind","arguments":{"left":"1","right":"1","result":"0"}}','{"tool":"mel_kan_evaluate","arguments":{"points":[[0]],"checkpoint":"fake"}}','{"tool":"mel_kan_evaluate","arguments":{"points":[[9]]}}','{"tool":"mel_hdc_bind","arguments":{"left":"1","right":"01"}}','{"tool":"mel_vfa_evaluate","arguments":{"constant":NaN}}','{"tool":"shell_exec","arguments":{"command":"echo bad"}}','{"tool":"mel_hdc_bind","arguments":[]}', '```json\n{}\n```', '{"result":{"ok":true}}',' '*8193],ids=['grant','duplicate-tool','duplicate-arg','fake-result','fake-checkpoint','domain','dim','nan','shell','array','fence','receipt','size'])
def test_bad_request_no_worker(raw):
    with setup() as t:
        assert not t.dispatch(raw)['ok'] and not t.host._seen and t.audit is None

@pytest.mark.parametrize('op',['hdc.query','kan.evaluate','vfa.evaluate'])
def test_disabled_operations(op):
    with setup(('hdc.bind',)) as t:
        assert t.dispatch(request(op))==r.refusal('not_authorized') and not t.host._seen


def test_empty_allowlist():
    with setup(()) as t:assert t.schemas()==[] and t.dispatch(request('hdc.bind'))==r.refusal('not_authorized') and not t.host._seen


def test_live_scope_and_no_grant_leak():
    with setup() as t:
        raw=r.canonical(t.schemas());assert all(z.hex() not in raw for z in t.grants.values())
        assert len(t.schemas())==5 and all(not z['function']['parameters']['additionalProperties'] for z in t.schemas())
        assert t.host.revoke(S,t.grants['mel_hdc_query'])
        assert not t.dispatch(request('hdc.query'))['ok'] and not t.host._seen

@pytest.mark.parametrize('op',['kan.evaluate','vfa.evaluate'])
def test_zero_tolerance_refuses_numerical_payload(op):
    with setup(tol=0.) as t:
        out=t.dispatch(request(op));assert out==r.refusal('verification_refused'),out
        assert t.audit and len(t.host._seen)==1

@pytest.mark.parametrize('op',['hdc.query','kan.evaluate','vfa.evaluate'])
def test_fabricated_receipt_refused(op):
    with setup() as t:
        out=t.dispatch(request(op));assert out['ok'],out
        receipt=t.last_receipt;call=t.last_call
        with pytest.raises(ValueError):r.verified_feedback(S,call,replace(receipt,result_frame=b'fabricated'),(1e-5,),APP if op=='kan.evaluate' else None)
        with pytest.raises(ValueError):r.verified_feedback(replace(S,turn='other'),call,receipt,(1e-5,),APP if op=='kan.evaluate' else None)

@pytest.mark.parametrize('x',[True,0,1.,float('nan'),-1.,.1])
def test_bad_tolerance(x):
    with pytest.raises(ValueError):r.Allowed(('hdc.bind',),None,x)

@pytest.mark.parametrize('op',['hdc.query','kan.evaluate','vfa.evaluate'])
def test_hash_consistent_false_result_not_verified(op):
    # Recompute the digest after forging a structurally plausible result. A
    # matching digest is not proof of mathematical correctness.
    with setup() as t:
        assert t.dispatch(request(op))['ok']
        receipt=t.last_receipt;call=t.last_call
        if op=='vfa.evaluate':
            p=n.pb.VfaResult.FromString(receipt.result_frame)
            p.result.CopyFrom(n.result_object(op,call.function,call.points,[999.]).message())
        else:
            p=ep.EngineResult.FromString(receipt.result_frame)
            if op=='hdc.query':p.query.hamming_distance[0]=2
            else:p.kan.values[1]=999.
        raw=n.serialize(p);fake=replace(receipt,result_frame=raw,result_sha256=hashlib.sha256(raw).hexdigest())
        if op=='hdc.query':
            with pytest.raises(ValueError):r.verified_feedback(S,call,fake,())
        else:
            out,_=r.verified_feedback(S,call,fake,(1e-5,),APP if op=='kan.evaluate' else None)
            assert out==r.refusal('verification_refused')


def test_grammar_is_live_projection_not_fixed_answer():
    from tools.mel06a.schema_grammar import request_grammar
    with setup() as t:
        g=request_grammar(t.schemas())
        assert all(name in g for name in r.NAMES.values())
        assert '0.5' not in g and '101101' not in g and 'refuse' in g
    with setup(('hdc.bind',)) as t:
        g=request_grammar(t.schemas());assert 'mel_hdc_bind' in g and 'mel_kan_evaluate' not in g
    with pytest.raises(ValueError):request_grammar([])


def test_outward_float_display():
    from fractions import Fraction as F
    b=r.u.Interval(F(1,3),F(2,3));shown=r.interval_wire(b)
    assert F(shown['lower'])<=b.lo and F(shown['upper'])>=b.hi

@pytest.mark.parametrize('lo,hi,target,expect',[(0,1,0,'above'),(0,1,1,'uncertain'),(0,1,2,'below'),(1,1,1,'above')])
def test_threshold_display_rule(lo,hi,target,expect):assert r.bound_decision({'lower':lo,'upper':hi},target)==expect

@pytest.mark.parametrize('op',['hdc.query','kan.evaluate','vfa.evaluate'])
def test_verified_answer_guard(op):
    with setup() as t:
        args={"points":[[.5]]} if op=="kan.evaluate" else ARG[op]
        raw=json.dumps({"tool":r.NAMES[op],"arguments":args});assert r.intent_matches(raw,op,args);out=t.dispatch(raw);assert out['ok']
        threshold=1.5 if op!='hdc.query' else None
        value=r.expected_answer(out,op,threshold)
        assert r.publish_checked(json.dumps({'answer':value}),out,matched_intent=True,operation=op,threshold=threshold)=={'ok':True,'answer':value}
        assert not r.publish_checked(json.dumps({'answer':value}),out,matched_intent=False,operation=op,threshold=threshold)['ok']
        assert not r.publish_checked('{"answer":"invented"}',out,matched_intent=True,operation=op,threshold=threshold)['ok']
        assert not r.publish_checked(json.dumps({'answer':value,'receipt':'made up'}),out,matched_intent=True,operation=op,threshold=threshold)['ok']
        assert not r.publish_checked(json.dumps({'answer':value}),r.refusal('unverified'),matched_intent=True,operation=op,threshold=threshold)['ok']
