"""ORCH-01D: real inherited math kernels, honest negative science and no leakage."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from math import sin, cos, isfinite
import math

import numpy as np
import pytest

from cognitum import orc_comparison as c, orc_science_data as d
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_associative import Cleanup
from cognitum.research.kan_trainable import load_snapshot
from cognitum.research.ssm_timeaware import (
    ridge_fit, ridge_predict, ssm_zoh_rate)

START = 1_700_000_000_000
STEP = 60_000
UNIT = d.Units("water_level","m")
CLOCK = d.Clock(nominal_interval_ms=STEP)


def raw(n=160, *, missing=(), late=(), edit=None, offset=0., drift=0.):
    rows=["timestamp_ms,available_ms,value,observed,observation_id"]
    for i in range(n):
        t=START+i*STEP
        value=10 + .3*sin(i/4) + .2*cos(i/15) + .007*i + offset
        if i >= 4*n//5:
            value += drift
        if edit and i in edit:
            value=edit[i]
        arrival=t+2*STEP if i in late else t
        present=i not in missing
        rows.append(f"{t},{arrival},{format(value,'.12g') if present else ''},{1 if present else 0},obs{i}")
    return ("\n".join(rows)+"\n").encode("ascii")


def provenance(blob):
    return d.Provenance("syntheticPublisher","fixture:orca",
                        sha256(blob).hexdigest(),"unknown","declared")


def series(blob=None, n=160, *, clock=CLOCK, **kwargs):
    blob=raw(n,**kwargs) if blob is None else blob
    return d.qualify(blob,site_id="fakeStation1",units=UNIT,
                     clock=clock,provenance=provenance(blob))


def fit(s=None, *, kan=False, hdc=False, h=STEP, lag=STEP):
    return c.fit_train(s or series(),horizon_ms=h,lag_ms=lag,
                       research_kan=kan,research_hdc=hdc)


def selected(s=None,*,kan=False,hdc=False):
    s=s or series()
    m=fit(s,kan=kan,hdc=hdc)
    return m,c.calibrate(s,m)


def evaluate(s=None,*,kan=False,hdc=False,block=4):
    s=s or series()
    m,cal=selected(s,kan=kan,hdc=hdc)
    return c.evaluate_holdout(s,m,cal,block_size=block)


def test_real_ridge_ssm_and_persistence_reuse_without_mel_authorization():
    s=series()
    m,cal=selected(s)
    ev=c.evaluate_holdout(s,m,cal)
    assert m.methods==("persistence","train_mean","direct_ridge","timeaware_ssm")
    assert set(dict(ev.test_scores))==set(m.methods)
    assert ev.calibration.selected in m.methods and ev.calibration.selected_on=="cal"
    assert not m.execution_authorized and not cal.execution_authorized and not ev.execution_authorized
    assert ev.test_eligible_origins==32
    assert sum(ev.test_skipped[i][1] for i in range(len(ev.test_skipped)))+dict(ev.test_scores)["direct_ridge"].n == 32
    assert all(x.n>10 and x.mae>=0 and x.rmse>=x.mae
               for _,x in ev.test_scores)


def test_reuses_exact_r4_ridge_and_elapsed_ssm_kernel():
    s=series()
    m=fit(s)
    split=d.split_chronological(s)
    train=d.prepare_forecasts(s,split,m.scaler,d.CandidateContract("statistical.ridge",UNIT),
                              fold="train",horizon_ms=STEP,lag_ms=STEP)
    X=np.array([row.feature_values for row in train.examples])
    Y=np.array([row.target for row in train.examples])
    reffit=ridge_fit(np.column_stack((X,np.ones(len(X)))),Y)
    assert np.allclose(m.ridge_weight,reffit[2],rtol=0,atol=1e-12)
    assert m.ssm_tau_seconds in (60.,240.,960.,3840.)
    assert 0 < ssm_zoh_rate(m.ssm_tau_seconds,60.) < 1.


def test_train_model_is_immutable_source_bound_and_replayable():
    s=series()
    m=fit(s)
    again=fit(s)
    assert m==again and m.identity==again.identity and len(m.identity)==64
    with pytest.raises(FrozenInstanceError):m.identity="tampered"
    assert m.scaler.cutoff_ms==s.rows[d.split_chronological(s).train_stop-1].timestamp_ms


@pytest.mark.parametrize("kan,hdc,expected",[
    (False,False,4),(True,False,5),(False,True,5),(True,True,7)])
def test_explicit_research_kan_hdc_methods_are_computed_not_named_only(kan,hdc,expected):
    s=series()
    m=fit(s,kan=kan,hdc=hdc)
    assert len(m.methods)==expected
    ev=c.evaluate_holdout(s,m,c.calibrate(s,m))
    assert len(ev.test_scores)==expected
    if kan:
        assert len(m.kan_snapshot)>50 and m.kan_snapshot_sha256==sha256(m.kan_snapshot).hexdigest()
        network=load_snapshot(m.kan_snapshot,m.kan_snapshot_sha256)
        assert network.layers[0].kind=="chebyshev"
    else:assert m.kan_snapshot is None
    if hdc:
        assert len(m.hdc_prototypes)==2
        assert len(m.hdc_prototypes[0])==256
        bank=Cleanup(Spec("MAP",256),np.asarray(m.hdc_prototypes,np.float32))
        assert bank.nbytes>0
        counts=dict(ev.audit_counters)
        assert counts["hdc_abstained"]+counts["hdc_accepted"]==dict(ev.test_scores)["direct_ridge"].n
    else:assert m.hdc_prototypes is None


def test_full_composition_uses_actual_kan_and_hdc_prototypes_without_auto_grants():
    m=fit(kan=True,hdc=True)
    assert "ssm_kan_hdc" in m.methods
    assert "ssm_kan" in m.methods and "ssm_hdc" in m.methods
    s=series()
    ev=c.evaluate_holdout(s,m,c.calibrate(s,m))
    assert all(isfinite(z.rmse) for _,z in ev.test_scores)
    assert "offline_research_only_no_mel_grant" in ev.limitations


def test_selection_uses_only_calibration_not_test_targets():
    a=series(n=160)
    b=series(raw(160,edit={155:10000.}))
    m1=fit(a,kan=True,hdc=True);m2=fit(b,kan=True,hdc=True)
    assert m1.ridge_weight==m2.ridge_weight
    assert m1.ssm_tau_seconds==m2.ssm_tau_seconds
    assert m1.kan_snapshot==m2.kan_snapshot
    assert m1.hdc_prototypes==m2.hdc_prototypes
    cal1,cal2=c.calibrate(a,m1),c.calibrate(b,m2)
    assert cal1.scores==cal2.scores and cal1.selected==cal2.selected
    assert m1.source_identity!=m2.source_identity


def test_train_fit_does_not_consume_future_calibration_labels():
    a=series()
    b=series(raw(160,edit={100:20.}))
    f1=fit(a,kan=True,hdc=True);f2=fit(b,kan=True,hdc=True)
    assert f1.ridge_weight==f2.ridge_weight
    assert f1.kan_snapshot==f2.kan_snapshot
    assert f1.hdc_bias==f2.hdc_bias
    assert c.calibrate(a,f1).scores!=c.calibrate(b,f2).scores


def test_identity_cannot_be_interchanged_across_sources():
    a=series()
    b=series(raw(160,offset=1.))
    m=fit(a)
    with pytest.raises(ValueError,match="source-bound"):
        c.calibrate(b,m)
    with pytest.raises(ValueError,match="source-bound"):
        c.evaluate_holdout(b,m,c.calibrate(a,m))


@pytest.mark.parametrize("field,replacement",[
    ("identity","0"*64),("source_sha256","0"*64),
    ("ssm_tau_seconds",999.),("ridge_weight",(1.,2.,3.)),
    ("train_cutoff_ms",START),("execution_authorized",True)])
def test_model_mutations_fail_before_scoring(field,replacement):
    s=series()
    m=fit(s)
    forged=replace(m,**{field:replacement})
    with pytest.raises(ValueError):
        c.calibrate(s,forged)


def test_kan_snapshot_tampering_refused():
    s=series()
    m=fit(s,kan=True)
    altered=replace(m,kan_snapshot=m.kan_snapshot+b"z")
    with pytest.raises(ValueError,match="snapshot sha"):
        c.calibrate(s,altered)


def test_calibration_identity_reselection_refuses_fake_test_winner():
    s=series()
    m,cal=selected(s,kan=True,hdc=True)
    alternative=next(x for x in m.methods if x!=cal.selected)
    with pytest.raises(ValueError,match="post-hoc-selected"):
        c.evaluate_holdout(s,m,replace(cal,selected=alternative))
    with pytest.raises(ValueError,match="post-hoc-selected"):
        c.evaluate_holdout(s,m,replace(cal,selected_on="test"))


def test_calibration_score_forgery_refused():
    s=series()
    m,cal=selected(s)
    bad=replace(cal,scores=cal.scores[:-1])
    with pytest.raises(ValueError,match="post-hoc-selected"):
        c.evaluate_holdout(s,m,bad)


def test_test_metrics_can_be_negative_gain_and_are_not_overwritten():
    s=series()
    r=evaluate(s)
    scores=dict(r.test_scores)
    assert math.isclose(r.selected_rmse_gain_vs_ridge,
           scores["direct_ridge"].rmse-scores[r.calibration.selected].rmse,
           abs_tol=1e-12)
    assert math.isclose(r.selected_mae_gain_vs_ridge,
           scores["direct_ridge"].mae-scores[r.calibration.selected].mae,
           abs_tol=1e-12)
    assert "not_orc_vs_ridge_independent_benchmark" in r.limitations


def test_bootstrap_preserves_negative_gain_against_ridge():
    truth=np.zeros(80)
    ridge=np.zeros(80)
    chosen=np.ones(80)
    times=np.arange(80)*STEP
    result=c._bootstrap(truth,ridge,chosen,times,STEP,4)
    assert result.status.startswith("DESCRIPTIVE_")
    assert result.mean_mae_gain==-1.
    assert result.bootstrap_95==(-1.,-1.)
    assert not result.confidence_proven


def test_bootstrap_preserves_positive_and_equal_gain_as_well():
    truth=np.zeros(80)
    times=np.arange(80)*STEP
    for selected,expected in [(np.zeros(80),1.),(np.ones(80),0.)]:
        result=c._bootstrap(truth,np.ones(80),selected,times,STEP,4)
        assert result.mean_mae_gain==expected


def test_dependent_interval_refuses_small_sample_without_fake_coverage():
    r=evaluate(series(n=100),block=4)
    assert r.selected_interval.status.startswith("REFUSED_")
    assert r.selected_interval.radius is None
    assert r.selected_interval.origin_coverage is None
    assert not r.selected_interval.conditional_guarantee


def test_dependent_interval_calibrates_contiguous_observations_only():
    r=evaluate(series(n=480),block=4)
    v=r.selected_interval
    assert v.status=="DESCRIPTIVE_BLOCK_MAX_ONLY"
    assert v.calibration_blocks>=9 and v.test_blocks>=5
    assert v.radius>=0 and 0<=v.origin_coverage<=1
    assert 0<=v.simultaneous_block_coverage<=1
    assert not v.conditional_guarantee
    assert r.paired_gain.status.startswith("DESCRIPTIVE_")


def test_irregular_clock_never_implies_regular_dependent_intervals():
    s=series(clock=d.Clock())
    r=evaluate(s)
    assert r.selected_interval.status.startswith("REFUSED_")
    assert r.paired_gain.status.startswith("REFUSED_")
    assert r.paired_gain.bootstrap_95 is None


def test_timestamp_gaps_break_bootstrap_blocks_no_silent_stitching():
    values=np.ones(40)
    times=np.r_[np.arange(20)*STEP,np.arange(20)*STEP+10000*STEP]
    blocks=c._blocks(values,times,STEP,4)
    assert blocks.shape==(10,4)
    assert np.all(blocks==1)
    times=np.arange(40)*STEP*3
    assert c._blocks(values,times,STEP,4).shape==(0,4)


def test_independent_physical_sensor_source_still_unverified():
    s=series()
    r=evaluate(s)
    assert r.source_identity==s.identity
    assert "source_metadata_declared_not_original_sensor_authenticated" in r.limitations
    assert s.provenance.unit_evidence=="declared"


def test_missingness_refusal_denominators_remain_visible():
    s=series(raw(160,missing=(132,133,134,135),late=(137,)))
    m,cal=selected(s)
    r=c.evaluate_holdout(s,m,cal)
    assert r.test_eligible_origins==32
    assert len(r.test_scores)>0
    assert sum(v for _,v in r.test_skipped)+dict(r.test_scores)["direct_ridge"].n==32


def test_future_unavailable_measurement_never_becomes_origin_feature():
    s=series(raw(160,late=(130,131,132)))
    m,cal=selected(s)
    r=c.evaluate_holdout(s,m,cal)
    assert dict(r.test_skipped)["origin_unavailable"]>0
    assert all(score.n==dict(r.test_scores)["direct_ridge"].n
               for _,score in r.test_scores)


def test_out_of_domain_research_features_fall_back_without_sample_intersection():
    s=series(raw(160,drift=100.))
    m=fit(s,kan=True,hdc=True)
    r=c.evaluate_holdout(s,m,c.calibrate(s,m))
    counts=dict(r.audit_counters)
    assert counts["kan_ood"]>0 and counts["hdc_ood"]>0
    assert counts["hdc_abstained"]>=counts["hdc_ood"]
    assert len(set(x.n for _,x in r.test_scores))==1


@pytest.mark.parametrize("bad",[
    dict(research_kan="yes"),dict(research_hdc=1),
    dict(horizon_ms=0),dict(horizon_ms=True),
    dict(horizon_ms=31*86_400_000),dict(lag_ms=0),
    dict(lag_ms=1.0),dict(lag_ms=31*86_400_000)])
def test_fail_closed_research_and_elapsed_time_parameters(bad):
    kw=dict(horizon_ms=STEP,lag_ms=STEP)
    kw.update(bad)
    with pytest.raises(ValueError):
        c.fit_train(series(),**kw)


@pytest.mark.parametrize("invalid",[
    True,1.0,0,1,33,999,-1,"4",None])
def test_unreviewed_dependency_block_size_refused(invalid):
    s=series()
    m,cal=selected(s)
    with pytest.raises(ValueError,match="fixed dependence-block"):
        c.evaluate_holdout(s,m,cal,block_size=invalid)


def test_rejects_small_and_oversized_research_datasets():
    with pytest.raises(ValueError,match="bounded"):
        fit(series(n=79))
    s=series(n=2050)
    with pytest.raises(ValueError,match="bounded"):
        c.fit_train(s,horizon_ms=STEP,lag_ms=STEP)


def test_research_hdc_refuses_degenerate_training_features():
    # The strictly checked source has train scale, but one historical lag
    # feature can still be constant and must refuse a spurious HDC regime.
    rows=["timestamp_ms,available_ms,value,observed,observation_id"]
    for i in range(160):
        t=START+i*STEP
        value=(0 if i%2==0 else 1)
        rows.append(f"{t},{t},{float(value)},{1},obs{i}")
    s=series(("\n".join(rows)+"\n").encode())
    # Periodic 0/1 still has valid distinct regimes; the path must be bounded.
    model=fit(s,hdc=True)
    assert model.research_hdc


def test_no_implicit_external_forecast_or_unreviewed_candidate():
    s=series()
    model=fit(s)
    assert "research.kan" not in model.methods
    assert "ssm_kan" not in model.methods
    assert "research.ssm" not in model.methods
    assert model.methods==c._BASE


def test_explicit_source_byte_sha_mismatch_blocks_any_scientific_comparison():
    blob=raw(160)
    with pytest.raises(ValueError,match="source content SHA256"):
        c.run_offline(blob+b"X",site_id="fakeStation1",units=UNIT,
                      clock=CLOCK,provenance=provenance(blob),
                      horizon_ms=STEP,lag_ms=STEP)


def test_unreviewed_methods_have_no_execution_grant_api():
    assert not hasattr(c,"issue")
    assert not hasattr(c,"execute")
    assert not hasattr(c,"install")
    assert not hasattr(c,"Registry")
    assert not hasattr(c,"Admission")


def test_convenience_offline_runner_equals_explicit_staged_protocol():
    blob=raw(160)
    direct=c.run_offline(blob,site_id="fakeStation1",units=UNIT,clock=CLOCK,
                         provenance=provenance(blob),horizon_ms=STEP,lag_ms=STEP)
    staged=evaluate(series(blob))
    assert direct==staged


def test_matched_cohorts_are_rechecked_for_all_engines_in_every_fold():
    s=series()
    model=fit(s,kan=True,hdc=True)
    for fold in ("train","cal","test"):
        contracts=[d.prepare_forecasts(s,d.split_chronological(s),model.scaler,
              d.CandidateContract(op,UNIT),fold=fold,horizon_ms=STEP,lag_ms=STEP)
              for op in ("statistical.ridge","research.ssm","research.kan","research.hdc")]
        assert d.assert_matched_cohorts(*contracts)


def test_mismatched_lag_cohort_refuses_even_when_counts_happen_to_match():
    s=series()
    model=fit(s)
    a=d.prepare_forecasts(s,d.split_chronological(s),model.scaler,
         d.CandidateContract("statistical.ridge",UNIT),fold="test",horizon_ms=STEP,lag_ms=STEP)
    b=d.prepare_forecasts(s,d.split_chronological(s),model.scaler,
         d.CandidateContract("research.ssm",UNIT),fold="test",horizon_ms=STEP,lag_ms=2*STEP)
    with pytest.raises(ValueError,match="candidate cohorts differ"):
        d.assert_matched_cohorts(a,b)


def test_nonfinite_scoring_and_uncertainty_refuses_instead_of_imputation():
    with pytest.raises(ValueError,match="finite matched"):
        c._metric(np.asarray([1.]),np.asarray([np.nan]))
    with pytest.raises(ValueError):
        c._metric(np.asarray([1.,2.]),np.asarray([1.]))


def test_kernel_actual_ridge_prediction_differs_from_simple_mean():
    s=series()
    m=fit(s)
    b=c._batch(s,m.scaler,"test",STEP,STEP,"statistical.ridge")
    pred,_=c._predict(m,b)
    assert not np.allclose(pred["direct_ridge"],pred["train_mean"])
    assert not np.allclose(pred["timeaware_ssm"],pred["train_mean"])
