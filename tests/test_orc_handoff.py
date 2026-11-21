"""ORCH-01C: actual authorized graph handoffs, independent verification, refusal.

These are synthetic numeric source fixtures with declared (not authenticated)
metadata. They do not demonstrate learned forecasting gains or sensor custody.
"""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import pytest

from cognitum import cooperative as cpu
from cognitum.cooperative_cpu import CooperativeCpu
from cognitum.contracts import HostContext
from cognitum.mel import admission as a, cooperation as g, native as n
from cognitum.mel import engines as e, engines_pb2 as ep
from cognitum.mel import model_engines as m, verified_graph as vg
from cognitum.mel.engine_limits import KanLimits
from cognitum.orc_handoff import Handoff, compile_kalman, compile_mel, check_source_current, execute_bound_mel
from cognitum.orc_science_data import Units, Clock, Provenance, CandidateContract
from cognitum.registry import Registry
from cognitum.runtime import Runtime
from cognitum.temporal_statespace import TemporalModel
from cognitum.proto import temporal_practical_pb2 as temporal

START = 1_700_000_000_000
STEP = 60_000
BUILD = "a"*40
S = a.Scope("science","workspace","owner","turn")
CTX = HostContext("workspace","owner")
UNITS = Units("water_level","m")
CLOCK = Clock(nominal_interval_ms=STEP)


def raw_source(*, nrows=40, missing=(), delayed=(), shift=0.):
    lines=["timestamp_ms,available_ms,value,observed,observation_id"]
    for i in range(nrows):
        t=START+i*STEP
        availability=t+(STEP*4 if i in delayed else 0)
        value="" if i in missing else str(float(i%7)+i/10.+(shift if i==37 else 0.))
        lines.append(f"{t},{availability},{value},{0 if i in missing else 1},obs{i}")
    return ("\n".join(lines)+"\n").encode("ascii")


def provenance(raw):
    return Provenance("publisherX","source:station1/fixture",
                      sha256(raw).hexdigest(), "unknown", "declared")


def vfa_function():
    return n.gaussian([[0.,0.]],[[1.,1.]],[1.],constant=0.,
                      axes=[("current_z","1"),("lag_z","1")],
                      domain=[(-10.,10.),(-10.,10.)],output_unit="1")


def approval():
    layer=ep.KanLayer(inputs=2,outputs=1,knots=3,basis=ep.RBF,
                      grid=[-10.,0.,10.,-10.,0.,10.],
                      coefficients=[0.,1.,0.,0.,1.,0.],mask=[1.,1.])
    ck=m.Checkpoint(m.checkpoint_wire([layer]))
    return m.Approval(ck,"reviewedFixture")


def mel_plan(*, operation="vfa.evaluate", raw=None, function=None,
             approved=None, fold="test", units=UNITS,
             scope=S, budget=None, **kwargs):
    raw=raw if raw is not None else raw_source()
    return compile_mel(raw,site_id="station1",units=units,clock=CLOCK,
                       provenance=provenance(raw),scope=scope,
                       operation=operation,fold=fold,
                       horizon_ms=kwargs.pop("horizon_ms",STEP),
                       lag_ms=kwargs.pop("lag_ms",STEP),
                       function=(vfa_function() if function is None and
                                 operation=="vfa.evaluate" else function),
                       approval=approved,
                       budget=budget if budget is not None else g.Budget(step_ms=5000),
                       **kwargs)


def cpu_plan(*, raw=None, model=None, build=BUILD, **kwargs):
    raw=raw if raw is not None else raw_source()
    model=model if model is not None else TemporalModel(
        "local_level",0.01,0.1,1.,3.,STEP)
    return compile_kalman(
        raw,site_id="station1",units=UNITS,clock=CLOCK,
        provenance=provenance(raw),workspace_id="workspace",
        subject_id="owner",build_sha=build,horizon_ms=STEP,
        model=model,**kwargs)


def host_vfa(*, install=True):
    reg=Registry()
    if install:
        manifest=reg.install(n.NativeVFAPlugin,enabled=True)
        for operation in n.OP:
            reg.nominate(operation,manifest.name)
    h=a.Admission(Runtime(reg),S.session)
    route=next(q for q in a.routes() if q.operation=="vfa.evaluate")
    return h,route


