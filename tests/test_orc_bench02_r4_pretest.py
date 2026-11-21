"""R4 pre-result training/selection, original cohort and tamper refusals."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import pytest
import numpy as np

from tools.orcbench02 import benchmark_r4 as b

def test_frozen_before_scores_contract_and_site_inventory():
    p=b.policy()
    assert p["preregistered_before_R4_target_read_or_model_fit"]
    assert p["prereg_site_order"]==list(b.SITE_ORDER)
    assert p["guardrails"]["all_9_case_reports_required"]
    assert p["guardrails"]["no_holdout_based_method_choice"]
    assert p["R3_frozen_protocol_sha256"]==b.R3_SHA
    assert p["R4_full_specialist_HDC_KAN_scope"].startswith("NOT_QUALIFIED")

@pytest.mark.parametrize("site",b.SITE_ORDER)
def test_authentic_original_source_replays_frozen_hourly_site(site):
    d=b.site_data(site)
    assert d["original_sha256"]==b.policy()["R3_raw_sha256"][site]
    assert len(d["cohort"]["horizons"])==3
    assert not d["cohort"]["real_historical_publication_attested"]
    assert not d["cohort"]["production_admission_authorized"]

@pytest.mark.parametrize("h",b.HORIZONS)
def test_complete_fixed_katl_fold_and_unmodified_cohort_hash(h):
    d=b.site_data("KATL")
    for fold in ("train","calibration","test"):
        batch=b.batch(d,h,fold)
        original=d["cohort"]["horizons"][b.HORIZONS.index(h)]["folds"][fold]
        assert len(batch["y"])==original["reason_counts"]["retrospective_receipt_proxy_eligible"]
        assert batch["hash"]==original["retrospective_cohort_sha256"]
        assert len(batch["clocks"])==len(batch["y"])
        assert np.isfinite(batch["x"]).all()

def test_train_only_fit_expected_features_and_elapsed_time():
    d=b.site_data("KSEA")
    fitted=b.fit(b.batch(d,1,"train"),1)
    assert fitted["train_n"]==74
    assert fitted["tau_hours"] in (1,4,16,64)
    assert fitted["direct"]["lag_indices"]==[0,1]
    assert fitted["ar24"]["lag_indices"]==[0,1,2,3,4]
    assert fitted["direct"]["beta"].shape==(3,)
    assert fitted["ar24"]["beta"].shape==(6,)

def test_all_nine_calibration_decisions_precede_scoring():
    frozen=b.prepare()
    assert not frozen["test_labels_scored"]
    assert len(frozen["cases"])==9
    assert frozen["decision_sha256"]==b.digest({
        k:v for k,v in frozen.items() if k!="decision_sha256"})
    for name,record in frozen["cases"].items():
        assert record["all_heldout_labels_unscored"]
        assert "heldout_metrics" not in record
        assert "predictions" not in record
        assert record["selectors"]["orc_default"]["selector"].endswith(
            "not_direct_propose_forecast")
        assert record["selectors"]["orc_default"]["calibration_n"]>=20

def test_selector_does_not_depend_on_test_labels():
    source=b.site_data("KDEN")
    train=b.batch(source,3,"train")
    cal=b.batch(source,3,"calibration")
    model=b.fit(train,3)
    preds=b.predict(model,cal)
    one=b.select(model,preds,cal,"orc_default")
    copied=deepcopy(source["cohort"])
    copied["horizons"][1]["folds"]["test"]["first_capture_origin_target_clock_pairs"]=[]
    # Selection consumes only training/actual calibration objects, not the test.
    two=b.select(model,preds,cal,"orc_default")
    assert one==two

def test_calibration_only_policy_refuses_missing_source_evidence():
    source=b.site_data("KSEA")
    model=b.fit(b.batch(source,1,"train"),1)
    cal=b.batch(source,1,"calibration")
    cal["fold_hours"]=1000
    a=b.select(model,b.predict(model,cal),cal,"orc_default")
    assert a["status"]=="ABSTAIN"
    assert "excessive_calibration_missing_or_unavailable" in a["reasons"]

def test_source_tamper_denied(tmp_path,monkeypatch):
    original=b.DATA
    root=tmp_path/"e"
    root.mkdir()
    for suffix in ("-original.json","-receipt.json","-cohort.json"):
        name="KATL"+suffix
        (root/name).write_bytes((original/name).read_bytes())
    path=root/"KATL-original.json"
    path.write_bytes(path.read_bytes()+b" ")
    monkeypatch.setattr(b,"DATA",root)
    with pytest.raises(b.Refusal,match="source bytes"):
        b.site_data("KATL")

def test_frozen_r4_protocol_forgery_denied(tmp_path,monkeypatch):
    p=json.loads(b.R4_PATH.read_text())
    p["horizons_hours"]=[1,2,6]
    file=tmp_path/"mutated.json"
    file.write_text(json.dumps(p))
    monkeypatch.setattr(b,"R4_PATH",file)
    with pytest.raises(b.Refusal,match="Git blob altered"):
        b.policy()

def test_r4_selector_is_explicit_adapter_not_full_original_specialists():
    p=b.policy()
    assert not p["guardrails"]["no_claim_of_full_Orc_KAN_HDC_specialists"] is False
    d=b.prepare()
    assert d["policy_adapter_not_original_propose_forecast"]
    assert d["HDC_KAN_specialists_not_evaluated"]
