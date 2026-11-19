from dataclasses import replace
import json
import pytest
from cognitum.mel import intent_reference as ir, model_reference as r, admission as a
from tools.mel06a.experiment import APP, HDC, KAN, VFA, T
from tools.mel06a.benchmark_r1 import CASES, answer_grammar

S=a.Scope('ref','w','u','turn')
POL=r.Allowed(r.OPS,APP)
def raw(op,args):return r.canonical({'tool':r.NAMES[op],'arguments':args})
def intent(op='hdc.query',args=HDC,threshold=None,component=0):return ir.Intent(S,op,r.canonical(args),threshold,APP.checkpoint.identity if op=='kan.evaluate' else None,component)
def final(x):return r.canonical({'answer':x})

@pytest.mark.parametrize('case',CASES,ids=[x.id for x in CASES])
def test_actual_intent_and_publication(case):
    i=intent(case.op,case.args,case.threshold)
    with ir.BoundTurn(i,POL) as b:
        out=b.dispatch(raw(case.op,case.args));assert out['ok'],out
        assert b.worker_calls==1 and b.audit['operation']==case.op
        result=b.publish(final(case.answer));assert result['ok'] and result['source']=='model_verified',result
        assert result['answer']==case.answer and result['intent_sha256']==i.identity and result['result_sha256']==b.audit['result_sha256'] and result['evidence_sha256']==out['evidence_sha256']
        assert not b.publish(final(case.answer))['ok']

@pytest.mark.parametrize('bad',[{'points':[[True]]},{'points':[[.5000000000000001]]},{'points':[[.5],[.5]]},{'points':[.5]},{'points':[[.5]],'checkpoint':'x'}, {'points':[[0.]]}],ids=['bool','rounded','extra-row','ragged','checkpoint','wrong-point'])
def test_wrong_args_no_worker(bad):
    i=intent('kan.evaluate',KAN,1.5)
    with ir.BoundTurn(i,POL) as b:
        assert b.dispatch(raw('kan.evaluate',bad))==r.refusal('intent_mismatch') and b.worker_calls==0
        assert b.dispatch(raw('kan.evaluate',KAN))==r.refusal('turn_attempt_limit')
        assert not b.publish(final('above'),host_fallback=True)['ok']

@pytest.mark.parametrize('bad',[{'probe':HDC['probe'],'candidates':HDC['candidates'][::-1]}, {'probe':'101100','candidates':HDC['candidates']}, {'probe':HDC['probe'],'candidates':HDC['candidates']+['000111']}])
def test_wrong_hdc_intent(bad):
    with ir.BoundTurn(intent(),POL) as b:assert not b.dispatch(raw('hdc.query',bad))['ok'] and b.worker_calls==0

def test_reordered_json_numeric_equivalence():
    i=intent('kan.evaluate',{'points':[[1]]},1.5)
    assert i.matches('{"arguments":{"points":[[1.0]]},"tool":"mel_kan_evaluate"}')
    assert not i.matches('{"arguments":{"points":[[true]]},"tool":"mel_kan_evaluate"}')

@pytest.mark.parametrize('bad',[True,1,float('inf'),float('nan'),None])
def test_threshold_profile(bad):
    with pytest.raises(ValueError):intent('kan.evaluate',KAN,bad)

@pytest.mark.parametrize('what',['checkpoint','scope','threshold','component','arguments','operation'])
def test_identity_binds_fields(what):
    i=intent('kan.evaluate',KAN,1.5)
    if what=='checkpoint':j=replace(i,checkpoint='0'*64)
    elif what=='scope':j=replace(i,scope=replace(S,turn='other'))
    elif what=='threshold':j=replace(i,threshold=1.6)
    elif what=='component':j=replace(i,component=1)
    elif what=='arguments':j=replace(i,arguments=r.canonical({'points':[[.25]]}))
    else:j=intent('vfa.evaluate',VFA,1.5)
    assert j.identity!=i.identity

def test_checkpoint_and_allowlist_refusal():
    with pytest.raises(ValueError):ir.BoundTurn(replace(intent('kan.evaluate',KAN,1.5),checkpoint='0'*64),POL)
    with pytest.raises(ValueError):ir.BoundTurn(intent(),r.Allowed(('hdc.bind',)))

