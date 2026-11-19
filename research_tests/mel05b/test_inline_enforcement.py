"""Real authorized worker and no-successor controls for inline MEL-05B-R1."""
from dataclasses import replace
import pytest
from cognitum.runtime import Runtime
from cognitum.mel import cooperation as g, native as n, engines as e, engines_pb2 as ep
from cognitum.mel import verified_graph as vg, uncertainty as u, exchange as x
from research_tests.mel04b.test_cooperation import S, fixture_plan, setup
from research_tests.mel05b.test_graph_acceptance import TOL


def _assert_stopped(h,t,guarded,seen,unused,status='verification_refused'):
    assert guarded.status==status and guarded.outcome is None and guarded.witness is None
    assert {rid for scope,rid in h._seen}==set(seen)
    assert guarded.reserved_calls==len(seen)
    assert all(h._grants[dict(t)[i]].calls_left==1 for i in unused)


def _tail_plan(id='tail', domain_gate=False):
    f=n.gaussian([[0.]],[[1.]],[-1.],constant=1.,axes=[('x','1')],domain=[(-2000.,2000.)],output_unit='1')
    nodes=(g.Seed('seed',n.points(f,[[1000.]])),g.Vfa('value','seed',f))
    if domain_gate:
        downstream=n.gaussian([],[],[],constant=2.,axes=[('value','1')],domain=[(1.,2.)],output_unit='1')
        nodes+=(g.Vfa('next','value',downstream),)
        tol=(('value',(1e-12,)),('next',(1e-12,)))
    else:
        nodes+=(g.Threshold('bits','value',1.,'1'),g.Query('query','bits',('bits',)))
        tol=(('value',(1e-12,)),)
    return g.Plan(id,S,nodes,g.Budget(step_ms=5000)),tol


def test_ambiguous_threshold_never_materializes_or_dispatches(monkeypatch):
    p,tol=_tail_plan();h,t=setup(p)
    monkeypatch.setattr(x,'threshold',lambda *v,**kw:pytest.fail('ambiguous bits materialized'))
    try:
        guarded=vg.execute_verified(h,p,t,tol)
        _assert_stopped(h,t,guarded,['tail:value'],['query'])
    finally:h.close()


def test_propagated_domain_crossing_blocks_next_numerical_dispatch():
    p,tol=_tail_plan('domain',True);h,t=setup(p)
    try:
        guarded=vg.execute_verified(h,p,t,tol)
        _assert_stopped(h,t,guarded,['domain:value'],['next'])
    finally:h.close()


def test_genuine_worker_kan_wrong_value_denied_before_vfa(monkeypatch):
    p=fixture_plan('forged');h,t=setup(p);original=Runtime.call
    def corrupt(*args,**kwargs):
        response=original(*args,**kwargs)
        if response.operation!='kan.evaluate':return response
        assert response.execution_status=='completed'
        raw=n.decode_carrier(response.result['frame'],e.MAX_RESULT)
        result=ep.EngineResult.FromString(raw);result.kan.values[0]=float(result.kan.values[0])+.25
        return replace(response,result={'frame':n.encode_carrier(n.serialize(result),e.MAX_RESULT)})
    monkeypatch.setattr(Runtime,'call',corrupt)
    try:
        guarded=vg.execute_verified(h,p,t,TOL)
        _assert_stopped(h,t,guarded,['forged:kan'],['vfa','base','query'])
    finally:h.close()


def test_knot_domain_crossing_in_kan_stops_before_call():
    p,_=_tail_plan('kan-domain',True);last=p.nodes[-1]
    from cognitum.mel import model_engines as m
    layer=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[1.,1.5,2.],coefficients=[1.,0.,0.],mask=[1.])
    approval=m.Approval(m.Checkpoint(m.checkpoint_wire([layer])),'review')
    p=replace(p,nodes=p.nodes[:-1]+(g.Kan(last.id,last.parent,approval,('value',),('out',)),))
    tol=(('value',(1e-12,)),('next',(1e-6,)))
    h,t=setup(p)
    try:
        guarded=vg.execute_verified(h,p,t,tol)
        _assert_stopped(h,t,guarded,['kan-domain:value'],['next'])
    finally:h.close()


@pytest.mark.parametrize('tol',[(),(('kan',(1e-6,)),),TOL+(TOL[0],),TOL[:1]+(('vfa',(1e-6,1e-6)),)+TOL[2:],TOL[:1]+(('vfa',(float('nan'),)),)+TOL[2:],TOL[:1]+(('vfa',(True,)),)+TOL[2:]])
def test_bad_policy_refuses_before_any_worker(tol):
    p=fixture_plan();h,t=setup(p)
    try:
        with pytest.raises(ValueError):vg.execute_verified(h,p,t,tol)
        assert not h._seen and all(gr.calls_left==1 for gr in h._grants.values())
    finally:h.close()


@pytest.mark.parametrize('kind',['work','bytes'])
def test_verification_reservation_blocks_worker_before_dispatch(kind,monkeypatch):
    p,tol=_tail_plan('budget');p=replace(p,budget=replace(p.budget,**({kind:1000} if kind=='work' else {kind:100000})))
    h,t=setup(p)
    monkeypatch.setattr(Runtime,'call',lambda *v,**kw:pytest.fail('unreserved worker'))
    try:
        guarded=vg.execute_verified(h,p,t,tol)
        _assert_stopped(h,t,guarded,[],['value','query'],'resource_denied')
        assert guarded.charged_work<=p.budget.work and guarded.reserved_bytes<=p.budget.bytes
    finally:h.close()


