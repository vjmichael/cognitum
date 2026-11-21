"""Independent numerical replay of original heldout rows and fixed decisions.

Invoked ONLY after the separate --phase freeze artifact has been fsynced and
--phase score has completed at the exact same source SHA.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import math
import pytest
import numpy as np

from tools.orcbench02 import benchmark_r4 as b

FREEZE=Path("bench02-r4-decisions.json")
RESULTS=Path("bench02-r4-results.json")

def read():
    assert FREEZE.exists() and RESULTS.exists()
    decisions=json.loads(FREEZE.read_bytes())
    results=json.loads(RESULTS.read_bytes())
    assert decisions==b.prepare()
    assert results["frozen_decision_sha256"]==decisions["decision_sha256"]
    return decisions,results

def test_original_frozen_decisions_have_no_heldout_metrics():
    d,_=read()
    assert not d["test_labels_scored"]
    assert all(c["all_heldout_labels_unscored"] for c in d["cases"].values())
    assert all("all_heldout_metrics" not in c for c in d["cases"].values())

def test_all_nine_tasks_and_sources_preserved():
    d,r=read()
    assert len(d["cases"])==9
    assert r["source_cases"]==9
    assert [case["task"] for case in r["cases"]]==[
        f"{s}_{h}h" for s in b.SITE_ORDER for h in b.HORIZONS]
    assert r["total_heldout_rows"]==sum(
        x["test_eligible_origins"] for x in r["cases"])
    assert all(not c["full_HDC_KAN_orc_evaluated"] for c in r["cases"])

def test_exact_original_heldout_origins_not_intersected():
    _,r=read()
    for case in r["cases"]:
        site=case["station"]; h=case["horizon_hours"]
        source=b.site_data(site)
        original=source["cohort"]["horizons"][b.HORIZONS.index(h)]["folds"]["test"]
        pairs=[(row["origin_ms"],row["target_ms"])
               for row in r["full_original_heldout_predictions"] if row["task"]==case["task"]]
        assert pairs==[tuple(x) for x in original["retrospective_origin_target_clock_pairs"]]
        assert case["test_cohort_sha256"]==original["retrospective_cohort_sha256"]
        assert len(pairs)==original["reason_counts"]["retrospective_receipt_proxy_eligible"]

def test_each_original_prediction_metric_recomputed_without_selected_model():
    _,r=read()
    for case in r["cases"]:
        rows=[row for row in r["full_original_heldout_predictions"]
              if row["task"]==case["task"]]
        assert len(rows)==case["test_eligible_origins"]
        for method,reported in case["all_heldout_metrics"].items():
            truth=np.asarray([x["observed_target_kelvin"] for x in rows])
            predicted=np.asarray([x["predictions_kelvin"][method] for x in rows])
            independent=b.metrics(truth,predicted)
            assert independent["n"]==reported["n"]
            assert math.isclose(independent["mae"],reported["mae"],abs_tol=1e-10)
            assert math.isclose(independent["rmse"],reported["rmse"],abs_tol=1e-10)
            gain=case["all_signed_gains"][method]
            assert math.isclose(gain["signed_rmse_gain_kelvin"],
                   case["all_heldout_metrics"]["direct_ridge"]["rmse"]-reported["rmse"],
                   abs_tol=1e-10)

def test_decision_is_frozen_from_calibration_before_test():
    d,r=read()
    for case in r["cases"]:
        f=d["cases"][case["task"]]
        assert case["frozen_decision_sha256"]==d["decision_sha256"]
        for name,chosen in case["selected_methods"].items():
            assert chosen==f["selectors"][name]["selected"]
            if chosen is not None:
                assert chosen in b.EVALUATED
            else:
                assert f["selectors"][name]["status"]=="ABSTAIN"

def test_all_methods_same_original_truth_and_no_replacement():
    _,r=read()
    for row in r["full_original_heldout_predictions"]:
        assert set(row["predictions_kelvin"])==set(b.METHODS)
        assert row["source_sha256"]==b.policy()["R3_raw_sha256"][row["task"][:4]]
        assert row["target_ms"]>row["origin_ms"]
    for case in r["cases"]:
        assert all(v["n"]==case["test_eligible_origins"]
                   for v in case["all_heldout_metrics"].values())

def test_independent_win_loss_tie_and_macro_replay():
    _,r=read()
    for method,s in r["summaries"].items():
        values=[case["all_signed_gains"][method]["dimensionless_relative_rmse_gain"]
                for case in r["cases"] if method in case["all_signed_gains"]]
        assert s["cases"]==len(values)
        assert s["wins"]+s["losses"]+s["ties"]==s["cases"]
        eps=b.policy()["tie_epsilon"]
        assert s["wins"]==sum(x>eps for x in values)
        assert s["losses"]==sum(x < -eps for x in values)
        assert s["ties"]==sum(abs(x)<=eps for x in values)
        assert math.isclose(s["macro_mean_fractional_rmse_gain"],
                            float(np.mean(values)),abs_tol=1e-12)

def test_historical_first_capture_and_production_claims_remain_refused():
    d,r=read()
    assert r["strict_first_capture_eligible_test_origins"]==0
    assert not r["historical_publication_attested"]
    assert not r["installed_MEL_execution_authorized"]
    assert not r["direct_existing_Orc_propose_forecast_invoked"]
    assert not r["native_HDC_KAN_specialists_evaluated"]
    assert all(c["strict_first_capture_eligible_origins"]==0 for c in r["cases"])
    assert all(c["retrospective_AWC_receipt_proxy_only"] for c in r["cases"])
    assert all(not v["conditional_guarantee"]
               for case in r["cases"] for v in case["paired_dependence_sensitivity"].values())

def test_no_test_score_changes_frozen_selection():
    d,r=read()
    edited=json.loads(json.dumps(d))
    edited["cases"]["KSEA_1h"]["selectors"]["orc_default"]["selected"]="forged"
    with pytest.raises(b.Refusal,match="frozen calibration"):
        b.score(edited)