@pytest.mark.parametrize('mutate',['feedback','audit','raw_receipt','intent','close','revoke','checkpoint'])
def test_retained_evidence_or_revocation(mutate):
    i=intent('kan.evaluate',KAN,1.5)
    with ir.BoundTurn(i,POL) as b:
        out=b.dispatch(raw(i.operation,KAN));assert out['ok']
        if mutate=='feedback':out['projection']['lower_ge_threshold']=False;out['projection']['interval']['lower']=-100
        elif mutate=='audit':b.audit['result_sha256']='0'*64 # display copy, not trusted
        elif mutate=='raw_receipt':b.turn.last_receipt=replace(b.turn.last_receipt,result_sha256='0'*64)
        elif mutate=='intent':b.intent=replace(i,threshold=2.)
        elif mutate=='close':b.close()
        elif mutate=='revoke':b.turn.host.revoke(S,b.turn.grants[r.NAMES[i.operation]])
        else:b.turn.host.revoke_checkpoint(S,APP.checkpoint.identity)
        p=b.publish(final('above'),host_fallback=True)
        assert bool(p['ok'])==(mutate in ('feedback','audit')),p
        if p['ok']:assert p['answer']=='above'

@pytest.mark.parametrize('bad',['{"answer":"above"}','{"answer":"uncertain","receipt":"fake"}','{"answer":"uncertain","answer":"uncertain"}','x'*8193,''])
def test_ambiguous_host_fallback_is_explicit(bad):
    i=intent('vfa.evaluate',VFA,T)
    with ir.BoundTurn(i,POL) as b:
        assert b.dispatch(raw(i.operation,VFA))['ok'];p=b.publish(bad,host_fallback=True)
        assert p['ok'] and p['source']=='host_verified_fallback' and p['answer']=='uncertain'

@pytest.mark.parametrize('bad',['{"answer":[0]}','{"answer":[0,1],"receipt":"made up"}','{"answer":[true,1]}','{"answer":[1,0]}'])
def test_never_publish_wrong_model_answer(bad):
    with ir.BoundTurn(intent(),POL) as b:
        assert b.dispatch(raw('hdc.query',HDC))['ok'];assert not b.publish(bad)['ok']

@pytest.mark.parametrize('case',CASES,ids=[x.id for x in CASES])
def test_wrong_route_or_forged_schema(case):
    i=intent(case.op,case.args,case.threshold)
    with ir.BoundTurn(i,POL) as b:
        assert not b.dispatch('{"tool":"shell_exec","arguments":{"command":"echo 1"}}')['ok'] and b.worker_calls==0


def test_invalid_component_fails_closed():
    i=intent('vfa.evaluate',VFA,1.5,component=1)
    with pytest.raises(ValueError,match='component absent'):ir.BoundTurn(i,POL)


def test_no_gold_answer_encoded_in_grammars():
    assert '[01]{1,1024}' in answer_grammar('hdc.bind') and '11011010' not in answer_grammar('hdc.bind')
    assert '"above" | "below" | "uncertain"' in answer_grammar('kan.evaluate')
    assert '[0-7]' in answer_grammar('hdc.query') and '[0,1]' not in answer_grammar('hdc.query')


def test_signed_zero_drift_never_dispatches():
    with ir.BoundTurn(intent('kan.evaluate',{'points':[[0.]]},1.5),POL) as b:
        # On this canonical Protobuf profile negative zero has a different wire.
        assert b._wire(b._bind(r.canonical({'points':[[-0.]]})))!=b._expected_wire
        assert b.dispatch(raw('kan.evaluate',{'points':[[-0.]]}))==r.refusal('intent_mismatch') and b.worker_calls==0


def test_publication_before_dispatch_is_terminal():
    with ir.BoundTurn(intent(),POL) as b:
        assert b.publish(final([0,1]))==r.refusal('no_verified_result')
        assert b.dispatch(raw('hdc.query',HDC))==r.refusal('turn_attempt_limit') and b.worker_calls==0


def test_multi_component_vfa_gradient():
    i=intent('vfa.gradient',dict(VFA,points=[[0.],[.5]]),-.5,component=1)
    with ir.BoundTurn(i,POL) as b:
        out=b.dispatch(raw(i.operation,dict(VFA,points=[[0.],[.5]])))
        assert out['ok'] and out['projection']['component']==1
        assert b.publish(final('below'))['ok']


def test_two_simultaneous_dispatches_only_one_execution():
    from concurrent.futures import ThreadPoolExecutor
    with ir.BoundTurn(intent(),POL) as b, ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(b.dispatch,[raw('hdc.query',HDC)]*2))
        assert sum(v['ok'] for v in outcomes)==1 and b.worker_calls==1
        assert b.publish(final([0,1]))['ok']
