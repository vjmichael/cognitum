"""BENCH-02-R4-R2 native Orc real research specialists, original R3 refusal tests."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import json
import pytest
import numpy as np

from cognitum import orc_science_data as science
from cognitum import orc_comparison as compare
from cognitum import orc_selection as choice
from cognitum.orc_r3_frozen import ResearchCohort, PROTOCOL_SHA,HOUR
from tools.orcbench02 import original_orc_r4r2 as r

def test_original_protocol_frozen_and_existing_R4_negative_report_preserved():
    p=r.protocol()
    assert p["schema"]=="cognitum.orc.bench02.r4.r2.full_original_specialists.v1"
    assert p["source_contract"]["only_original_git_archived_NOAA_byte_snapshots"]
    assert p["original_R3_protocol_sha256"]==PROTOCOL_SHA
    assert p["notes"].startswith("Existing baseline R4 heldout")
    assert r.blob((r.ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R4.md").read_bytes())==r.R4_REPORT_ORIGINAL_BLOB

def test_existing_science_source_split_remains_original_without_fixed_contract():
    x=r.source_bound("KSEA",1)
    raw=x["raw"];d=x["selection_kwargs"]
    plain=science.qualify(raw,site_id="KSEA",units=d["units"],
                          clock=d["clock"],provenance=d["provenance"])
    assert plain.fixed_research is None
    assert plain.identity != x["qualified"].identity
    old_split=science.split_chronological(plain)
    assert (old_split.train_stop,old_split.cal_stop,old_split.row_count)==(115,153,192)

@pytest.mark.parametrize("site,horizon",[
    ("KSEA",1),("KDEN",3),("KATL",6)])
def test_actual_original_source_and_five_lag_fixed_all_folds(site,horizon):
    x=r.source_bound(site,horizon)
    series=x["qualified"]
    frozen=x["fixed"]
    assert len(series.rows)==192
    assert frozen.station==site
    assert not frozen.execution_authorized
    assert frozen.first_capture_test_eligible==0
    assert frozen.original_noaa_sha256==r.protocol()["original_raw_sha256"][site]
    split=science.split_chronological(series)
    assert (split.train_stop,split.cal_stop)==(115,153)
    scaler=science.fit_train_scaler(series,split)
    for fold,expected in zip(("train","cal","test"),frozen.fold_pairs):
        original=science.prepare_forecasts(series,split,scaler,
            science.CandidateContract("statistical.ridge",series.units),
            fold=fold,horizon_ms=horizon*HOUR,lag_ms=HOUR)
        assert tuple((v.origin_ms,v.target_ms) for v in original.examples)==expected
    assert series.identity!=science.qualify(x["raw"],site_id=site,units=x["selection_kwargs"]["units"],
        clock=x["selection_kwargs"]["clock"],
        provenance=x["selection_kwargs"]["provenance"]).identity

def test_actual_original_propose_and_train_only_HDC_KAN_engines():
    x=r.fit_case("KSEA",1)
    m=x["model"]
    assert m.research_hdc and m.research_kan
    assert m.kan_snapshot_sha256==sha256(m.kan_snapshot).hexdigest()
    assert len(m.hdc_prototypes)==2
    assert set(m.methods)==set(r.METHODS)
    assert x["calibration"].selected_on=="cal"
    assert x["calibration"].source_identity==x["source"]["qualified"].identity
    for p in x["proposals"].values():
        assert type(p) is choice.Decision
        assert p.execution_authorized is False
        assert p.calibration_cohort_sha256==x["calibration"].cohort_sha256
        assert len(p.candidates)==7
        assert p.selection_basis in (
            "conservative_ridge_default","calibration_only_research_proposal",
            "calibration_only_reviewed_baseline","no_valid_calibration_decision",
            "resource_bounded_fallback")

def test_no_fake_provider_source_freshness_and_no_retroactive_first_capture():
    x=r.fit_case("KSEA",1)
    args={**x["source"]["selection_kwargs"],"source_current":lambda _:False}
    with pytest.raises(ValueError,match="stale scientific source"):
        choice.propose_forecast(x["source"]["raw"],model=x["model"],
              calibration=x["calibration"],policy=choice.SelectionPolicy(),**args)
    with pytest.raises(ValueError,match="unregistered"):
        replace(x["source"]["fixed"],first_capture_test_eligible=1)

def test_injected_original_cohort_hash_fails_closed():
    x=r.source_bound("KSEA",1)
    fixed=x["fixed"]
    corrupted=list(fixed.fold_pairs)
    corrupted[0]=corrupted[0][1:]
    with pytest.raises(ValueError,match="pair hash"):
        replace(fixed,fold_pairs=tuple(corrupted))

def test_mismatched_horizon_source_and_provenance_refused():
    x=r.source_bound("KSEA",1)
    with pytest.raises(ValueError,match="original R3"):
        replace(x["fixed"],horizon_ms=HOUR*3)
    with pytest.raises(ValueError,match="mismatch"):
        d=x["selection_kwargs"]
        science.qualify(x["raw"],site_id="KDEN",units=d["units"],clock=d["clock"],
                        provenance=d["provenance"],fixed_research=x["fixed"])
    split=science.split_chronological(x["qualified"])
    scaler=science.fit_train_scaler(x["qualified"],split)
    with pytest.raises(ValueError,match="horizon"):
        science.prepare_forecasts(x["qualified"],split,scaler,
            science.CandidateContract("statistical.ridge",x["qualified"].units),
            fold="test",horizon_ms=3*HOUR,lag_ms=HOUR)

def test_fixed_research_flag_never_grants_native_execution():
    x=r.source_bound("KDEN",1)
    assert not x["qualified"].fixed_research.execution_authorized
    assert x["fixed"].execution_authorized is False
    assert r.protocol()["scope_exclusions"]
