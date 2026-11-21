"""R4-R2-R3 original native Orc portfolio and near-tie refusal replay."""
from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import json
import math
import numpy as np
import pytest

from tools.orcbench02 import portable_r4r2r3 as q
from tools.orcbench02 import original_orc_r4r2 as original
from tools.orcbench02 import benchmark_r4 as old

DEC=Path("bench02-r4r2r3-decisions.json")
SCORE=Path("bench02-r4r2r3-results.json")

def read():
    d=json.loads(DEC.read_bytes())
    s=json.loads(SCORE.read_bytes())
    fresh=q.freeze()
    q.compare_frozen(d,fresh)
    assert s["portable_aggregate_decision_sha256"]==d["portable_aggregate_decision_sha256"]
    return d,s

def test_original_r3_noaa_and_original_R4_negative_results_unchanged():
    d,s=read()
    cfg,_=q.prereg()
    assert s["original_R3_R4_R4R2_scientific_results_preserved"]
    assert s["original_model_algorithms_unchanged"]
    assert s["original_orc_propose_forecast_invoked"]
    assert not d["heldout_scored"]
    assert s["original_first_capture_eligible_origins"]==0
    assert not s["historical_publication_proven"]
    assert not s["installed_MEL_authorized"]
    assert s["matched_heldout_origins"]==cfg["original_total_retrospective_test_pairs"]

def test_exact_nine_original_unchanged_cohorts_265_matched_forecasts():
    d,s=read()
    assert len(d["source_locked_cases"])==9
    assert len(s["cases"])==9
    assert s["site_horizon_cases"]==9
    assert len(s["matched_native_forecasts"])==265
    for case in s["cases"]:
        name=case["task"];station=name[:4];hours=int(name[5:-1])
        original_site=old.site_data(station)
        expected=original_site["cohort"]["horizons"][original.HORIZONS.index(hours)]["folds"]["test"]
        pair=[(v["origin_ms"],v["target_ms"]) for v in s["matched_native_forecasts"]
              if v["task"]==name]
        assert pair==[tuple(x) for x in expected["retrospective_origin_target_clock_pairs"]]
        assert case["original_R3_test_cohort_sha256"]==expected["retrospective_cohort_sha256"]
        assert case["origin_n"]==expected["reason_counts"]["retrospective_receipt_proxy_eligible"]
        assert d["source_locked_cases"][name]["original_test_pair_SHA256"]==expected["retrospective_cohort_sha256"]
        assert case["portable_receipt_sha256"]==d["source_locked_cases"][name]["portable_receipt_sha256"]
        assert case["original_noaa_sha256"]==q.prereg()[0]["original_raw_sha256"][station]

def test_near_tie_is_conservative_portable_abstention_not_improved_model_choice():
    d,s=read()
    f=d["source_locked_cases"]["KATL_1h"]
    before=f["full_precision_original_decisions"]["research_opt_in"]
    assert before["selected"] is None
    assert before["status"]=="ABSTAIN"
    assert before["selection_basis"]=="portable_near_tie_abstention"
    assert "ambiguous_near_tied_research_calibration" in before["reasons"]
    case=next(x for x in s["cases"] if x["task"]=="KATL_1h")
    assert case["original_selection_status"]["research_opt_in"]["selected"] is None
    assert "original_orc_research_opt_in" not in case["all_native_model_metrics"]
    assert "original_orc_default" in case["all_native_model_metrics"]
    for p in s["matched_native_forecasts"]:
        if p["task"]=="KATL_1h":
            assert "original_orc_research_opt_in" not in p["native_method_predictions_kelvin"]

def test_no_selector_backfill_where_original_study_missingness_is_real():
    _,s=read()
    for site in ("KSEA_6h","KDEN_6h"):
        case=next(c for c in s["cases"] if c["task"]==site)
        assert case["original_selection_status"]["default"]["status"]=="ABSTAIN"
        assert case["original_selection_status"]["research_opt_in"]["status"]=="ABSTAIN"
        assert "original_orc_default" not in case["all_native_model_metrics"]
        assert "original_orc_research_opt_in" not in case["all_native_model_metrics"]

def test_original_full_matched_native_forecast_metrics_independently_recomputed():
    _,s=read()
    for c in s["cases"]:
        rows=[x for x in s["matched_native_forecasts"] if x["task"]==c["task"]]
        assert len(rows)==c["origin_n"]
        y=np.asarray([r["target_kelvin"] for r in rows])
        for method,stored in c["all_native_model_metrics"].items():
            p=np.asarray([r["native_method_predictions_kelvin"][method] for r in rows])
            indep=q.metric(y,p)
            assert indep["n"]==stored["n"]
            assert math.isclose(indep["mae"],stored["mae"],abs_tol=1e-10)
            assert math.isclose(indep["rmse"],stored["rmse"],abs_tol=1e-10)
            base=c["all_native_model_metrics"]["original_R4_direct_ridge"]["rmse"]
            gain=c["signed_gains_vs_prior_R4_ridge"][method]
            assert math.isclose(gain["signed_rmse_gain_kelvin"],base-stored["rmse"],abs_tol=1e-10)

def test_all_macros_and_losses_including_abstention_not_hidden():
    _,s=read()
    for method,summary in s["methods"].items():
        gains=[c["signed_gains_vs_prior_R4_ridge"][method]["fractional_rmse_gain"]
               for c in s["cases"] if method in c["all_native_model_metrics"]]
        omitted=[c["task"] for c in s["cases"] if method not in c["all_native_model_metrics"]]
        assert summary["reported"]==len(gains)
        assert summary["abstained_cases"]==omitted
        assert summary["wins"]==sum(v>1e-10 for v in gains)
        assert summary["losses"]==sum(v< -1e-10 for v in gains)
        assert summary["ties"]==sum(abs(v)<=1e-10 for v in gains)
        assert summary["complete_nine_case_macro"]==(len(gains)==9)
        if gains:
            assert math.isclose(summary["reported_only_macro"],float(np.mean(gains)),abs_tol=1e-12)
        else:assert summary["reported_only_macro"] is None

def test_forged_frozen_decision_has_no_posthoc_test_rescue():
    d,_=read()
    modified=deepcopy(d)
    modified["source_locked_cases"]["KATL_1h"]["full_precision_original_decisions"][
        "research_opt_in"]["selected"]="ssm_kan"
    with pytest.raises(q.Refusal,match="altered frozen"):
        q.score(modified)
