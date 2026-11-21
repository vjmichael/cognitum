"""Independent full R3 original-native specialist result replay.

No new data downloads. Read the two immutable-phase native CI files.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from collections import defaultdict
import pytest

from tools.orcbench02 import original_orc_r4r2 as r
from tools.orcbench02 import benchmark_r4 as old

DECISIONS=Path("bench02-r4r2-decisions.json")
RESULTS=Path("bench02-r4r2-results.json")

def files():
    assert DECISIONS.exists() and RESULTS.exists()
    d=json.loads(DECISIONS.read_bytes())
    p=json.loads(RESULTS.read_bytes())
    assert r.hashed(d)==r.hashed(r.freeze())
    assert p["frozen_calibration_decision_sha256"]==d["decision_sha256"]
    return d,p

def test_original_native_declarations_are_not_adapter_fakes():
    d,p=files()
    assert d["native_original_orc_propose_forecast"]
    assert d["native_KAN_and_HDC_fitted"]
    assert p["direct_original_propose_and_frozen_evaluate_called"]
    assert p["models_fitted_original_native_KAN_HDC_SSM"]
    assert not p["production_MEL_authorized"]
    assert not p["all_noaa_historical_publication_attested"]
    assert p["strict_first_capture_test_origins"]==0
    assert d["previous_R4_heldout_data_already_viewed"]

def test_nine_complete_source_stamped_original_cohorts():
    d,p=files()
    assert len(d["cases"])==len(p["cases"])==9
    assert p["source_cases"]==9
    assert p["original_matched_test_origins"]==265
    assert [case["task"] for case in p["cases"]]==[
        f"{site}_{h}h" for site in r.SITES for h in r.HORIZONS]
    for case in p["cases"]:
        task=case["task"]
        original=old.site_data(case["site"])
        fold=original["cohort"]["horizons"][r.HORIZONS.index(case["horizon_hours"])]["folds"]["test"]
        clocks=[(x["origin_ms"],x["target_ms"]) for x in p["original_rows_and_predictions"]
                if x["task"]==task]
        assert clocks==[tuple(v) for v in fold["retrospective_origin_target_clock_pairs"]]
        assert case["tested_origin_count"]==fold["reason_counts"]["retrospective_receipt_proxy_eligible"]
        assert case["R3_test_original_cohort_sha256"]==fold["retrospective_cohort_sha256"]
        assert d["cases"][task]["R3_test_pairs_sha256"]==fold["retrospective_cohort_sha256"]

def test_all_heldout_predictions_independent_metric_and_sign_replay():
    _,p=files()
    for case in p["cases"]:
        rows=[v for v in p["original_rows_and_predictions"] if v["task"]==case["task"]]
        assert rows
        expected={"original_R4_direct_ridge",*r.METHODS}
        for row in rows:
            assert expected.issubset(row["predictions_kelvin"])
            assert row["origin_ms"]<row["target_ms"]
            assert row["original_NOAA_sha256"]==r.protocol()["original_raw_sha256"][case["site"]]
        for method,reported in case["all_matched_native_metrics"].items():
            y=[float(z["target_kelvin"]) for z in rows]
            pred=[float(z["predictions_kelvin"][method]) for z in rows]
            n=len(y)
            mae=sum(abs(a-b) for a,b in zip(y,pred))/n
            rmse=math.sqrt(sum((a-b)**2 for a,b in zip(y,pred))/n)
            assert reported["n"]==n
            assert math.isclose(mae,reported["mae"],abs_tol=1e-10)
            assert math.isclose(rmse,reported["rmse"],abs_tol=1e-10)
            baseline=case["all_matched_native_metrics"]["original_R4_direct_ridge"]
            assert math.isclose(baseline["rmse"]-rmse,
                case["all_signed_gains_vs_accepted_R4_direct_ridge"][method]["signed_rmse_gain_kelvin"],
                abs_tol=1e-10)

def test_decisions_frozen_and_original_policy_abstentions_not_filled():
    d,p=files()
    for case in p["cases"]:
        pre=d["cases"][case["task"]]
        assert case["frozen_decision_sha256"]==d["decision_sha256"]
        assert pre["heldout_labels_not_evaluated"]
        assert pre["native_original_propose_forecast_invoked"]
        assert pre["native_specialists_trained_only_on_original_train"]
        assert pre["native_kan_snapshot_sha256"]
        assert pre["native_hdc_train_prototype_sha256"]
        assert set(pre["calibration_methods"])==set(r.METHODS)
        for key in ("default","research_opt_in"):
            selected=pre["selected_prior_to_heldout"][key]
            scored=case["actual_orc_proposals"][key]
            assert scored["status"]==selected["status"]
            assert scored["selected"]==selected["selected"]
            if selected["selected"] is None:
                assert scored["status"]=="ABSTAIN"
                assert "original_orc_"+key not in case["all_matched_native_metrics"]
            else:
                assert scored["decision_sha256"]==selected["decision_sha256"]
                assert scored["real_original_evaluate_frozen_proposal_called"]
                method="original_orc_"+key
                assert method in case["all_matched_native_metrics"]

def test_independent_total_and_macro_wins_losses_with_abstention():
    _,p=files()
    for method,reported in p["all_task_summaries"].items():
        v=[case["all_signed_gains_vs_accepted_R4_direct_ridge"][method]["fractional_rmse_gain"]
           for case in p["cases"] if method in case["all_matched_native_metrics"]]
        assert reported["reported"]==len(v)
        assert reported["win"]==sum(z>1e-10 for z in v)
        assert reported["loss"]==sum(z< -1e-10 for z in v)
        assert reported["tie"]==sum(abs(z)<=1e-10 for z in v)
        assert reported["reported"]+len(reported["abstained_cases"])==9
        assert reported["complete_nine_case_macro"]==(len(v)==9)
        if v:
            assert math.isclose(reported["macro_signed_fractional_rmse_gain"],
                                sum(v)/len(v),abs_tol=1e-12)
        else:
            assert reported["macro_signed_fractional_rmse_gain"] is None

def test_results_are_not_renamed_production_or_prospective_evidence():
    d,p=files()
    assert d["heldout_labels_scored"] is False
    assert p["prior_r4_retrospective_source_and_results_preserved"]
    assert p["strict_first_capture_test_origins"]==0
    assert all(case["first_capture_bounded_origin_count"]==0 for case in p["cases"])
    assert all(case["historical_provider_first_availability_signed"] is False
               for case in p["cases"])

def test_decision_tamper_cannot_change_native_method_after_frozen():
    d,_=files()
    d["cases"]["KSEA_1h"]["selected_prior_to_heldout"]["default"]["selected"]="ssm_kan"
    with pytest.raises(r.Refusal,match="changed after freeze"):
        r.score(d)
