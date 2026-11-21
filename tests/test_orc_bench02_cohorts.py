"""R3 freeze, negative-source, and no retrospective future/holdout leakage."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import pytest
from tools.orcbench02 import cohorts as c

START=1_800_000_456_789
END=START+2000
WINDOW_END=(START//c.HOUR)*c.HOUR-2*c.HOUR
WINDOW_START=WINDOW_END-192*c.HOUR

def record(i,station="KSEA",**updates):
    event=WINDOW_START+i*c.HOUR+50*60_000
    receipt=event+5*60_000
    row={"icaoId":station,"obsTime":event//1000,
         "receiptTime":datetime.fromtimestamp(receipt/1000,timezone.utc).isoformat(),
         "rawOb":"METAR "+station+" 010053Z 18010KT 10SM CLR 17/09 A3000",
         "temp":17.0+(i%9)*.1}
    row.update(updates)
    return row

def raw(rows):
    return json.dumps(rows,sort_keys=True,separators=(",",":")).encode()

def build(rows=None,station="KSEA"):
    data=raw([record(i,station) for i in range(191,-1,-1)] if rows is None else rows)
    return c.build_site(data,station,capture_start_ms=START,capture_end_ms=END,
                        sha256_pin=sha256(data).hexdigest())

def test_fixed_prereg_contract_and_hash():
    spec,pin=c.lock()
    assert pin=="fd0b6a372ee5cd9ee8870ad20c475261460a069daf4fd52f56e8dcc2961a5104"
    assert spec["independent_stations_in_fixed_order"]==["KSEA","KDEN","KATL"]
    assert "KMCI" not in spec["independent_stations_in_fixed_order"]
    assert spec["forecast_horizons_hours"]==[1,3,6]
    assert spec["chronological_folds"]==dict(train_hours=115,calibration_hours=38,test_hours=39)
    assert not spec["historical_provider_receipt_is_public_availability_proof"]

def test_full_hourly_grid_has_true_fixed_boundaries():
    out=build()
    assert out["source_clock_start_inclusive_ms"]==WINDOW_START
    assert out["source_clock_end_exclusive_ms"]==WINDOW_END
    assert out["original_source_rows"]==192
    assert out["hours_with_each_status"]=={"single_observation":192}
    assert len(out["horizons"])==3
    assert out["all_targets_kept_private_from_model_selection"]
    assert out["no_fitting_or_scoring_performed"]
    for arm in out["horizons"]:
        assert [arm["folds"][k]["all_origin_hours"] for k in
                ("train","calibration","test")]==[115,38,39]
        for name,start,stop in (("train",0,115),("calibration",115,153),("test",153,192)):
            fold=arm["folds"][name]
            assert fold["reason_counts"]["first_capture_bounded_eligible"]==0
            assert fold["reason_counts"]["target_crosses_fold"]==arm["forecast_horizon_hours"]
            for origin,target in fold["retrospective_origin_target_clock_pairs"]:
                assert WINDOW_START+(start+1)*c.HOUR <= origin <= WINDOW_START+stop*c.HOUR
                assert target>origin
                assert target<=WINDOW_START+stop*c.HOUR
                assert (target-origin)//c.HOUR==arm["forecast_horizon_hours"]

def test_source_provenance_matches_original_and_source_row_order():
    source=raw([record(3),record(1),record(2)])
    xs=c.source_rows(source,"KSEA",capture_start_ms=START,capture_end_ms=END,
                    sha256_pin=sha256(source).hexdigest())
    assert [r["source_row"] for r in xs]==[0,1,2]
    assert xs[0]["temperature_kelvin"]==pytest.approx(290.45)
    assert xs[0]["first_seen_ms"]==END
    assert xs[0]["receipt_ms"]<END

def test_real_r2_kmci_control_is_refused_as_new_site():
    source=raw([record(0,"KMCI")])
    with pytest.raises(c.Refusal,match="KMCI"):
        c.source_rows(source,"KMCI",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(source).hexdigest())

@pytest.mark.parametrize("changed,pattern",[
    ({"icaoId":"KLAX"},"station label"),
    ({"obsTime":"Nov 2026"},"epoch"),
    ({"obsTime":True},"epoch"),
    ({"receiptTime":None},"receipt"),
    ({"receiptTime":"2026-11-20 00:00:00"},"timezone"),
    ({"receiptTime":"2000-01-01T00:00:00Z"},"clock"),
    ({"rawOb":"METAR KLAX"},"raw report"),
    ({"temp":"17"},"Celsius"),
    ({"temp":float("inf")},"Celsius"),
    ({"temp":float("nan")},"Celsius"),
    ({"temp":-273.15},"Celsius"),
])
def test_schema_time_unit_or_station_forgery_refused(changed,pattern):
    source=raw([record(0,**changed)])
    with pytest.raises(c.Refusal,match=pattern):
        c.source_rows(source,"KSEA",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(source).hexdigest())

def test_altered_source_hash_and_truncated_json_refused():
    source=raw([record(0)])
    with pytest.raises(c.Refusal,match="SHA mismatch"):
        c.source_rows(source+b" ","KSEA",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(source).hexdigest())
    with pytest.raises(c.Refusal,match="JSON"):
        c.source_rows(source[:-1],"KSEA",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(source[:-1]).hexdigest())

def test_source_response_400_rows_refuses_instead_of_sampling():
    source=raw([record(0) for _ in range(400)])
    with pytest.raises(c.Refusal,match="400-row"):
        c.source_rows(source,"KSEA",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(source).hexdigest())

def test_hard_upper_byte_cap_refuses():
    source=b" "*2_000_001
    with pytest.raises(c.Refusal,match="oversized"):
        c.source_rows(source,"KSEA",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(source).hexdigest())

def test_missing_hour_and_temperature_never_imputed():
    rows=[record(i) for i in range(192) if i!=87]
    rows[12]["temp"]=None
    out=build(rows)
    assert out["hours_with_each_status"]=={"missing_hour":1,"missing_temperature":1,
                                            "single_observation":190}
    test=out["horizons"][0]["folds"]["train"]
    assert test["reason_counts"].get("feature_missing_hour",0)>0
    assert test["reason_counts"].get("feature_missing_temperature",0)>0

def test_same_hour_revisions_and_special_reports_ambiguous():
    rows=[record(i) for i in range(192)]
    rows.append(record(20,rawOb="METAR KSEA COR 010053Z 18010KT 10SM CLR 18/09 A3000"))
    out=build(rows)
    assert out["original_source_rows"]==193
    assert out["hours_with_each_status"]["ambiguous_multiple_or_corrected_reports"]==1
    assert out["horizons"][0]["folds"]["train"]["reason_counts"].get(
        "feature_ambiguous_multiple_or_corrected_reports",0)>0

def test_late_receipt_makes_feature_ineligible_not_available():
    rows=[record(i) for i in range(192)]
    row=rows[60]
    row["receiptTime"]=datetime.fromtimestamp((WINDOW_START+65*c.HOUR)/1000,
                                                timezone.utc).isoformat()
    out=build(rows)
    assert out["horizons"][0]["folds"]["train"]["reason_counts"].get(
        "feature_provider_receipt_late",0)>0

def test_late_first_capture_yields_zero_prospective_cases():
    out=build()
    assert sum(f["reason_counts"]["first_capture_bounded_eligible"]
               for h in out["horizons"] for f in h["folds"].values())==0
    assert sum(f["reason_counts"]["retrospective_receipt_proxy_eligible"]
               for h in out["horizons"] for f in h["folds"].values())>0
    assert not out["real_historical_publication_attested"]
    assert not out["production_admission_authorized"]

def test_no_target_leakage_in_train_or_calibration():
    out=build()
    for h in out["horizons"]:
        for name,limit in (("train",115),("calibration",153),("test",192)):
            assert all(target<=WINDOW_START+limit*c.HOUR for _,target in
                       h["folds"][name]["retrospective_origin_target_clock_pairs"])

def test_cohort_hash_independent_of_provider_row_order():
    rows=[record(i) for i in range(192)]
    left=build(rows)
    right=build(rows[::-1])
    for x,y in zip(left["horizons"],right["horizons"]):
        for name in ("train","calibration","test"):
            assert x["folds"][name]["retrospective_cohort_sha256"]==(
                y["folds"][name]["retrospective_cohort_sha256"])

def test_site_and_horizon_not_posthoc_adjusted_for_empty_station():
    sparse=build([record(1)])
    assert len(sparse["horizons"])==3
    assert sparse["hours_with_each_status"]["missing_hour"]==191
    assert all(f["reason_counts"]["retrospective_receipt_proxy_eligible"]==0
               for h in sparse["horizons"] for f in h["folds"].values())

def test_fixed_source_status_does_not_output_predictions_or_holdout_values():
    output=c.preregistration_summary()
    assert not output["forecast_models_fitted"]
    assert not output["heldout_scores_computed"]
    data=json.dumps(build(),sort_keys=True)
    assert "temperature_kelvin" not in data
    assert "rmse" not in data.lower() and "predictions" not in data.lower()

def test_policy_weakening_rejected(monkeypatch,tmp_path):
    spec,pin=c.lock()
    spec["forecast_horizons_hours"]=[1,2,3]
    location=tmp_path/"altered.json"
    location.write_text(json.dumps(spec))
    monkeypatch.setattr(c,"PREREG",location)
    with pytest.raises(c.Refusal,match="horizon mutation"):
        c.lock()

def test_actual_r2_archived_kmci_not_laundered_as_independent_station():
    previous=c.ROOT/"research_tests/orcbench02/awc_kmci_20261121/snapshot-000001.json"
    if not previous.exists():
        pytest.skip("The original R2 archive is only in the connected repository checkout")
    raw_bytes=previous.read_bytes()
    assert sha256(raw_bytes).hexdigest()==(
        "d332e16d7c9f9ae9253bdfd2563695aa2bc8cf39a92891549bb38a914914989a")
    assert len(json.loads(raw_bytes))==3
    with pytest.raises(c.Refusal,match="KMCI"):
        c.source_rows(raw_bytes,"KMCI",capture_start_ms=START,capture_end_ms=END,
                      sha256_pin=sha256(raw_bytes).hexdigest())