def test_guard_budget_charged_beyond_unverified_execution():
    p=fixture_plan('account');h,t=setup(p)
    try:
        raw=g.execute(h,p,t);assert raw.status=='completed'
    finally:h.close()
    h,t=setup(p)
    try:
        verified=vg.execute_verified(h,p,t,TOL);assert verified.status=='verified'
        assert verified.charged_work>raw.charged_work and verified.reserved_bytes>raw.reserved_bytes
        assert verified.reserved_calls==raw.reserved_calls==4
        assert verified.charged_work<=p.budget.work and verified.reserved_bytes<=p.budget.bytes
        assert len(verified.witness)<=verified.reserved_bytes
        assert vg.replay(p,verified.outcome,TOL,verified.witness)
        with pytest.raises(ValueError):vg.replay(p,verified.outcome,(('kan',(1e-5,)),)+TOL[1:],verified.witness)
    finally:h.close()


def test_cancellation_during_independent_numeric_verification(monkeypatch):
    p,tol=_tail_plan('cancel');h,t=setup(p);control=g.Cancellation();original=u.vfa_bounds
    def cancel(*args,**kwargs):
        assert control.cancel()
        return original(*args,**kwargs)
    monkeypatch.setattr(u,'vfa_bounds',cancel)
    try:
        guarded=vg.execute_verified(h,p,t,tol,cancellation=control)
        _assert_stopped(h,t,guarded,['cancel:value'],['query'],'cancelled')
        assert not control.cancel()
    finally:h.close()


def test_deadline_during_independent_numeric_verification(monkeypatch):
    p,tol=_tail_plan('timeout');h,t=setup(p);clock=[0];original=u.vfa_bounds
    monkeypatch.setattr(g,'monotonic_ns',lambda:clock[0])
    def expired(*args,**kwargs):
        clock[0]=p.budget.time_ms*1000000
        return original(*args,**kwargs)
    monkeypatch.setattr(u,'vfa_bounds',expired)
    try:
        guarded=vg.execute_verified(h,p,t,tol)
        _assert_stopped(h,t,guarded,['timeout:value'],['query'],'timed_out')
    finally:h.close()


def test_precancel_prevents_verifier_and_worker(monkeypatch):
    p,tol=_tail_plan('pre-cancel');h,t=setup(p);control=g.Cancellation();assert control.cancel()
    monkeypatch.setattr(vg._Verifier,'reserve',lambda *v,**kw:pytest.fail('cancelled verification'))
    try:
        guarded=vg.execute_verified(h,p,t,tol,cancellation=control)
        _assert_stopped(h,t,guarded,[],['value','query'],'cancelled')
    finally:h.close()


def test_revoked_kan_grant_prevents_independent_numeric_evaluation(monkeypatch):
    p=fixture_plan('revoked');h,t=setup(p);h.revoke(S,dict(t)['kan'])
    monkeypatch.setattr(u,'kan_bounds',lambda *v,**kw:pytest.fail('unauthorized numerical evaluation'))
    try:
        guarded=vg.execute_verified(h,p,t,TOL)
        _assert_stopped(h,t,guarded,[],['kan','vfa','base','query'],'denied')
    finally:h.close()


def test_contradicted_threshold_refuses_even_tolerated_worker_error(monkeypatch):
    from cognitum.mel import model_engines as m
    f=n.gaussian([],[],[],constant=0.,axes=[('x','1')],domain=[(-1.,1.)],output_unit='1')
    layer=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,grid=[-1.,0.,1.],coefficients=[0.,0.,0.],mask=[0.],bias=[.49])
    app=m.Approval(m.Checkpoint(m.checkpoint_wire([layer])),'review')
    p=g.Plan('contradicted',S,(g.Seed('seed',n.points(f,[[0.]])),g.Kan('kan','seed',app,('x',),('value',)),g.Threshold('bits','kan',.5,'1'),g.Query('query','bits',('bits',))),g.Budget(step_ms=10000))
    from cognitum.mel.engine_limits import KanLimits, HdcLimits
    h,t=setup(p,limits={'kan':KanLimits(timeout_ms=10000),'query':HdcLimits(timeout_ms=10000)});original=Runtime.call
    def corrupt(*args,**kwargs):
        response=original(*args,**kwargs)
        assert response.operation=='kan.evaluate' and response.execution_status=='completed'
        result=ep.EngineResult.FromString(n.decode_carrier(response.result['frame'],e.MAX_RESULT));result.kan.values[0]=.51
        return replace(response,result={'frame':n.encode_carrier(n.serialize(result),e.MAX_RESULT)})
    monkeypatch.setattr(Runtime,'call',corrupt)
    monkeypatch.setattr(x,'threshold',lambda *v,**kw:pytest.fail('contradicted bits materialized'))
    try:
        guarded=vg.execute_verified(h,p,t,(('kan',(.1,)),))
        _assert_stopped(h,t,guarded,['contradicted:kan'],['query'])
    finally:h.close()


def test_cancellation_at_witness_finalization_suppresses_result(monkeypatch):
    p,_=_tail_plan('finish');p=replace(p,nodes=p.nodes[:2]);h,t=setup(p);control=g.Cancellation();original=vg._Verifier.finish
    def cancel(self):
        wire=original(self);assert control.cancel();return wire
    monkeypatch.setattr(vg._Verifier,'finish',cancel)
    try:
        guarded=vg.execute_verified(h,p,t,(('value',(1e-12,)),),cancellation=control)
        _assert_stopped(h,t,guarded,['finish:value'],[],'cancelled')
    finally:h.close()