def host_kan(*, approval_present=True):
    reg=Registry()
    manifest=reg.install(e.EnginePlugin,enabled=True)
    for op in e.OPERATIONS:reg.nominate(op,manifest.name)
    h=a.Admission(Runtime(reg),S.session,
                  enable_engines=True,enable_model_codecs=True)
    selected=approval()
    if approval_present:
        h.approve_checkpoint(S,selected.checkpoint.wire,
                             expected_sha256=selected.checkpoint.identity,
                             review_id=selected.review_id)
    route=next(q for q in a.routes(include_engines=True)
               if q.operation=="kan.evaluate")
    return h,route,selected


def issued_vfa():
    h,route=host_vfa()
    token=h.issue(S,route,a.Limits(timeout_ms=5000),ttl_ms=60000)
    return h,(("evaluate",token),)


def issued_kan():
    h,route,selected=host_kan()
    token=h.issue(S,route,KanLimits(timeout_ms=5000),ttl_ms=60000,
                  model_codec=True,checkpoint_sha256=selected.checkpoint.identity)
    return h,(("evaluate",token),),selected


def runtime_cpu():
    reg=Registry();manifest=reg.install(CooperativeCpu,enabled=True)
    for op in manifest.operations:reg.nominate(op.slot,manifest.name)
    return Runtime(reg)


def run_cpu(handoff, **kwargs):
    return cpu.execute(runtime_cpu(),handoff.plan,CTX,expected_build_sha=BUILD,
                       admit=kwargs.pop("admit",lambda claim,ctx: True),
                       source_current=kwargs.pop("source_current",
                                                lambda stamp,ctx: True),
                       cancelled=kwargs.pop("cancelled",lambda: False),
                       **kwargs)


def test_candidate_contract_recognizes_reviewed_mel_without_permission():
    for name in ("vfa.evaluate","kan.evaluate"):
        c=CandidateContract(name,UNITS)
        assert c.operation==name
    with pytest.raises(ValueError,match="unknown mathematical"):
        CandidateContract("kan.training",UNITS)


def test_native_vfa_handoff_verified_from_real_source_and_worker():
    r=raw_source()
    p=mel_plan(raw=r)
    assert type(p) is Handoff and p.operation=="vfa.evaluate"
    assert not p.execution_authorized and p.source_sha256==sha256(r).hexdigest()
    assert len(p.origin_target_keys)==7
    assert p.plan_sha256==p.plan.identity
    assert check_source_current(p,r,site_id="station1",units=UNITS,
          clock=CLOCK,provenance=provenance(r),
          source_current=lambda handoff,series: True)
    h,tokens=issued_vfa()
    result=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.00001,)),))
    assert result.status=="verified",result
    assert result.outcome is not None and result.witness is not None
    assert [x.node_id for x in result.outcome.nodes]==["seed","evaluate"]
    assert vg.replay(p.plan,result.outcome,(("evaluate",(0.00001,)),),
                     result.witness)
    assert check_source_current(p,r,site_id="station1",units=UNITS,
          clock=CLOCK,provenance=provenance(r),
          source_current=lambda handoff,series: True)


def test_actual_kan_checkpoint_handoff_runs_with_host_grant():
    h,tokens,selected=issued_kan()
    p=mel_plan(operation="kan.evaluate",approved=selected,
               max_binary32_error=1e-5)
    assert p.plan.nodes[-1].approval.checkpoint.identity==selected.checkpoint.identity
    assert p.conversion_kind=="binary32_explicit" and 0 < p.max_quantization_error < 1e-5
    out=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.001,)),))
    assert out.status=="verified",out
    assert out.outcome.plan_sha256==p.plan.identity
    assert out.outcome.nodes[-1].operation=="kan.evaluate"


def test_classical_kalman_handoff_real_existing_cooperative_runtime():
    p=cpu_plan()
    assert p.operation=="temporal.kalman"
    assert not p.execution_authorized and p.plan_sha256==cpu.plan_digest(p.plan)
    claim=[]
    out=run_cpu(p,admit=lambda c,ctx: claim.append(c.phase) or True)
    assert out.status=="completed",out
    assert out.receipts[0].assurance=="numerical_replay"
    m=temporal.FilterResult.FromString(out.receipts[0].frame)
    assert m.status=="OK" and m.observed_count==24
    assert claim==["plan","compute","verify","publish"]


def test_cpu_kalman_delayed_measurement_masked_not_imputed():
    p=cpu_plan(raw=raw_source(delayed=(23,)))
    request=temporal.FilterRequest.FromString(p.plan.steps[0].frame)
    assert request.samples[23].observed[0] is False
    assert request.samples[23].values[0]==0.
    out=run_cpu(p)
    assert out.status=="completed",out
    m=temporal.FilterResult.FromString(out.receipts[0].frame)
    assert m.missing_count>=1


