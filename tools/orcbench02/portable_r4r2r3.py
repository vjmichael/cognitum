"""R4-R2-R3: portable abstention using original Orc native selector and engines.

Research-only source-locked decision policy. Legacy default selector remains
unmodified when portable_near_tie_mae_kelvin=0. No new training or test tuning.
"""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha256,sha1
from math import floor, isfinite
from pathlib import Path
import argparse
import json
import numpy as np

from cognitum import orc_selection as selection
from cognitum import orc_comparison as comparison
from tools.orcbench02 import original_orc_r4r2 as old
from tools.orcbench02 import benchmark_r4 as r4
from tools.orcbench02.cohorts import canonical

ROOT=Path(__file__).resolve().parents[2]
ROOT_DOC=ROOT/"docs/research/orcgraph"
BASE_LOCK=ROOT_DOC/"ORCH01E_BENCH02_R4_R2_R3_PREREG.json"
AMEND_LOCK=ROOT_DOC/"ORCH01E_BENCH02_R4_R2_R3_RECEIPT_AMENDMENT.json"
BASE_GIT_BLOB="dcfc11361bee51507cbdbe99f73652755023eb27"
AMEND_GIT_BLOB="d62a05fabbbe5aa7490d046f20382f24d7973d0f"
HOUR=3600000
METHODS=tuple(comparison.METHODS)
ALL_POLICIES=("default","research_opt_in")

class Refusal(ValueError):pass

def need(ok,why):
    if not ok: raise Refusal(why)

def digest(o):
    return sha256(canonical(o)).hexdigest()

def blob(raw):
    return sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def prereg():
    base=BASE_LOCK.read_bytes();amended=AMEND_LOCK.read_bytes()
    need(blob(base)==BASE_GIT_BLOB and blob(amended)==AMEND_GIT_BLOB,
         "original portable scientific precommit or amendment altered")
    cfg=json.loads(base);adj=json.loads(amended)
    need(cfg["schema"]=="cognitum.orc.bench02.r4r2r3.portable_refusal.precommitted.v1"
         and adj["schema"].endswith("decimal_precision_amendment.v1")
         and adj["original_immutable_prereg_git_blob"]==BASE_GIT_BLOB
         and cfg["selection_policy"]["opt_in_value"]==1e-10
         and adj["unchanged_selector_near_tie_threshold_kelvin"]==1e-10
         and adj["superseding_scores_decimals"]==8
         and adj["superseding_quantum_kelvin"]==1e-8
         and cfg["original_total_retrospective_test_pairs"]==265,
         "altered fixed portable source and scoring rules")
    need(blob((ROOT_DOC/"ORCH01E_BENCH02_R4.md").read_bytes())==
         cfg["original_R4_negative_report_blob"],
         "historical negative R4 results altered")
    need(blob((ROOT_DOC/"ORCH01E_BENCH02_R4_R2_NATIVE_ARTIFACTS.json").read_bytes())==
         cfg["original_R4R2_native_receipt_file_blob"],
         "historical original native R4-R2 receipts altered")
    return cfg,adj

def opts():
    return {
        "default":selection.SelectionPolicy(portable_near_tie_mae_kelvin=1e-10),
        "research_opt_in":selection.SelectionPolicy(
            allow_research_proposals=True,
            max_evaluation_work_proxy=200_000,
            max_research_abstention_fraction=1.0,
            portable_near_tie_mae_kelvin=1e-10)}

def quantize(x):
    cfg,adjust=prereg()
    x=float(x)
    need(isfinite(x) and x>=0.,"invalid calibration numeric receipt")
    decimals=adjust["superseding_scores_decimals"]
    quantum=adjust["superseding_quantum_kelvin"]
    distance=abs((x/quantum-floor(x/quantum))-.5)*quantum
    need(distance>adjust["unchanged_boundary_refusal_margin_kelvin"],
         "calibration score too close to portable rounding boundary")
    return format(x,f".{decimals}f")

