"""R4 measured-time native model falsification: genuine native components, no future leakage."""
from pathlib import Path
import numpy as np
import pytest
from scipy.linalg import expm
from cognitum.research import ssm_timeaware as m

DATA=Path(__file__).parent/"data"
PREV=Path(__file__).parent.parent/"ssm_postnative05"/"data"
SRC={
 "Rac":DATA/"Rac_daily_Q.csv",
 "Musk":DATA/"Musk_daily_Q.csv",
 m.NOAA:PREV/"NOAA_RA_station_2025.csv"
}
META=(DATA/"USGS_siteInfo.csv").read_bytes()


@pytest.fixture(scope="module",params=["Rac","Musk",m.NOAA])
def obs(request):
    key=request.param
    return m.ingest(key,SRC[key].read_bytes(),META if key!="noaa_partner_water_level" else None)


@pytest.fixture(scope="module")
def model(obs):
    return m.fit(obs)


@pytest.fixture(scope="module")
def report(obs):
    return m.evaluate(obs)


def test_usgs_source_metadata_physical_units_and_locations():
    for name in ("Rac","Musk"):
        s=m.ingest(name,SRC[name].read_bytes(),META)
        assert s["unit"]=="cubic meters per second"
        assert s["metadata_blob"]==m.META_BLOB
        assert s["source_blob"]==m.USGS_BLOBS[name]
        assert len(s["times"])>3600 and np.all(np.diff(s["times"])==m.DAY)
        assert np.isfinite(s["state"]).all() and (s["state"]>=0).all()
        assert s["site_name"] in ("Raccoon River at Des Moines, IA",
                                   "Muskingum River at McConnelsville OH")
        assert "EGRET-derived" in s["provenance"]


@pytest.mark.parametrize("name",["Rac","Musk"])
def test_usgs_mutated_data_source_swap_and_metadata_refused(name):
    raw=bytearray(SRC[name].read_bytes());raw[100]^=1
    with pytest.raises(ValueError,match="source blob"):
        m.ingest(name,bytes(raw),META)
    other="Rac" if name=="Musk" else "Musk"
    with pytest.raises(ValueError,match="source blob"):
        m.ingest(name,SRC[other].read_bytes(),META)
    meta=bytearray(META);meta[100]^=1
    with pytest.raises(ValueError,match="metadata digest"):
        m.ingest(name,SRC[name].read_bytes(),bytes(meta))


def test_genuine_noaa_uneven_sampling_not_converted_to_uniform_sequence():
    s=m.ingest(m.NOAA,SRC[m.NOAA].read_bytes())
    assert s["original_rows"]==34099 and s["excluded_duplicates"]==18
    gaps=np.flatnonzero(np.diff(s["times"])!=300)
    assert len(gaps)>100
    fold=m.partition(len(s["times"]))[1]
    o,z=m.eligible(s,fold,300)
    assert np.all(s["times"][z]-s["times"][o]==300)
    # Next array item across a gap must never be a valid exact +5 minute target.
    bad=gaps[(gaps>=fold[0])&(gaps<fold[1]-1)]
    assert len(bad)>0 and int(bad[0]) not in set(o.tolist())


@pytest.mark.parametrize("h",[300,1800,7200])
def test_exact_continuous_ssm_against_matrix_exponential(h):
    tau=3*3600.
    a=m.ssm_zoh_rate(tau,h)
    assert a==pytest.approx(np.exp(-h/tau),abs=1e-14)
    assert a==pytest.approx(expm(np.array([[-1/tau]])*h)[0,0],abs=1e-14)
    assert 0<a<1
    with pytest.raises(ValueError,match="elapsed"):
        m.ssm_zoh_rate(tau,0)


def test_physical_domain_chronological_holdout_and_genuine_observation_count(obs):
    fs=m.partition(len(obs["times"]))
    for h in m.HORIZONS[obs["name"]]:
        folds=[m.eligible(obs,f,h) for f in fs]
        assert len(folds[0][0])>500 and len(folds[1][0])>100 and len(folds[2][0])>100
        previously=set()
        for (a,b),(o,z) in zip(fs,folds):
            assert np.all(o>=a) and np.all(z<b) and np.all(z>o)
            assert np.all(obs["times"][z]-obs["times"][o]==h)
            assert not previously.intersection(set(z.tolist()))
            previously.update(z.tolist())
        assert not set(folds[0][1].tolist())&set(folds[2][1].tolist())


def test_train_only_native_kan_hdc_components(model,obs):
    assert len(model["kan_snapshot"])==64
    assert model["train_hdc_prototypes"]==2
    assert model["train_transitions"]>800
    assert model["tau"]>0 and model["ssm_generator"]<0
    assert model["train_last_timestamp"]==obs["times"][m.partition(len(obs["times"]))[0][1]-1]
    # A source-native KAN snapshot and actual HDC prototypes are trained, not labels.
    raw,pin=model["kan"].research_snapshot()
    assert pin==model["kan_snapshot"] and len(raw)>10


