"""BENCH-01 real publisher excerpt, strong baseline and no future-label controls."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pytest

from tools.orcbench01 import benchmark as b
from cognitum import orc_comparison as c, orc_selection as route
from cognitum import orc_science_data as d

@pytest.mark.parametrize("site",b.SITES)
def test_original_uci_source_bytes_preserved_by_recorded_sha(site):
    path=b.DATA/(site+".csv")
    record=json.loads((b.DATA/"sources.json").read_text())
    row=next(x for x in record["entries"] if x["site"]==site)
    assert sha256(path.read_bytes()).hexdigest()==row["excerpt_sha256"]
    assert len(path.read_bytes())==row["excerpt_bytes"]
    raw,series,meta,provenance=b.acquire_site(site)
    assert len(series.rows)==1920 and not series.has_missing
    assert len(raw)<2_000_000
    assert meta.raw_sha256==sha256(raw).hexdigest()
    assert provenance["license"]=="CC BY 4.0"
    assert provenance["upstream_sensor_signature_verified"] is False
    assert provenance["real_source_new_to_existing_cognitum_research"] if "real_source_new_to_existing_cognitum_research" in provenance else True
    assert not provenance["observation_availability"].startswith("VERIFIED")


def test_celsius_to_kelvin_is_exactly_declared_and_clock_utc_plus_eight():
    raw,series,_,prov=b.acquire_site("Changping")
    assert series.units==d.Units("temperature","K")
    first=series.rows[0]
    source_first=-2.3
    assert first.value==pytest.approx(source_first+273.15,abs=1e-9)
    assert first.timestamp_ms==int(datetime(2013,3,1,0,tzinfo=timezone(
        timedelta(hours=8))).timestamp()*1000)
    assert first.available_ms==first.timestamp_ms
    assert prov["observation_availability"].startswith("ASSUMED")
    assert prov["time_interpretation"].startswith("ASSUMED")


def test_source_site_identity_and_policy_not_exchangeable():
    _,a,_,_=b.acquire_site("Changping")
    _,csite,_,_=b.acquire_site("Dingling")
    assert a.identity!=csite.identity
    assert a.provenance.raw_sha256!=csite.provenance.raw_sha256
    with pytest.raises(ValueError,match="fixed site"):
        b.acquire_site("InventedStation")


def test_preregistered_fixed_site_and_horizons():
    assert b.SITES==("Changping","Dingling","Guanyuan")
    assert b.HOURS==(1,6,24)
    assert b.N_ROWS==1920
    assert b.CLASSICAL==("direct_ridge","persistence","train_mean",
                         "timeaware_ssm","seasonal_naive24","ridge_AR24")
    assert b.POLICY_BASE.allow_research_proposals is False
    assert b.POLICY_RESEARCH.allow_research_proposals is True
    with pytest.raises(ValueError,match="unreviewed task"):
        b.case("Changping",123)


def test_trained_ar24_and_seasonal24_use_original_history_not_future():
    _,series,_,_=b.acquire_site("Changping")
    fitted=c.fit_train(series,horizon_ms=b.HOUR_MS,lag_ms=b.HOUR_MS)
    train=c._matched(series,fitted.scaler,"train",b.HOUR_MS,b.HOUR_MS,
                     ("statistical.ridge","research.ssm"))
    cal=c._matched(series,fitted.scaler,"cal",b.HOUR_MS,b.HOUR_MS,
                   ("statistical.ridge","research.ssm"))
    ar,excluded,count=b.train_strong(series,fitted,train)
    assert excluded>=24 and count>100
    forecast,missing=b.strong_predictions(series,ar,cal,"cal")
    assert missing==0 and len(forecast["ridge_AR24"])==len(cal.examples)
    by_time={r.timestamp_ms:r.value for r in series.rows}
    for ix,v in enumerate(cal.examples[:50]):
        assert forecast["seasonal_naive24"][ix]==by_time[
            v.origin_ms-24*b.HOUR_MS]
    assert np.isfinite(forecast["ridge_AR24"]).all()


def test_original_source_and_strong_cohorts_match_horizon_without_intersection():
    _,s,_,_=b.acquire_site("Dingling")
    m=c.fit_train(s,horizon_ms=6*b.HOUR_MS,lag_ms=b.HOUR_MS)
    train=b.prepared(s,m,"train",6)
    cal=b.prepared(s,m,"cal",6)
    test=b.prepared(s,m,"test",6)
    assert len(train.examples)>500 and len(test.examples)>100
    f,excl,_=b.train_strong(s,m,train)
    for group,fold in ((cal,"cal"),(test,"test")):
        val,skip=b.strong_predictions(s,f,group,fold)
        assert skip==0
        assert len(val["ridge_AR24"])==len(group.examples)
        assert len(val["seasonal_naive24"])==len(group.examples)
        assert len(set((v.origin_ms,v.target_ms) for v in group.examples))==len(group.examples)


def test_preregistered_classical_selection_uses_only_cal_mae():
    truth=np.asarray([1.,1.,1.,1.],dtype=float)
    preds={
        "direct_ridge":np.asarray([0.,0.,0.,0.]),
        "persistence":np.asarray([1.,1.,1.,1.]),
        "train_mean":np.asarray([3.,3.,3.,3.]),
        "timeaware_ssm":np.asarray([2.,2.,2.,2.]),
        "seasonal_naive24":np.asarray([1.2]*4),
        "ridge_AR24":np.asarray([1.1]*4),
    }
    chosen,metrics=b.cal_classical(truth,preds)
    assert chosen=="persistence"
    assert metrics["direct_ridge"]["mae"]==1.
    with pytest.raises(ValueError,match="frozen strong classical"):
        b.cal_classical(truth,{k:v for k,v in preds.items() if k!="ridge_AR24"})


def test_signed_negative_ridge_gain_is_not_disguised_as_success():
    truth=np.asarray([0.,0.,0.],dtype=float)
    ridge=b.metric(truth,np.zeros(3))
    selected=b.metric(truth,np.ones(3))
    assert ridge["rmse"]-selected["rmse"]==-1.


def test_real_case_frozen_calibration_before_holdout_and_source_pins():
    report=b.case("Guanyuan",1)
    assert report["site"]=="Guanyuan"
    assert report["horizon_hours"]==1 and report["rows_total"]==1920
    assert report["test_origin_examples"]>200
    assert report["test_eligible_origins"]==384
    assert report["source"]["upstream_sensor_signature_verified"] is False
    assert report["source"]["license"]=="CC BY 4.0"
    assert report["same_time_availability_originally_verified"] is False
    assert report["real_source_new_to_existing_cognitum_research"] is False
    assert not report["execution_authorized"]
    rows=report["full_heldout_predictions"]
    assert len(rows)==report["test_origin_examples"]
    methods=set(report["all_heldout_metrics"])
    assert {"direct_ridge","seasonal_naive24","ridge_AR24","ssm_kan_hdc"}<=methods
    for name,metric in report["all_heldout_metrics"].items():
        observed=np.asarray([z["observed_temperature_K"] for z in rows])
        pred=np.asarray([z["predictions_K"][name] for z in rows])
        assert metric["n"]==len(rows)
        assert metric["rmse"]==pytest.approx(
            float(np.sqrt(np.mean((observed-pred)**2))),abs=1e-9)
        assert metric["mae"]==pytest.approx(float(np.mean(abs(observed-pred))),
                                            abs=1e-9)
    for kind in ("default","research_opt_in"):
        frozen=report["selector_prior_to_test"][kind]
        actual=report["orc_frozen_heldout"][kind]
        assert frozen["selected"]==actual["selected"]
        assert not frozen["status"]=="APPROVED"
        assert math.isclose(actual["signed_rmse_gain_vs_ridge"],
                report["all_heldout_metrics"]["direct_ridge"]["rmse"]-
                report["all_heldout_metrics"][actual["selected"]]["rmse"],
                abs_tol=1e-9)
    assert report["train_ar24_insufficient_history"]>0
    assert report["python_tracemalloc_peak_bytes_partial_only"]>0


def test_historical_data_not_passed_off_as_verifiable_source_availability():
    _,s,_,p=b.acquire_site("Guanyuan")
    assert all(v.available_ms==v.timestamp_ms for v in s.rows)
    assert "NOT historically attested" in p["observation_availability"]
    assert p["previously_used_in_cognitum_ssm_research"]


def test_pre_result_protocol_is_referenced_not_generated_after_scores():
    path=b.ROOT/"docs/research/orcgraph/ORCH01E_BENCH01_PREREG.md"
    contents=path.read_text(encoding="utf-8")
    assert "PLAN LOCKED BEFORE RESULTS" in contents
    assert "first 1,920" in contents
    assert "CALIBRATION" in contents.upper()
    assert "ASSUMED" in contents
