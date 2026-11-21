"""R4-R2-R3 fail-closed portable original Orc selection pretest."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import math
import json
import pytest
import numpy as np

from cognitum import orc_selection as choice, orc_comparison as comp
from cognitum.research.kan_trainable import load_snapshot
from tools.orcbench02 import portable_r4r2r3 as q
from tools.orcbench02 import original_orc_r4r2 as old

def test_protocol_frozen_then_amended_receipt_only_before_native_scoring():
    p,a=q.prereg()
    assert p["original_total_retrospective_test_pairs"]==265
    assert p["selection_policy"]["opt_in_value"]==1e-10
    assert a["superseding_scores_decimals"]==8
    assert a["unchanged_selector_near_tie_threshold_kelvin"]==1e-10
    assert a["supersedes_only"].startswith("portable_numerical_identity")
    assert not p["comparison_limits"]["no_train_on_existing_test"] is False
    assert p["comparison_limits"]["first_capture_bounded_test_eligibility"]==0

@pytest.mark.parametrize("bad",[True,0,1,1e-4,float("nan"),float("inf"),-1e-10])
def test_explicit_policy_rejects_nonfloat_large_or_nonfinite_tolerance(bad):
    with pytest.raises(ValueError,match="bounded near-tie"):
        choice.SelectionPolicy(portable_near_tie_mae_kelvin=bad)

def test_original_legacy_policy_defaults_are_still_disabled():
    a=choice.SelectionPolicy()
    b=choice.SelectionPolicy(portable_near_tie_mae_kelvin=0.0)
    assert a==b
    assert a.portable_near_tie_mae_kelvin==0.
    assert q.opts()["research_opt_in"].portable_near_tie_mae_kelvin==1e-10
    assert q.opts()["default"].portable_near_tie_mae_kelvin==1e-10

def test_original_KATL1_research_near_tie_refuses_not_switches():
    x,p,receipt=q.original_fitted_case("KATL",1)
    assert x["model"].research_hdc and x["model"].research_kan
    assert p["research_opt_in"].status=="ABSTAIN"
    assert p["research_opt_in"].selected is None
    assert p["research_opt_in"].selection_basis=="portable_near_tie_abstention"
    assert "ambiguous_near_tied_research_calibration" in p["research_opt_in"].reasons
    assert p["default"].status=="PROPOSED_OFFLINE"
    assert p["default"].selected=="direct_ridge"
    original=x["proposals"]["research_opt_in"]
    assert original.selected in ("ssm_kan","ssm_kan_hdc") and original.selected!=p["research_opt_in"].selected
    mae=dict(x["calibration"].scores)
    assert abs(mae["ssm_kan"].mae-mae["ssm_kan_hdc"].mae)<1e-10
    assert receipt["first_capture_eligible_test"]==0
    assert not receipt["execution_authorized"]

def test_normal_native_ORC_selection_unmodified_for_unambiguous_case():
    native,decisions,receipt=q.original_fitted_case("KSEA",1)
    assert decisions["research_opt_in"].selected==native["proposals"]["research_opt_in"].selected
    assert decisions["default"].selected==native["proposals"]["default"].selected
    assert not any(d.selection_basis=="portable_near_tie_abstention" for d in decisions.values())
    assert len(receipt["calibration_numeric_receipts"])==7
    assert receipt["method_inventory"]==list(comp.METHODS)

def test_no_original_KAN_HDC_model_refit_or_architecture_change():
    native,_,_=q.original_fitted_case("KATL",1)
    model=native["model"]
    net=load_snapshot(model.kan_snapshot,model.kan_snapshot_sha256)
    assert len(net.layers)==1
    assert net.layers[0].kind=="chebyshev"
    assert net.layers[0].degree==2
    assert net.layers[0].inputs==2
    assert len(model.hdc_prototypes)==2
    assert len(model.hdc_prototypes[0])==256
    assert model.kan_snapshot_sha256==sha256(model.kan_snapshot).hexdigest()
    assert not model.execution_authorized

def test_certificate_uses_exact_source_and_calibration_numerics_only():
    _,_,receipt=q.original_fitted_case("KSEA",3)
    p,_=q.prereg()
    assert receipt["R3_original_NOAA_SHA256"]==p["original_raw_sha256"]["KSEA"]
    assert receipt["training_count"]>0 and receipt["calibration_count"]>=20
    assert len(receipt["R3_original_train_cal_test_clock_SHA256"])==3
    assert len(receipt["original_selection"])==2
    assert len(receipt["calibration_numeric_receipts"])==7
    assert "raw_original_decision_sha256" not in str(receipt)

def test_frozen_pretest_replays_original_nine_cases_without_holdout():
    frozen=q.freeze()
    assert len(frozen["source_locked_cases"])==9
    assert not frozen["heldout_scored"]
    assert frozen["native_model_fitting_algorithm_unchanged"]
    assert frozen["portable_aggregate_decision_sha256"]==q.digest({
        k:v["portable_receipt_sha256"] for k,v in frozen["source_locked_cases"].items()})
    for task,row in frozen["source_locked_cases"].items():
        assert row["calibration_selected_only"]
        assert row["heldout_scored"] is False
        assert "heldout_metrics" not in row

def test_rounding_boundary_refuses_ambiguous_portable_certificate():
    # Strict decimal rounding protects numerical audit, never scientific selection.
    with pytest.raises(q.Refusal,match="rounding boundary"):
        q.quantize(1.000000005)
    assert q.quantize(1.2345678923)=="1.23456789"

def test_recreated_frozen_artifact_rejects_forged_selection():
    f=q.freeze()
    forged=json.loads(json.dumps(f))
    forged["source_locked_cases"]["KATL_1h"]["full_precision_original_decisions"][
        "research_opt_in"]["selected"]="ssm_kan"
    with pytest.raises(q.Refusal,match="altered frozen"):
        q.compare_frozen(forged,f)

def test_original_orc_research_policy_returns_correct_abstention_for_missing():
    for site,h in (("KSEA",6),("KDEN",6)):
        _,decisions,_=q.original_fitted_case(site,h)
        assert decisions["research_opt_in"].status=="ABSTAIN"
        assert decisions["default"].status=="ABSTAIN"