def test_source_digest_and_metadata_changes_invalidate_handoff():
    r=raw_source()
    p=mel_plan(raw=r)
    other=raw_source(shift=1000.)
    with pytest.raises(ValueError):
        check_source_current(p,other,site_id="station1",units=UNITS,
              clock=CLOCK,provenance=provenance(other),
              source_current=lambda h,s: True)
    with pytest.raises(ValueError):
        check_source_current(p,r,site_id="station1",
              units=Units("temperature","K"),clock=CLOCK,
              provenance=provenance(r),source_current=lambda h,s: True)
    with pytest.raises(ValueError,match="no longer current"):
        check_source_current(p,r,site_id="station1",units=UNITS,
              clock=CLOCK,provenance=provenance(r),
              source_current=lambda h,s: False)


def test_tampered_plan_and_fake_authorization_refused_by_host_preflight():
    r=raw_source()
    p=mel_plan(raw=r)
    for bad in (replace(p,plan_sha256="0"*64),
                replace(p,execution_authorized=True)):
        with pytest.raises(ValueError):
            check_source_current(bad,r,site_id="station1",
                  units=UNITS,clock=CLOCK,provenance=provenance(r),
                  source_current=lambda h,s: True)
    with pytest.raises(FrozenInstanceError):
        p.source_sha256="changed"


def test_altered_fold_or_source_produces_distinct_mel_plan_identity():
    a=mel_plan(fold="test")
    b=mel_plan(fold="cal")
    c=mel_plan(raw=raw_source(shift=0.5))
    assert len({a.plan_sha256,b.plan_sha256,c.plan_sha256})==3
    assert a.cohort_sha256!=b.cohort_sha256


@pytest.mark.parametrize("operation",["research.ssm","research.hdc","statistical.ridge",
                                       "python.exec","kan.training"])
def test_unwired_engine_or_unsafe_route_refused(operation):
    with pytest.raises(ValueError,match="unreviewed MEL scientific handoff"):
        mel_plan(operation=operation)


@pytest.mark.parametrize("fold",["unknown","past","all"])
def test_unreviewed_science_fold_refused(fold):
    with pytest.raises(ValueError):
        mel_plan(fold=fold)


def test_rejects_missing_reviews_and_unapproved_checkpoint():
    with pytest.raises(ValueError,match="checkpoint required"):
        mel_plan(operation="kan.evaluate")
    h,route,selected=host_kan(approval_present=False)
    with pytest.raises(ValueError):
        h.issue(S,route,KanLimits(timeout_ms=5000),ttl_ms=60000,
                model_codec=True,checkpoint_sha256=selected.checkpoint.identity)


def test_kan_refuses_implicit_float32_conversion():
    with pytest.raises(ValueError,match="unapproved or excessive binary32"):
        mel_plan(operation="kan.evaluate",approved=approval())


def test_kan_refuses_insufficient_declared_error_budget():
    with pytest.raises(ValueError,match="unapproved or excessive binary32"):
        mel_plan(operation="kan.evaluate",approved=approval(),
                 max_binary32_error=1e-15)


def test_kan_rejects_unbounded_or_wrong_type_precision_authority():
    for value in (float("nan"),float("inf"),-1.,1.,True,"0.1"):
        with pytest.raises(ValueError,match="rounding budget"):
            mel_plan(operation="kan.evaluate",approved=approval(),
                     max_binary32_error=value)


def test_grants_cannot_be_substituted_across_routes():
    h,token=issued_vfa()
    p=mel_plan(operation="kan.evaluate",approved=approval(),
               max_binary32_error=1e-5)
    out=vg.execute_verified(h,p.plan,token,(("evaluate",(0.001,)),))
    assert out.status!="verified" and out.outcome is None and out.witness is None


def test_vfa_host_revocation_blocks_worker_and_publication():
    p=mel_plan()
    h,tokens=issued_vfa()
    assert h.revoke(S,tokens[0][1])
    out=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.00001,)),))
    assert out.status!="verified" and out.outcome is None and out.witness is None


def test_kan_checkpoint_revocation_blocks_worker():
    h,tokens,selected=issued_kan()
    p=mel_plan(operation="kan.evaluate",approved=selected,
               max_binary32_error=1e-5)
    assert h.revoke_checkpoint(S,selected.checkpoint.identity)
    out=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.001,)),))
    assert out.status!="verified" and out.outcome is None and out.witness is None