def portable_payload(site,h,source,model,calibration,decisions):
    cfg,_=prereg()
    original=source["source"]["original"]
    fixed=source["source"]["fixed"]
    cert={
        "schema":"cognitum.orc.bench02.r4r2r3.portable_source_bound_certificate.v1",
        "preregistered_git_blobs":[BASE_GIT_BLOB,AMEND_GIT_BLOB],
        "site":site,"horizon_hours":h,
        "R3_original_protocol_sha256":cfg["original_R3_prereg_sha256"],
        "R3_original_NOAA_SHA256":original["original_sha256"],
        "R3_original_cohort_sha256":fixed.original_r3_cohort_sha256,
        "R3_original_train_cal_test_clock_SHA256":list(fixed.fold_pair_sha256),
        "derived_original_weather_CSV_SHA256":fixed.derived_csv_sha256,
        "training_count":source["train_n"],
        "calibration_count":source["cal_n"],
        "method_inventory":list(model.methods),
        "calibration_numeric_receipts":{
            method:{"mae_kelvin_8dp":quantize(v.mae),"rmse_kelvin_8dp":quantize(v.rmse),
                    "n":v.n}
            for method,v in calibration.scores},
        "original_selection":{
            policy_name:{
                "policy_sha256":decision.policy_sha256,
                "status":decision.status,"selected":decision.selected,
                "selection_basis":decision.selection_basis,
                "reason_codes":list(decision.reasons),
                "calibration_cohort_sha256":decision.calibration_cohort_sha256,
                "calibration_n":decision.calibration_n,
                "calibration_skipped":decision.calibration_skipped,
                "candidate_eligibility": [
                    {"method":v.method,"eligible":v.eligible,
                     "reason_codes":list(v.reasons),
                     "work_proxy":v.evaluation_work_proxy,
                     "memory_proxy":v.model_memory_proxy_bytes}
                    for v in decision.candidates]}
            for policy_name,decision in decisions.items()},
        "first_capture_eligible_test":0,
        "execution_authorized":False
    }
    need(cert["R3_original_NOAA_SHA256"]==
         cfg["original_raw_sha256"][site] and
         len(cert["method_inventory"])==7 and
         cert["method_inventory"]==list(METHODS),
         "source/method inventory changed")
    return cert

def original_fitted_case(site,h):
    cfg,_=prereg()
    need(site in old.SITES and h in old.HORIZONS,"original fixed R3 station/horizon replaced")
    native=old.fit_case(site,h) # accepted original native HDC/KAN/SSM fit unchanged
    original=native["source"]
    kw=original["selection_kwargs"]
    decisions={
       key:selection.propose_forecast(
           original["raw"],model=native["model"],
           calibration=native["calibration"],policy=policy,**kw)
       for key,policy in opts().items()}
    need(all(not d.execution_authorized for d in decisions.values()),
         "research decision must not grant host execution")
    cert=portable_payload(site,h,native,native["model"],native["calibration"],decisions)
    return native,decisions,cert

def freeze_case(site,h):
    native,decisions,cert=original_fitted_case(site,h)
    model=native["model"];f=native["source"]["fixed"]
    return {
       "task":f"{site}_{h}h",
       "portable_receipt_sha256":digest(cert),
       "portable_source_bound_receipt":cert,
       "full_precision_original_decisions":{k:asdict(v) for k,v in decisions.items()},
       "unmodified_native_trained_model_sha256":model.identity,
       "unmodified_KAN_snapshot_sha256":model.kan_snapshot_sha256,
       "unmodified_HDC_prototype_sha256":digest(model.hdc_prototypes),
       "unmodified_original_calibration_SHA256":native["calibration"].cohort_sha256,
       "original_test_pair_SHA256":f.fold_pair_sha256[2],
       "calibration_selected_only":True,
       "heldout_scored":False
    }

