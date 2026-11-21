"""ORCH-01E: conservative frozen-calibration routing, budgets and refusal."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from math import cos, sin
import math

import pytest

from cognitum import orc_selection as choose, orc_science_data as d
from cognitum import orc_comparison as comparison
from cognitum.cooperative import SourceStamp
from cognitum.cooperative_cpu import wire, sha
from cognitum.orc_graph import ScientificTask
from cognitum.proto import specialists_pb2 as math_pb

START=1_700_000_000_000
STEP=60_000
UNIT=d.Units("water_level","m")
CLOCK=d.Clock(nominal_interval_ms=STEP)
BUILD="a"*40


def raw(n=160, *, changed=None, missing=(), delayed=(), shifted_test=0.):
    lines=["timestamp_ms,available_ms,value,observed,observation_id"]
    changed = changed or {}
    for i in range(n):
        t=START+i*STEP
        value=10 + .3*sin(i/4) + .2*cos(i/15)+.007*i
        if i in changed:value=changed[i]
        if i>=4*n//5:value+=shifted_test
        available=t+2*STEP if i in delayed else t
        observed=i not in missing
        lines.append(f"{t},{available},{format(value,'.12g') if observed else ''},"
                     f"{1 if observed else 0},obs{i}")
    return ("\n".join(lines)+"\n").encode("ascii")


def provenance(blob, *, unit="declared", rights="unknown"):
    return d.Provenance("syntheticPublisher","synthetic:selector01e",
                        sha256(blob).hexdigest(),rights,unit)


def research(blob=None,*,n=160,kan=False,hdc=False,**kwargs):
    blob=raw(n,**kwargs) if blob is None else blob
    p=provenance(blob)
    series=d.qualify(blob,site_id="fixtureStation",
                     units=UNIT,clock=CLOCK,provenance=p)
    model=comparison.fit_train(series,horizon_ms=STEP,lag_ms=STEP,
                               research_kan=kan,research_hdc=hdc)
    cal=comparison.calibrate(series,model)
    return blob,p,series,model,cal


def recommend(*,blob=None,metadata=None,model=None,cal=None,
              policy=None,override=None,source_current=None,n=160,kan=False,
              hdc=False,**kwargs):
    if model is None:
        blob,metadata,_,model,cal=research(blob=blob,n=n,kan=kan,hdc=hdc,**kwargs)
    return choose.propose_forecast(
        blob,site_id="fixtureStation",units=UNIT,clock=CLOCK,
        provenance=metadata,source_current=source_current if source_current is not None
        else lambda s:True,
        model=model,calibration=cal,policy=policy or choose.SelectionPolicy(),
        override=override)


def test_default_selector_is_frozen_inert_and_uses_calibration_only():
    blob,meta,series,m,cal=research()
    p=recommend(blob=blob,metadata=meta,model=m,cal=cal)
    assert p.status=="PROPOSED_OFFLINE"
    assert p.selected in m.methods
    assert p.calibration_cohort_sha256==cal.cohort_sha256
    assert p.calibration_n==cal.scores[0][1].n
    assert p.policy_sha256 and len(p.decision_sha256)==64
    assert not p.execution_authorized and not p.research_only
    assert "cost_figures_are_static_proxies_not_measured_time_or_ram" in p.reasons
    with pytest.raises(FrozenInstanceError):p.selected="forged"
    assert p==recommend(blob=blob,metadata=meta,model=m,cal=cal)


def test_selector_never_requests_test_fold_or_test_model_score(monkeypatch):
    blob,meta,_,m,cal=research()
    original=d.prepare_forecasts
    def refuse_test(*args,**kw):
        if kw.get("fold")=="test":
            raise AssertionError("test fold consulted during selection")
        return original(*args,**kw)
    monkeypatch.setattr(d,"prepare_forecasts",refuse_test)
    p=recommend(blob=blob,metadata=meta,model=m,cal=cal)
    assert p.status=="PROPOSED_OFFLINE"


def test_train_and_calibration_remain_independent_of_heldout_changes():
    a,pa,_,ma,ca=research()
    b,pb,_,mb,cb=research(raw(160,shifted_test=15.))
    x=recommend(blob=a,metadata=pa,model=ma,cal=ca)
    y=recommend(blob=b,metadata=pb,model=mb,cal=cb)
    assert ma.ridge_weight==mb.ridge_weight
    assert ca.scores==cb.scores
    assert x.selected==y.selected and x.selection_basis==y.selection_basis
    assert x.source_identity!=y.source_identity
    assert x.decision_sha256!=y.decision_sha256


def test_calibration_altered_method_winner_refused_before_holdout():
    blob,p,_,m,cal=research()
    alt=next(x for x in m.methods if x!=cal.selected)
    with pytest.raises(ValueError,match="post-hoc calibration"):
        recommend(blob=blob,metadata=p,model=m,cal=replace(cal,selected=alt))
    with pytest.raises(ValueError,match="post-hoc calibration"):
        recommend(blob=blob,metadata=p,model=m,cal=replace(cal,selected_on="test"))


def test_fake_calibration_heldout_accuracy_refused():
    blob,p,_,m,cal=research()
    forged=replace(cal,scores=cal.scores[:-1])
    with pytest.raises(ValueError):
        recommend(blob=blob,metadata=p,model=m,cal=forged)


@pytest.mark.parametrize("modifications",[
    {"identity":"0"*64},{"source_sha256":"0"*64},
    {"ssm_tau_seconds":123.456},{"execution_authorized":True},
])
def test_tampered_fitted_model_never_generates_proposal(modifications):
    blob,p,_,m,cal=research()
    with pytest.raises(ValueError):
        recommend(blob=blob,metadata=p,model=replace(m,**modifications),cal=cal)


def test_source_bytes_change_or_stale_host_refuses_before_proposal():
    blob,p,_,m,cal=research()
    with pytest.raises(ValueError,match="SHA256 mismatch"):
        recommend(blob=blob+b"\n",metadata=p,model=m,cal=cal)
    with pytest.raises(ValueError,match="stale scientific"):
        recommend(blob=blob,metadata=p,model=m,cal=cal,source_current=lambda _:False)


def test_declared_units_and_unreported_rights_can_be_required_by_host():
    blob,p,_,m,cal=research()
    policy=choose.SelectionPolicy(require_documented_units=True,
                                  require_reported_rights=True)
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal,policy=policy)
    assert decision.status=="ABSTAIN" and decision.selected is None
    assert "documented_units_unavailable" in decision.reasons
    assert "publisher_reported_rights_unavailable" in decision.reasons


def test_conservative_baseline_survives_research_without_opt_in():
    b,p,_,m,cal=research(n=480,kan=True,hdc=True)
    d1=recommend(blob=b,metadata=p,model=m,cal=cal)
    assert d1.selected not in ("ssm_kan","ssm_hdc","ssm_kan_hdc")
    cards={x.method:x for x in d1.candidates}
    for name in ("ssm_kan","ssm_hdc","ssm_kan_hdc"):
        assert not cards[name].eligible
        assert "research_candidate_not_opted_in" in cards[name].reasons
        assert cards[name].research_only


def test_approved_research_opt_in_only_generates_inert_proposal():
    b,p,_,m,cal=research(n=480,kan=True,hdc=True)
    policy=choose.SelectionPolicy(allow_research_proposals=True,
                                  max_research_abstention_fraction=1.)
    cards=recommend(blob=b,metadata=p,model=m,cal=cal,policy=policy).candidates
    eligible=[v.method for v in cards if v.eligible and v.research_only]
    assert eligible
    override=choose.UserOverride(eligible[0],"operator-a","experimental analysis")
    selected=recommend(blob=b,metadata=p,model=m,cal=cal,
                       policy=policy,override=override)
    assert selected.selected==eligible[0]
    assert selected.research_only and not selected.execution_authorized
    assert "research_candidate_not_admitted_into_mel" in selected.reasons
    assert "operator_intent_not_authenticated_or_authorized" in selected.reasons


def test_user_override_can_choose_a_weaker_reviewed_baseline_without_auth():
    blob,p,_,m,cal=research()
    override=choose.UserOverride("train_mean","operator-one","compare baseline")
    proposal=recommend(blob=blob,metadata=p,model=m,cal=cal,override=override)
    assert proposal.selected=="train_mean"
    assert proposal.selection_basis=="unverified_operator_requested_proposal"
    assert proposal.override==override
    assert not proposal.execution_authorized
    assert proposal.decision_sha256 != recommend(blob=blob,metadata=p,model=m,cal=cal).decision_sha256


def test_operator_cannot_override_resource_refusal():
    blob,p,_,m,cal=research()
    policy=choose.SelectionPolicy(max_evaluation_work_proxy=50)
    with pytest.raises(ValueError,match="override refused"):
        recommend(blob=blob,metadata=p,model=m,cal=cal,policy=policy,
                  override=choose.UserOverride("direct_ridge","operator","budget bypass"))


def test_very_low_budget_abstains_with_no_execution_grants():
    blob,p,_,m,cal=research()
    proposal=recommend(blob=blob,metadata=p,model=m,cal=cal,
                       policy=choose.SelectionPolicy(max_evaluation_work_proxy=1))
    assert proposal.status=="ABSTAIN" and proposal.selected is None
    assert "no_conservative_baseline_within_budget" in proposal.reasons


def test_ridge_resource_limit_triggers_conventional_fallback():
    blob,p,_,m,cal=research()
    policy=choose.SelectionPolicy(max_evaluation_work_proxy=100)
    proposal=recommend(blob=blob,metadata=p,model=m,cal=cal,policy=policy)
    assert proposal.selected=="persistence"
    assert proposal.selection_basis=="resource_bounded_fallback"
    assert "ridge_resource_proxy_refused" in proposal.reasons


def test_model_memory_budget_excludes_research_snapshots():
    blob,p,_,m,cal=research(n=480,kan=True,hdc=True)
    policy=choose.SelectionPolicy(max_model_memory_proxy_bytes=100,
                                  allow_research_proposals=True,
                                  max_research_abstention_fraction=1.)
    proposal=recommend(blob=blob,metadata=p,model=m,cal=cal,policy=policy)
    for card in proposal.candidates:
        if card.method in ("ssm_kan","ssm_hdc","ssm_kan_hdc"):
            assert "model_memory_proxy_exceeded" in card.reasons
    assert proposal.selected not in ("ssm_kan","ssm_hdc","ssm_kan_hdc")


def test_no_calibration_data_policy_abstains_not_fake_positive_gain():
    blob,p,_,m,cal=research()
    result=recommend(blob=blob,metadata=p,model=m,cal=cal,
                     policy=choose.SelectionPolicy(min_calibration_examples=120))
    assert result.status=="ABSTAIN" and result.selected is None
    assert "insufficient_calibration_examples" in result.reasons


def test_missing_data_fraction_policy_abstains_with_visible_denominator():
    b,p,_,m,cal=research(missing=tuple(range(100,108)))
    dec=recommend(blob=b,metadata=p,model=m,cal=cal,
                  policy=choose.SelectionPolicy(max_calibration_skipped_fraction=.1))
    assert dec.status=="ABSTAIN"
    assert "excessive_calibration_missing_or_unavailable" in dec.reasons
    assert dec.calibration_skipped>0 and dec.calibration_n>0


@pytest.mark.parametrize("bad",[
    {"max_evaluation_work_proxy":0},
    {"max_model_memory_proxy_bytes":-1},
    {"min_calibration_examples":9},
    {"minimum_research_contiguous_blocks":8},
    {"min_relative_mae_improvement":float("nan")},
    {"min_absolute_mae_improvement":float("-inf")},
    {"max_research_abstention_fraction":1.1},
    {"max_calibration_skipped_fraction":True},
    {"allow_research_proposals":"yes"},
    {"require_documented_units":1},
    {"require_reported_rights":"approved"},
])
def test_invalid_policy_refused_at_definition(bad):
    with pytest.raises(ValueError):
        choose.SelectionPolicy(**bad)


@pytest.mark.parametrize("method,actor,reason",[
    ("not_a_method","operator","reason"),
    ("direct_ridge","", "reason"),
    ("direct_ridge","operator",""),
])
def test_unknown_or_unattributed_operator_requests_refused(method,actor,reason):
    with pytest.raises(ValueError):
        choose.UserOverride(method,actor,reason)


def test_selected_holdout_report_uses_preapproved_choice_and_signed_gain():
    blob,p,_,m,cal=research()
    forced=choose.UserOverride("train_mean","operator-a","show bad model")
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal,override=forced)
    metric=choose.evaluate_frozen_proposal(
        decision,blob,site_id="fixtureStation",units=UNIT,clock=CLOCK,
        provenance=p,source_current=lambda s:True,
        model=m,calibration=cal,policy=choose.SelectionPolicy())
    assert metric.method=="train_mean" and metric.n>0
    assert metric.decision_sha256==decision.decision_sha256
    assert math.isclose(metric.signed_mae_gain_vs_ridge,
                        metric.ridge_mae-metric.selected_mae,abs_tol=1e-12)
    assert math.isclose(metric.signed_rmse_gain_vs_ridge,
                        metric.ridge_rmse-metric.selected_rmse,abs_tol=1e-12)
    assert not metric.independent_physical_benchmark and not metric.execution_authorized


def test_test_evaluation_refuses_tampered_frozen_decision():
    blob,p,_,m,cal=research()
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal)
    for bad in (replace(decision,decision_sha256="0"*64),
                replace(decision,selected="train_mean"),
                replace(decision,execution_authorized=True)):
        with pytest.raises(ValueError,match="tampered"):
            choose.evaluate_frozen_proposal(
                bad,blob,site_id="fixtureStation",units=UNIT,clock=CLOCK,
                provenance=p,source_current=lambda _:True,
                model=m,calibration=cal,policy=choose.SelectionPolicy())


def test_heldout_mutation_changes_actual_metric_but_not_selection():
    first,pa,_,ma,ca=research()
    second,pb,_,mb,cb=research(raw(160,shifted_test=25.))
    a=recommend(blob=first,metadata=pa,model=ma,cal=ca)
    b=recommend(blob=second,metadata=pb,model=mb,cal=cb)
    assert a.selected==b.selected
    def audit(decision,blob,p,m,cal):
        return choose.evaluate_frozen_proposal(decision,blob,
            site_id="fixtureStation",units=UNIT,clock=CLOCK,provenance=p,
            source_current=lambda _:True,model=m,calibration=cal,
            policy=choose.SelectionPolicy())
    x,y=audit(a,first,pa,ma,ca),audit(b,second,pb,mb,cb)
    assert x.selected_rmse!=y.selected_rmse


def test_abstained_decision_cannot_be_evaluated():
    blob,p,_,m,cal=research()
    pol=choose.SelectionPolicy(min_calibration_examples=120)
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal,policy=pol)
    with pytest.raises(ValueError,match="tampered"):
        choose.evaluate_frozen_proposal(decision,blob,
            site_id="fixtureStation",units=UNIT,clock=CLOCK,
            provenance=p,source_current=lambda _:True,model=m,
            calibration=cal,policy=pol)


def test_independent_source_current_rechecked_at_audit():
    blob,p,_,m,cal=research()
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal)
    with pytest.raises(ValueError,match="stale"):
        choose.evaluate_frozen_proposal(decision,blob,
            site_id="fixtureStation",units=UNIT,clock=CLOCK,
            provenance=p,source_current=lambda _:False,model=m,
            calibration=cal,policy=choose.SelectionPolicy())


def test_override_is_not_cryptographic_host_authentication():
    override=choose.UserOverride("direct_ridge","claimed-human","I want ridge")
    assert not hasattr(override,"approval_token")
    assert not hasattr(override,"issuer_signature")
    blob,p,_,m,cal=research()
    result=recommend(blob=blob,metadata=p,model=m,cal=cal,override=override)
    assert not result.execution_authorized
    assert "operator_intent_not_authenticated_or_authorized" in result.reasons


def test_exact_deterministic_route_reuses_original_cooperative_compiler():
    q=math_pb.LinearRequest(action="solve")
    q.a.add(entries=["2"]);q.b.add(entries=["6"])
    frame=wire(q)
    task=ScientificTask("exact_linear",(frame,),
                        (SourceStamp("source","r1",sha(frame)),))
    proposal=choose.route_exact(task,plan_id="orc",workspace_id="workspace",
        subject_id="user",build_sha=BUILD)
    assert proposal.route_names==("math.linear",)
    assert proposal.plan.steps[0].operation=="math.linear"
    assert not proposal.execution_authorized


@pytest.mark.parametrize("goal",["research.hdc","statistical.ridge","research.ssm",
                                  "research.kan","not_a_goal"])
def test_deterministic_route_refuses_unreviewed_goals(goal):
    with pytest.raises(ValueError,match="unreviewed scientific goal"):
        ScientificTask(goal,(),())


def test_offline_router_has_no_new_grants_or_native_worker():
    assert not hasattr(choose,"execute")
    assert not hasattr(choose,"issue")
    assert not hasattr(choose,"Registry")
    assert not hasattr(choose,"Runtime")
    assert not hasattr(choose,"approve_checkpoint")


def test_selection_policy_does_not_claim_measured_latency_or_memory():
    blob,p,_,m,cal=research()
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal)
    assert all(x.evaluation_work_proxy==x.calibration_n*choose._STEPS[x.method]
               for x in decision.candidates)
    assert all(x.model_memory_proxy_bytes>0 for x in decision.candidates)
    assert "cost_figures_are_static_proxies_not_measured_time_or_ram" in decision.reasons


def test_scientific_selection_not_same_as_user_ai_synergy_test():
    blob,p,_,m,cal=research()
    decision=recommend(blob=blob,metadata=p,model=m,cal=cal)
    assert decision.status=="PROPOSED_OFFLINE"
    assert "no_independent_site_or_physical_accuracy_claim" in decision.reasons
    assert not hasattr(decision,"user_benefit_gain")