def test_mel_pre_cancel_suppresses_all_outputs():
    p=mel_plan()
    h,tokens=issued_vfa()
    stop=g.Cancellation();stop.cancel()
    out=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.00001,)),),
                            cancellation=stop)
    assert out.status=="cancelled" and out.outcome is None and out.witness is None


def test_session_close_blocks_mel_grants():
    p=mel_plan()
    h,tokens=issued_vfa();h.close()
    out=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.00001,)),))
    assert out.status!="verified" and out.outcome is None and out.witness is None


def test_forged_worker_output_fails_existing_independent_mel_verification(monkeypatch):
    p=mel_plan()
    h,tokens=issued_vfa()
    original=a.Admission.execute
    def tamper(self,*args,**kwargs):
        r=original(self,*args,**kwargs)
        if r.status=="completed":
            return replace(r,frame=b"\x00",
                           result_sha256=sha256(b"\x00").hexdigest())
        return r
    monkeypatch.setattr(a.Admission,"execute",tamper)
    out=vg.execute_verified(h,p.plan,tokens,(("evaluate",(0.00001,)),))
    assert out.status!="verified" and out.outcome is None and out.witness is None


def test_cpu_denied_scope_and_build_and_source_staleness():
    p=cpu_plan()
    assert cpu.execute(runtime_cpu(),p.plan,
           HostContext("other","owner"),expected_build_sha=BUILD,
           admit=lambda c,ctx:True,source_current=lambda s,ctx:True,
           cancelled=lambda:False).status=="denied"
    assert cpu.execute(runtime_cpu(),p.plan,CTX,
           expected_build_sha="b"*40,admit=lambda c,ctx:True,
           source_current=lambda s,ctx:True,cancelled=lambda:False).status=="denied"
    assert run_cpu(p,source_current=lambda s,ctx:False).status=="stale_source"


def test_cpu_cancellation_denied_admission_and_verify_phase_refusal():
    p=cpu_plan()
    assert run_cpu(p,cancelled=lambda:True).status=="cancelled"
    assert run_cpu(p,admit=lambda c,ctx:False).status=="denied"
    assert run_cpu(p,admit=lambda c,ctx:c.phase!="verify").status=="denied"


def test_cpu_tampered_worker_result_suppresses_publication(monkeypatch):
    p=cpu_plan()
    original = Runtime.call
    def forge(self,request,context):
        response = original(self,request,context)
        if (request.operation=="cooperative.temporal.kalman.verify" and
            response.execution_status=="completed"):
            response.result={"receipt":"0"*64,
                             "assurance":response.result["assurance"]}
        return response
    monkeypatch.setattr(Runtime,"call",forge)
    out=run_cpu(p)
    assert out.status=="verification_failed" and not out.receipts


def test_mel_input_scoping_and_feature_numeric_bounds():
    with pytest.raises(ValueError):
        mel_plan(scope="not scope")
    with pytest.raises(ValueError):
        mel_plan(function=n.gaussian([[0]],[[1]],[1],constant=0.,
                   axes=[("notcurrent","1")],domain=[(-10,10)],output_unit="1"))
    with pytest.raises(ValueError):
        mel_plan(budget="unbounded")
    with pytest.raises(ValueError):
        mel_plan(raw=raw_source(missing=tuple(range(32,40))),fold="test")


def test_kan_approval_shape_and_checkpoint_mismatch_refused():
    selected=approval()
    with pytest.raises(ValueError):
        mel_plan(operation="kan.evaluate",approved=selected,
                 function=vfa_function())
    bad=ep.KanLayer(inputs=1,outputs=1,knots=3,basis=ep.RBF,
                    grid=[-10.,0.,10.],coefficients=[0.,1.,0.],mask=[1.])
    ck=m.Checkpoint(m.checkpoint_wire([bad]))
    with pytest.raises(ValueError,match="two inputs"):
        mel_plan(operation="kan.evaluate",
                 approved=m.Approval(ck,"review"))


def test_source_handoff_does_not_create_extra_runtime_grants_or_workers():
    import cognitum.orc_handoff as api
    assert not hasattr(api,"execute")
    assert not hasattr(api,"issue")
    assert not hasattr(api,"Registry")
    assert not hasattr(api,"Runtime")
    h=mel_plan()
    assert h.plan.nodes[0].points.message().body.WhichOneof("representation")=="points"