def freeze():
    cfg,_=prereg()
    cases={f"{site}_{h}h":freeze_case(site,h)
           for site in old.SITES for h in old.HORIZONS}
    need(len(cases)==9,"not all source-bound 9 cases frozen")
    return {
       "schema":"cognitum.orc.bench02.r4r2r3.portable_original_frozen.v1",
       "R4R2R3_precommit_git_blobs":[BASE_GIT_BLOB,AMEND_GIT_BLOB],
       "native_model_fitting_algorithm_unchanged":True,
       "historical_negative_baselines_unchanged":True,
       "heldout_scored":False,
       "original_test_cases":9,
       "source_locked_cases":cases,
       "portable_aggregate_decision_sha256":digest({
           task:v["portable_receipt_sha256"] for task,v in cases.items()
       })
    }

def compare_frozen(original,new):
    # Canonical serialization tolerates Python tuple vs JSON list, but
    # NEVER tolerates any altered decision, source ID or original raw model.
    need(digest(original)==digest(new),"altered frozen original numerical decision")
    need(original["portable_aggregate_decision_sha256"]==
         new["portable_aggregate_decision_sha256"],
         "portable exact source-bound decision identity altered")

def metric(y,p):
    y=np.asarray(y,dtype=float);p=np.asarray(p,dtype=float)
    need(len(y)>0 and len(y)==len(p) and np.isfinite(y).all() and
         np.isfinite(p).all(),"unmatched original predictions")
    e=y-p
    return {"n":int(len(y)),
            "mae":float(np.mean(np.abs(e))),
            "rmse":float(np.sqrt(np.mean(e*e)))}

