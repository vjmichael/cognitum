"""R5 historical evidence locks, no prospective model accuracy claims."""
from __future__ import annotations
from hashlib import sha1
import json
from pathlib import Path
import pytest
from tools.orcbench02 import audit_r5 as audit
from tools.orcbench02 import prospective_r5 as p

ROOT=Path(__file__).resolve().parents[1]
HIST=ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R5_HISTORICAL_AUDIT.json"
R4=ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R4.md"
R4R2R3=ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R4_R2_R3_NATIVE_ARTIFACTS.json"

def gitblob(v):
    return sha1(b"blob "+str(len(v)).encode()+b"\0"+v).hexdigest()

def test_original_acceptance_receipts_and_negative_history_unchanged():
    x=json.loads(HIST.read_bytes())
    assert x["schema"]=="cognitum.orc.bench02.r5.independently_consolidated_original_science.v1"
    assert gitblob(R4.read_bytes())=="5dc4fa1f980fc7678371cba78dbfdbdfe09fb651"
    assert gitblob(R4R2R3.read_bytes())=="ea8c8ab8fb90a272b68d5bc56d66d9f031c4b42c"
    assert x["original_acceptance_runs"]["R4"]["run"]==44873223743
    assert x["original_acceptance_runs"]["R4_R2_R3"]["run"]==44875900382
    assert x["original_history_observations"]["identical_265_origin_target_clocks_both_archival_studies"]
    assert x["original_history_observations"]["max_original_direct_ridge_replay_difference_K"]==0

def test_original_R4_policy_negative_results_not_harmonized_with_research_proposals():
    m=json.loads(HIST.read_bytes())["method_results_vs_accepted_R4_direct_ridge"]
    assert m["R4_policy_adapter_default"]["macro_fractional_RMSE_gain"]<0
    assert m["R4_policy_adapter_expanded_classical"]["macro_fractional_RMSE_gain"]<0
    assert m["original_native_Orc_default"]["reported_only_fractional_RMSE_gain"]<0
    assert m["original_native_Orc_research_portable"]["reported_only_fractional_RMSE_gain"]<0
    assert not m["original_native_Orc_default"]["complete_nine_case_macro"]
    assert not m["original_native_Orc_research_portable"]["complete_nine_case_macro"]
    assert m["original_native_Orc_research_portable"]["abstentions"]==[
        "KSEA_6h","KDEN_6h","KATL_1h"]
    assert m["original_native_SSM_KAN"]["macro_fractional_RMSE_gain"]>\
           m["original_native_SSM_KAN_HDC"]["macro_fractional_RMSE_gain"]

def test_archive_sha_inventory_matches_independent_original_auditor():
    x=json.loads(HIST.read_bytes())
    registered={y["id"]:y["sha256"] for y in x["original_nine_archived_ZIPs"]}
    assert len(registered)==9
    assert registered=={**audit.R4,**audit.NATIVE,**audit.FOURWAY}
    assert x["native_model_integrity"]["portable_four_way_sha256"]==audit.PORTABLE_SHA
    assert x["limitations"]["R3_strict_first_capture_heldout_origins"]==0
    assert x["limitations"]["no_prospective_out_of_sample_superiority_proven"]
    assert x["prospective_successor"]["observations_captured_under_new_protocol"]==0
    assert x["prospective_successor"]["independent_GitHub_creation_time_receipts_obtained"]==0
    assert not x["prospective_successor"]["network_capture_active"]

def test_R5_precommit_and_original_scientific_methods_are_not_retrained():
    x=json.loads(HIST.read_bytes())
    assert p.gitblob(p.PRE.read_bytes())==p.PRE_BLOB
    assert x["prospective_successor"]["original_new_prereg_git_blob"]==p.PRE_BLOB
    s=p.prereg()
    assert s["models"]["no_post_hoc_alpha_basis_or_hdc_research_training_changes"]
    assert s["models"]["research_selection_near_tie_tolerance_K"]==1e-10
    assert s["scientific_metrics"]["coverage_abstention"].startswith("report all")
    assert s["execution"]["CI_policy"].startswith("manual-only")

def test_9_case_all_method_substitutions_are_impossible():
    x=json.loads(HIST.read_bytes())
    assert x["original_history_observations"]["R3_prereg_sha256"]==\
        "fd0b6a372ee5cd9ee8870ad20c475261460a069daf4fd52f56e8dcc2961a5104"
    assert set(x["original_history_observations"]["original_NOAA_sha256"])==\
        {"KSEA","KDEN","KATL"}
    assert x["original_acceptance_runs"]["R4_R2_R3"]["original_retrospective_cases"]==9
    assert x["original_acceptance_runs"]["R4"]["original_heldout_pairs"]==265
    assert x["native_model_integrity"]["portable_near_tie_refusal_KATL_1h"]