def test_cpu_input_frame_source_revision_bound_to_exact_series_identity():
    raw=raw_source()
    plan=cpu_plan(raw=raw)
    assert plan.plan.steps[0].source.revision==plan.series_identity[:40]
    assert plan.plan.steps[0].source.frame_sha256==sha256(plan.plan.steps[0].frame).hexdigest()
    assert check_source_current(plan,raw,site_id="station1",units=UNITS,
        clock=CLOCK,provenance=provenance(raw),
        source_current=lambda handoff,series:True)


def test_cpu_unsupported_model_horizon_and_source_type_rejected():
    with pytest.raises(ValueError):
        cpu_plan(model=TemporalModel("local_level",0.01,0.1,1.,3.,1000))
    with pytest.raises(ValueError):
        cpu_plan(raw=raw_source(nrows=16),build="notsha")
    with pytest.raises(ValueError):
        compile_kalman(raw_source(),site_id="station1",units=UNITS,clock=CLOCK,
             provenance=provenance(raw_source()),workspace_id="workspace",
             subject_id="owner",build_sha=BUILD,horizon_ms=0,
             model=TemporalModel("local_level",0.01,0.1,1.,3.,STEP))


def guarded_execution(p,host,grants,*,source_current=None,raw=None,
                      tolerances=(("evaluate",(0.00001,)),),cancellation=None):
    raw=raw if raw is not None else raw_source()
    return execute_bound_mel(host,p,grants,tolerances,raw=raw,
             site_id="station1",units=UNITS,clock=CLOCK,
             provenance=provenance(raw),
             source_current=source_current if source_current is not None
             else lambda handoff,series:True,cancellation=cancellation)


def test_bound_host_gate_permits_fresh_vfa_after_source_recheck():
    p=mel_plan()
    h,tokens=issued_vfa()
    seen=[]
    def fresh(handoff,series):
        seen.append((handoff.plan_sha256,series.identity))
        return True
    out=guarded_execution(p,h,tokens,source_current=fresh)
    assert out.status=="verified" and out.witness is not None
    assert len(seen)==2 and seen[0]==seen[1]


def test_bound_host_preflight_staleness_never_dispatches():
    p=mel_plan()
    h,tokens=issued_vfa()
    out=guarded_execution(p,h,tokens,
         source_current=lambda handoff,series:False)
    assert out.status=="stale_source" and out.outcome is None and out.witness is None
    assert len(h._seen)==0 and h._grants[tokens[0][1]].calls_left==1


def test_bound_host_postflight_staleness_discards_verified_result():
    p=mel_plan()
    h,tokens=issued_vfa()
    observed=[]
    def expiry(handoff,series):
        observed.append(series.identity)
        return len(observed)==1
    out=guarded_execution(p,h,tokens,source_current=expiry)
    assert out.status=="stale_source" and out.outcome is None and out.witness is None
    assert out.reserved_calls==1 and len(observed)==2
    assert h._grants[tokens[0][1]].calls_left==0


def test_bound_host_rejects_substituted_source_before_grant():
    p=mel_plan()
    h,tokens=issued_vfa()
    out=guarded_execution(p,h,tokens,raw=raw_source(shift=0.5))
    assert out.status=="stale_source" and out.outcome is None
    assert len(h._seen)==0


def test_bound_host_respects_original_mel_revocation_and_cancel():
    p=mel_plan()
    h,tokens=issued_vfa()
    assert h.revoke(S,tokens[0][1])
    out=guarded_execution(p,h,tokens)
    assert out.status!="verified" and out.outcome is None and out.witness is None
    h,tokens=issued_vfa()
    stop=g.Cancellation();stop.cancel()
    out=guarded_execution(p,h,tokens,cancellation=stop)
    assert out.status=="cancelled" and out.outcome is None and out.witness is None


def test_bound_host_kan_verified_guard_only_with_checkpoint_approval():
    h,tokens,selected=issued_kan()
    p=mel_plan(operation="kan.evaluate",approved=selected,
               max_binary32_error=1e-5)
    out=guarded_execution(p,h,tokens,tolerances=(("evaluate",(0.001,)),))
    assert out.status=="verified" and out.outcome is not None
    assert p.conversion_kind=="binary32_explicit"


def test_bound_host_refuses_tampered_handoff_and_wrong_target():
    p=mel_plan()
    h,tokens=issued_vfa()
    out=guarded_execution(replace(p,plan_sha256="0"*64),h,tokens)
    assert out.status=="stale_source" and out.outcome is None
    with pytest.raises(ValueError):
        guarded_execution(cpu_plan(),h,tokens)