def score(stored):
    fresh=freeze()
    compare_frozen(stored,fresh)
    cases=[];predictions=[]
    for site in old.SITES:
        for h in old.HORIZONS:
            key=f"{site}_{h}h"
            native,decisions,cert=original_fitted_case(site,h)
            original=native["source"]
            model=native["model"];series=original["qualified"]
            from cognitum import orc_comparison as comp
            test=comp._matched(series,model.scaler,"test",h*HOUR,HOUR,
                ("statistical.ridge","research.ssm","research.kan","research.hdc"))
            clocks=tuple((r.origin_ms,r.target_ms) for r in test.examples)
            need(clocks==original["fixed"].fold_pairs[2],
                 "original R3 test matched origins changed")
            prior_r4_test=r4.batch(original["original"],h,"test")
            need(clocks==tuple(tuple(x) for x in prior_r4_test["clocks"]),
                 "original historical R4 baseline clocks changed")
            previous_fit=r4.fit(r4.batch(original["original"],h,"train"),h)
            ridge=r4.predict(previous_fit,prior_r4_test)["direct_ridge"]
            y=np.asarray([q.target for q in test.examples],dtype=float)
            need(np.allclose(y,prior_r4_test["y"],rtol=0,atol=1e-10),
                 "accepted original target temperature changed")
            native_forecast,counters=comp._predict(model,test)
            allpred={"original_R4_direct_ridge":ridge,**native_forecast}
            for name,decision in decisions.items():
                if decision.status=="ABSTAIN":
                    need(decision.selected is None,"ambiguous/invalid method did not abstain")
                    continue
                audit=selection.evaluate_frozen_proposal(
                    decision,original["raw"],model=model,
                    calibration=native["calibration"],policy=opts()[name],
                    **original["selection_kwargs"])
                require_name=decision.selected
                need(audit.method==require_name and audit.n==len(y)
                   and abs(audit.selected_rmse-metric(y,native_forecast[require_name])["rmse"])<=1e-10,
                   "original Orc heldout frozen decision not independently reproduced")
                allpred["original_orc_"+name]=native_forecast[require_name].copy()
            scores={name:metric(y,p) for name,p in allpred.items()}
            base=scores["original_R4_direct_ridge"]
            gains={name:{
                "signed_rmse_gain_kelvin":base["rmse"]-v["rmse"],
                "fractional_rmse_gain":(base["rmse"]-v["rmse"])/max(base["rmse"],1e-12)}
                for name,v in scores.items()}
            cases.append({
                "task":key,"origin_n":len(y),
                "original_noaa_sha256":original["original"]["original_sha256"],
                "portable_receipt_sha256":digest(cert),
                "original_R3_test_cohort_sha256":original["fixed"].fold_pair_sha256[2],
                "unmodified_original_Fitted_identity":model.identity,
                "original_selection_status":{name:{
                    "status":d.status,"selected":d.selected,"basis":d.selection_basis,
                    "raw_original_decision_sha256":d.decision_sha256,
                    "reason_codes":list(d.reasons)}
                    for name,d in decisions.items()},
                "all_native_model_metrics":scores,
                "signed_gains_vs_prior_R4_ridge":gains,
                "native_counters":counters,
                "strict_first_capture_test_origins":0,
                "source_model_execution_authorized":False})
            for i,(origin,target) in enumerate(clocks):
                predictions.append({
                    "task":key,"origin_ms":origin,"target_ms":target,
                    "target_kelvin":float(y[i]),
                    "native_method_predictions_kelvin":{
                        n:float(p[i]) for n,p in allpred.items()}})
    need(len(cases)==9 and len(predictions)==265,"missing original R3 heldout forecasts")
    methods=["original_R4_direct_ridge",*METHODS,
             "original_orc_default","original_orc_research_opt_in"]
    summ={}
    for method in methods:
        gains=[case["signed_gains_vs_prior_R4_ridge"][method]["fractional_rmse_gain"]
            for case in cases if method in case["all_native_model_metrics"]]
        missing=[case["task"] for case in cases if method not in case["all_native_model_metrics"]]
        summ[method]={
            "reported":len(gains),"abstained_cases":missing,
            "wins":sum(q>1e-10 for q in gains),
            "losses":sum(q < -1e-10 for q in gains),
            "ties":sum(abs(q)<=1e-10 for q in gains),
            "reported_only_macro":float(np.mean(gains)) if gains else None,
            "complete_nine_case_macro":len(gains)==9}
    return {
        "schema":"cognitum.orc.bench02.r4r2r3.original_native_portability_score.v1",
        "original_R3_R4_R4R2_scientific_results_preserved":True,
        "original_model_algorithms_unchanged":True,
        "original_orc_propose_forecast_invoked":True,
        "portable_aggregate_decision_sha256":fresh["portable_aggregate_decision_sha256"],
        "site_horizon_cases":9,"matched_heldout_origins":265,
        "original_first_capture_eligible_origins":0,
        "historical_publication_proven":False,
        "installed_MEL_authorized":False,
        "cases":cases,"matched_native_forecasts":predictions,"methods":summ}

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=("freeze","score"),required=True)
    p.add_argument("--decisions",required=True)
    p.add_argument("--results")
    args=p.parse_args(argv)
    if args.phase=="freeze":
        result=freeze()
        with Path(args.decisions).open("x",encoding="utf-8",newline="\n") as fh:
            json.dump(result,fh,sort_keys=True,indent=2)
            fh.write("\n")
        print(json.dumps({"phase":"freeze","cases":9,
           "portable_decision_sha256":result["portable_aggregate_decision_sha256"],
           "no_heldout_scoring":True}))
    else:
        need(args.results,"results path needed")
        d=json.loads(Path(args.decisions).read_bytes())
        result=score(d)
        with Path(args.results).open("x",encoding="utf-8",newline="\n") as fh:
            json.dump(result,fh,sort_keys=True,indent=2)
            fh.write("\n")
        print(json.dumps({"phase":"score","cases":9,"rows":265,
            "portable_decision_sha256":result["portable_aggregate_decision_sha256"],
            "research_only":True,"native_KAN_HDC_SSM_unchanged":True}))

if __name__=="__main__":
    main()