def test_no_future_sensor_data_read_by_fitted_model(model,obs):
    h=m.HORIZONS[obs["name"]][0];f=m.partition(len(obs["times"]))[2]
    o,_=m.eligible(obs,f,h)
    selected=o[:50];assert len(selected)==50
    a,sa=m.hybrid_forecast(model,obs,selected,h)
    spoof=dict(obs);spoof["state"]=obs["state"].copy()
    spoof["state"][selected[-1]+1:]+=1000000.
    b,sb=m.hybrid_forecast(model,spoof,selected,h)
    np.testing.assert_array_equal(a,b)
    assert not sa["teacher_forced"] and not sa["future_sensor_value_used"]
    assert sb["elapsed_seconds"]==h


def test_kan_and_hdc_really_ablated_on_matched_origins(model,obs):
    h=m.HORIZONS[obs["name"]][0]
    o,_=m.eligible(obs,m.partition(len(obs["times"]))[2],h)
    o=o[:150]
    full,stat=m.hybrid_forecast(model,obs,o,h)
    notkan,_=m.hybrid_forecast(model,obs,o,h,kan=False)
    nothdc,_=m.hybrid_forecast(model,obs,o,h,hdc=False)
    assert full.shape==notkan.shape==nothdc.shape==(len(o),)
    assert np.isfinite(full).all()
    assert np.max(np.abs(full-notkan))>1e-10
    assert stat["hdc_accepted_origins"]>0
    assert not stat["teacher_forced"]


def test_model_honors_kan_ood_abstention_and_native_hdc_ambiguity():
    s=m.ingest(m.NOAA,SRC[m.NOAA].read_bytes())
    fit=m.fit(s)
    o,_=m.eligible(s,m.partition(len(s["times"]))[2],300)
    sample=o[:1]
    spoof=dict(s);spoof["state"]=s["state"].copy()
    spoof["state"][sample]=1e5
    pred,stat=m.hybrid_forecast(fit,spoof,sample,300)
    expected=m.base_prediction(fit,spoof,sample,300)
    assert pred==pytest.approx(expected,abs=1e-12)
    assert stat["kan_out_of_domain_origins"]==1
    assert stat["hdc_accepted_origins"]==0


def test_native_real_physical_dynamics_report_and_negative_results(report,obs):
    assert len(report["kan_snapshot_sha256"])==64
    assert report["real_elapsed_time_not_index"]
    assert not report["future_sensor_value_used"]
    assert not report["physical_law_discovered"]
    assert not report["conditional_dependent_coverage_guaranteed"]
    assert not report["full_hybrid_universal_superiority_proven"]
    assert not report["original_sensor_signed_attestation_verified"]
    assert not report["execution_authorized"]
    for h,x in report["horizons"].items():
        assert x["forecast_horizon_seconds"]==int(h)
        assert x["train_origins"]>500 and x["test_origins"]>100
        assert x["calibration_selected_baseline"] in ("persistence","harmonic","direct_ridge","timeaware_ssm")
        assert set(x["heldout_metrics"])=={
            "persistence","harmonic","direct_ridge","timeaware_ssm","HDC_KAN_SSM",
            "SSM_KAN_no_HDC","SSM_HDC_no_KAN"}
        for vals in x["heldout_metrics"].values():
            assert np.isfinite(vals["rmse"]) and vals["rmse"]>=0
        assert not x["selection_on_test"]
        assert x["hybrid_interval"]["conditional_coverage_guaranteed"] is False
        assert x["baseline_interval"]["conditional_coverage_guaranteed"] is False
        assert x["sensor_outage_sensitivity"]["imputed_missing_observations"] is False
        assert x["sensor_outage_sensitivity"]["retrospective_heldout_targets_only_for_sensitivity"]
        assert x["hybrid_stats"]["elapsed_seconds"]==int(h)


def test_block_max_calendar_gaps_refused_unless_enough_truly_contiguous():
    t=np.r_[np.arange(0,480)*300,(np.arange(480,960)+30)*300]
    e=np.ones(len(t));e[::24]=3.
    b=m.blocks(e,t,300,24)
    assert b.shape==(40,24)
    assert np.all(b.max(1)==3.)
    report=m.block_calibrate(e[:96],np.zeros(96),t[:96],e[480:576],np.zeros(96),t[480:576],m.NOAA)
    assert report["status"]=="REFUSED_INSUFFICIENT_DEPENDENT_BLOCKS"
    assert report["conditional_coverage_guaranteed"] is False


def test_false_physical_shift_not_promoted_to_observed_intervention():
    t=np.arange(0,1000)*300
    y=np.ones(1000);cal=np.ones(1000)
    diag=m.block_calibrate(y,cal,t,y,cal,t+300000,m.NOAA)
    assert diag["status"]=="DESCRIPTIVE_BLOCK_MAX_ONLY"
    assert diag["radius"]==0
    assert diag["conditional_coverage_guaranteed"] is False
    assert diag["synthetic_shift_3r_coverage"]==1
