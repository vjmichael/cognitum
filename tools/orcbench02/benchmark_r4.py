"""BENCH-02-R4 fixed-cohort retrospective comparison.

This is the R3-fold adapter for the *existing* Orc SelectionPolicy thresholds.
It is NOT a direct invocation of ORCH-01E propose_forecast, HDC/KAN evidence,
historical publication proof, authorized installed MEL, or live forecasting.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np

from cognitum.orc_selection import SelectionPolicy
from tools.orcbench02.cohorts import build_site, canonical, source_rows, HOUR, lock as r3_lock

ROOT = Path(__file__).resolve().parents[2]
R4_PATH = ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R4_PREREG.json"
DATA = ROOT/"research_tests/orcbench02/r3_20261121"
SITE_ORDER = ("KSEA","KDEN","KATL")
HORIZONS = (1,3,6)
METHODS = ("direct_ridge","ridge_AR24","persistence","lag24_persistence",
           "train_mean","timeaware_ssm","orc_default","orc_expanded_classical")
EVALUATED = METHODS[:6]
ALLOWED_R4_GIT_BLOB = "1cf7c2ae11e09130ef036f3812ebfb849235f26b"
R3_SHA = "fd0b6a372ee5cd9ee8870ad20c475261460a069daf4fd52f56e8dcc2961a5104"

class Refusal(ValueError):
    """Frozen source, unchanged cohort or calibration grant is invalid."""

def need(ok, why):
    if not ok:
        raise Refusal(why)

def digest(obj):
    return sha256(canonical(obj)).hexdigest()

def git_blob(raw):
    from hashlib import sha1
    return sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def policy():
    original = R4_PATH.read_bytes()
    need(git_blob(original)==ALLOWED_R4_GIT_BLOB, "R4 protocol original Git blob altered")
    p=json.loads(original)
    need(p["schema"]=="cognitum.orc.bench02.r4.frozen.20261120.v1" and
         p["prereg_site_order"]==list(SITE_ORDER) and
         p["horizons_hours"]==list(HORIZONS) and
         p["fold_hours"]==[115,38,39] and
         p["lag_hour_indices"]==[0,1,3,6,24] and
         p["R3_frozen_protocol_sha256"]==R3_SHA and
         p["guardrails"]["strict_asof_first_capture_eligible_test_total"]==0 and
         p["guardrails"]["no_claim_of_full_Orc_KAN_HDC_specialists"], "R4 frozen science contract altered")
    sel=SelectionPolicy()
    q=p["models"]["orc_default"]
    need(sel.min_calibration_examples==q["min_calibration_examples"] and
         sel.max_calibration_skipped_fraction==q["max_calibration_skipped_fraction"] and
         sel.min_absolute_mae_improvement==q["min_absolute_mae_improvement_K"] and
         sel.min_relative_mae_improvement==q["min_relative_mae_improvement"] and
         not sel.allow_research_proposals,"Orc original baseline policy diverged")
    need(tuple(p["models"]["orc_default"]["candidate_order"]) ==
         ("direct_ridge","persistence","train_mean","timeaware_ssm") and
         tuple(p["models"]["orc_expanded_classical"]["candidate_order"]) ==
         ("direct_ridge","persistence","train_mean","timeaware_ssm","lag24_persistence","ridge_AR24"),"selection inventory mutated")
    return p

def site_data(site):
    p=policy()
    need(site in SITE_ORDER, "unpreregistered station")
    root=DATA
    raw=(root/f"{site}-original.json").read_bytes()
    receipt=json.loads((root/f"{site}-receipt.json").read_bytes())
    cohort=json.loads((root/f"{site}-cohort.json").read_bytes())
    need(sha256(raw).hexdigest()==p["R3_raw_sha256"][site] and
         receipt["source_sha256"]==p["R3_raw_sha256"][site] and
         receipt["source_bytes"]==len(raw) and
         receipt["station"]==site and
         receipt["preregistration_sha256"]==R3_SHA and
         receipt["source_url"]==p["R3_original_archive_prefix"].replace(
             p["R3_original_archive_prefix"],
             f"https://aviationweather.gov/api/data/metar?ids={site}&format=json&hours=240"),
         "source bytes/receipt/site custody differs")
    need(sha256(canonical(cohort)).hexdigest()==p["R3_cohort_sha256"][site] and
         receipt["cohort_sha256"]==p["R3_cohort_sha256"][site],
         "original derived cohort mutated")
    independent=build_site(raw,site,
        capture_start_ms=receipt["capture_started_ms"],
        capture_end_ms=receipt["capture_completed_ms"],
        sha256_pin=p["R3_raw_sha256"][site])
    need(independent==cohort and cohort["preregistered_protocol_sha256"]==R3_SHA,
         "original R3 fixed as-of cohort replay mismatch")
    need(cohort["fold_hours"]==[115,38,39] and
         [x["forecast_horizon_hours"] for x in cohort["horizons"]]==list(HORIZONS),
         "fold or horizon drift")
    need(all(h["folds"]["test"]["reason_counts"]["first_capture_bounded_eligible"]==0
             for h in cohort["horizons"]),"unexpected strict as-of admission")
    bins=defaultdict(list)
    for item in source_rows(raw,site,
            capture_start_ms=receipt["capture_started_ms"],
            capture_end_ms=receipt["capture_completed_ms"],
            sha256_pin=p["R3_raw_sha256"][site]):
        bins[item["hour_bucket_ms"]].append(item)
    temperature={}
    for when,vals in bins.items():
        if len(vals)==1 and vals[0]["has_temperature"]:
            temperature[when]=vals[0]["temperature_kelvin"]
    return {"site":site,"temperature":temperature,"cohort":cohort,
            "original_sha256":sha256(raw).hexdigest(),
            "source_rows":cohort["original_source_rows"]}

def batch(source,h,fold):
    """No new sample eligibility decisions. Reuse exact R3 clocks and hashes."""
    cohort=source["cohort"]
    arm=cohort["horizons"][HORIZONS.index(h)]["folds"][fold]
    clocks=arm["retrospective_origin_target_clock_pairs"]
    need(len(clocks)==arm["reason_counts"]["retrospective_receipt_proxy_eligible"] and
         digest(clocks)==arm["retrospective_cohort_sha256"],
         "R3 originally frozen paired origin hash mismatch")
    start=cohort["source_clock_start_inclusive_ms"]
    temps=source["temperature"]
    xs,ys=[],[]
    for origin,target in clocks:
        oi=(origin-start)//HOUR-1
        ti=(target-start)//HOUR-1
        need(0<=oi<192 and 0<=ti<192 and ti-oi==h,"origin/horizon clock altered")
        features=[]
        for lag in (0,1,3,6,24):
            tick=start+(oi-lag)*HOUR
            need(tick in temps and tick <= origin,"R3 feature clock or source missing")
            features.append(temps[tick])
        ttick=start+ti*HOUR
        need(ttick in temps and ttick>origin-HOUR,
             "R3 target missing or wrong future timestamp")
        xs.append(features)
        ys.append(temps[ttick])
    need(len(xs)>0 and all(math.isfinite(z) for row in xs for z in row)
         and all(math.isfinite(z) for z in ys),"empty/nonfinite frozen R3 cohort")
    return {"clocks":clocks,
            "x":np.asarray(xs,dtype=np.float64),
            "y":np.asarray(ys,dtype=np.float64),
            "hash":arm["retrospective_cohort_sha256"],
            "fold_hours":arm["all_origin_hours"]}

def fit_ridge(train,lags,alpha):
    need(lags in ((0,1),(0,1,3,6,24)) and alpha==1.0,"unfrozen ridge features/penalty")
    indices=[(0,1,3,6,24).index(x) for x in lags]
    x=train["x"][:,indices]
    mu=np.mean(x,axis=0)
    sig=np.std(x,axis=0)
    sig=np.where(sig>1e-9,sig,1.)
    scaled=(x-mu)/sig
    design=np.column_stack((scaled,np.ones(len(x))))
    regular=np.diag(np.r_[np.ones(len(indices))*alpha,0.])
    beta=np.linalg.solve(design.T@design+regular,design.T@train["y"])
    need(np.isfinite(beta).all(),"ill-conditioned ridge fit")
    return {"lag_indices":indices,"mu":mu,"sig":sig,"beta":beta}

def ridge_predict(fit,batch):
    z=(batch["x"][:,fit["lag_indices"]]-fit["mu"])/fit["sig"]
    return np.column_stack((z,np.ones(len(z))))@fit["beta"]

def fit(train,h):
    need(h in HORIZONS and len(train["y"])>=25,"insufficient training-only examples")
    mean=float(np.mean(train["y"]))
    origin=train["x"][:,0]
    taus=(1,4,16,64)
    scores=[float(np.mean(np.abs(
          train["y"]-(mean+math.exp(-h/tau)*(origin-mean))))) for tau in taus]
    tau=taus[min(range(len(taus)),key=lambda i:(scores[i],i))]
    return {"direct":fit_ridge(train,(0,1),1.0),
            "ar24":fit_ridge(train,(0,1,3,6,24),1.0),
            "train_mean":mean,"tau_hours":tau,"horizon":h,
            "train_clock_sha256":train["hash"],"train_n":len(train["y"])}

def predict(fitted,batch):
    x=batch["x"]
    origin=x[:,0]
    mean=fitted["train_mean"]
    tau=fitted["tau_hours"]
    outputs={
        "direct_ridge":ridge_predict(fitted["direct"],batch),
        "ridge_AR24":ridge_predict(fitted["ar24"],batch),
        "persistence":origin.copy(),
        "lag24_persistence":x[:,4].copy(),
        "train_mean":np.full(len(origin),mean),
        "timeaware_ssm":mean+math.exp(-fitted["horizon"]/tau)*(origin-mean)}
    need(tuple(outputs)==EVALUATED and all(
         len(v)==len(origin) and np.isfinite(v).all() for v in outputs.values()),
         "unmatched or nonfinite candidate forecasts")
    return outputs

def metrics(y,pred):
    need(len(y)>0 and len(y)==len(pred) and np.isfinite(pred).all() and
         np.isfinite(y).all(),"unmatched score/refusal")
    e=y-pred
    return {"n":len(e),"mae":float(np.mean(np.abs(e))),
            "rmse":float(np.sqrt(np.mean(e*e)))}

def select(fitted,cal_preds,cal,kind):
    p=policy()
    cfg=p["models"][kind]
    original=SelectionPolicy()
    nominal=cal["fold_hours"]-fitted["horizon"]
    missing=nominal-len(cal["y"])
    need(0<nominal and 0<=missing<=nominal,"calibration eligibility changed")
    scores={method:metrics(cal["y"],cal_preds[method])
            for method in cfg["candidate_order"]}
    reasons=[]
    if len(cal["y"]) < original.min_calibration_examples:
        reasons.append("insufficient_calibration_examples")
    if missing/nominal > original.max_calibration_skipped_fraction:
        reasons.append("excessive_calibration_missing_or_unavailable")
    chosen=None
    if not reasons:
        chosen="direct_ridge"
        ridge=scores[chosen]["mae"]
        steps=p["static_work_proxy"]
        eligible=[]
        for k in cfg["candidate_order"]:
            if k==chosen:continue
            gain=ridge-scores[k]["mae"]
            if (gain >= original.min_absolute_mae_improvement and
                gain/max(ridge,1e-12)>=original.min_relative_mae_improvement):
                eligible.append(k)
        if eligible:
            chosen=min(eligible,key=lambda k:(
                scores[k]["mae"],steps[k],cfg["candidate_order"].index(k)))
    return {"status":"PROPOSED_OFFLINE" if chosen is not None else "ABSTAIN",
            "selected":chosen,"reasons":reasons,
            "cohort_sha256":cal["hash"],"calibration_n":len(cal["y"]),
            "calibration_skipped":missing,"calibration_metrics":scores,
            "selector":"faithful_baseline_threshold_adapter_not_direct_propose_forecast",
            "full_HDC_KAN_specialists_evaluated":False}

def prepare():
    p=policy()
    research={}
    for station in SITE_ORDER:
        data=site_data(station)
        for h in HORIZONS:
            train=batch(data,h,"train")
            cal=batch(data,h,"calibration")
            fitted=fit(train,h)
            cpred=predict(fitted,cal)
            selections={key:select(fitted,cpred,cal,key)
                        for key in ("orc_default","orc_expanded_classical")}
            research[f"{station}_{h}h"]={
                "site":station,"horizon_hours":h,
                "original_source_sha256":data["original_sha256"],
                "training_origin_sha256":train["hash"],
                "calibration_origin_sha256":cal["hash"],
                "test_origin_sha256":data["cohort"]["horizons"][HORIZONS.index(h)]
                    ["folds"]["test"]["retrospective_cohort_sha256"],
                "train_count":len(train["y"]),"calibration_count":len(cal["y"]),
                "fitted_ssm_tau_hours":fitted["tau_hours"],
                "fitted_train_only_mean_kelvin":fitted["train_mean"],
                "selectors":selections,
                "all_heldout_labels_unscored":True}
    need(len(research)==9,"nine frozen tasks not prepared")
    out={"schema":"cognitum.orc.bench02.r4.frozen_decisions.v1",
         "R4_preregistration_git_blob":ALLOWED_R4_GIT_BLOB,
         "R3_preregistration_sha256":R3_SHA,
         "test_labels_scored":False,"models_fitted_only_train":True,
         "policy_adapter_not_original_propose_forecast":True,
         "HDC_KAN_specialists_not_evaluated":True,
         "cases":research}
    out["decision_sha256"]=digest(out)
    return out

def dependence(y,ref,pred,clock_pairs):
    """Actual contiguous hourly non-overlapping paired MAE residual blocks."""
    p=policy()["paired_dependence"]
    n=len(y)
    gain=np.abs(y-ref)-np.abs(y-pred)
    width=p["block_width_hourly_contiguous_origins"]
    ordered=[row[0] for row in clock_pairs]
    blocks=[]
    first=0
    for i in range(1,n+1):
        if i==n or ordered[i]!=ordered[i-1]+HOUR:
            for j in range(first,i-width+1,width):
                blocks.append(float(np.mean(gain[j:j+width])))
            first=i
    if len(blocks)<p["minimum_nonoverlapping_blocks"]:
        return {"status":"REFUSED_INSUFFICIENT_CONTIGUOUS_BLOCKS",
                "blocks":len(blocks),"paired_mean_mae_gain":float(np.mean(gain)),
                "descriptive_interval_95":None,"conditional_guarantee":False}
    rng=np.random.default_rng(p["seed"])
    a=np.asarray(blocks)
    boot=np.asarray([np.mean(a[rng.integers(0,len(a),len(a))])
                    for _ in range(p["bootstrap_repetitions"])])
    return {"status":"DESCRIPTIVE_UNCORRECTED_PAIRED_BLOCK_BOOTSTRAP",
            "blocks":len(blocks),"paired_mean_mae_gain":float(np.mean(gain)),
            "descriptive_interval_95":[float(np.quantile(boot,.025)),
                                       float(np.quantile(boot,.975))],
            "conditional_guarantee":False}

def score(frozen):
    expected=prepare()
    need(frozen==expected and frozen.get("decision_sha256")==digest({
        k:v for k,v in expected.items() if k!="decision_sha256"}),
        "frozen calibration source/selection was changed after fitting")
    results=[]
    rows=[]
    for station in SITE_ORDER:
        data=site_data(station)
        for h in HORIZONS:
            name=f"{station}_{h}h"
            f=expected["cases"][name]
            train=batch(data,h,"train")
            test=batch(data,h,"test")
            fitted=fit(train,h)
            preds=predict(fitted,test)
            for selector in ("orc_default","orc_expanded_classical"):
                selected=f["selectors"][selector]["selected"]
                if selected is not None:
                    preds[selector]=preds[selected].copy()
            reference=preds["direct_ridge"]
            raw_metrics={name:metrics(test["y"],p) for name,p in preds.items()}
            need(all(v["n"]==len(test["y"]) for v in raw_metrics.values()),
                 "silently intersected heldout cohort")
            paired={method:dependence(test["y"],reference,pred,test["clocks"])
                    for method,pred in preds.items() if method!="direct_ridge"}
            gains={name:{
                "signed_rmse_gain_kelvin":raw_metrics["direct_ridge"]["rmse"]-m["rmse"],
                "signed_mae_gain_kelvin":raw_metrics["direct_ridge"]["mae"]-m["mae"],
                "dimensionless_relative_rmse_gain":(
                    raw_metrics["direct_ridge"]["rmse"]-m["rmse"])/
                    max(raw_metrics["direct_ridge"]["rmse"],1e-12)}
                for name,m in raw_metrics.items()}
            result={
                "task":name,"station":station,"horizon_hours":h,
                "physical_unit":"K","frozen_decision_sha256":frozen["decision_sha256"],
                "test_cohort_sha256":test["hash"],"test_eligible_origins":len(test["y"]),
                "train_origin_n":len(train["y"]),"calibration_origin_n":f["calibration_count"],
                "selected_methods":{key:f["selectors"][key]["selected"] for key in (
                    "orc_default","orc_expanded_classical")},
                "all_heldout_metrics":raw_metrics,"all_signed_gains":gains,
                "paired_dependence_sensitivity":paired,
                "retrospective_AWC_receipt_proxy_only":True,
                "strict_first_capture_eligible_origins":0,
                "real_historical_publication_attested":False,
                "full_HDC_KAN_orc_evaluated":False}
            results.append(result)
            for i,(origin,target) in enumerate(test["clocks"]):
                rows.append({"task":name,"origin_ms":origin,"target_ms":target,
                             "observed_target_kelvin":float(test["y"][i]),
                             "predictions_kelvin":{k:float(pred[i]) for k,pred in preds.items()},
                             "frozen_selection":result["selected_methods"],
                             "source_sha256":data["original_sha256"]})
    need(len(results)==9 and len(rows)==sum(c["test_eligible_origins"] for c in results),
         "missing case or original heldout row")
    summary={}
    for name in METHODS:
        values=[r["all_signed_gains"][name]["dimensionless_relative_rmse_gain"]
                for r in results if name in r["all_signed_gains"]]
        e=policy()["tie_epsilon"]
        summary[name]={"cases":len(values),
            "wins":sum(x>e for x in values),"losses":sum(x < -e for x in values),
            "ties":sum(abs(x)<=e for x in values),
            "macro_mean_fractional_rmse_gain":float(np.mean(values))}
    return {"schema":"cognitum.orc.bench02.r4.retrospective_result.v1",
            "R4_preregistration_git_blob":ALLOWED_R4_GIT_BLOB,
            "frozen_decision_sha256":frozen["decision_sha256"],
            "source_cases":9,"total_heldout_rows":len(rows),
            "summaries":summary,"cases":results,
            "full_original_heldout_predictions":rows,
            "strict_first_capture_eligible_test_origins":0,
            "historical_publication_attested":False,
            "direct_existing_Orc_propose_forecast_invoked":False,
            "native_HDC_KAN_specialists_evaluated":False,
            "installed_MEL_execution_authorized":False}

def main(argv=None):
    cli=argparse.ArgumentParser()
    cli.add_argument("--phase",choices=("freeze","score"),required=True)
    cli.add_argument("--decisions",required=True)
    cli.add_argument("--output")
    args=cli.parse_args(argv)
    if args.phase=="freeze":
        result=prepare()
        path=Path(args.decisions)
        with path.open("x",encoding="utf-8",newline="\n") as f:
            json.dump(result,f,sort_keys=True,indent=2)
            f.write("\n")
        print(json.dumps({"phase":"freeze","cases":len(result["cases"]),
                          "decision_sha256":result["decision_sha256"],
                          "no_heldout_scoring":True}))
    else:
        need(args.output,"explicit results path required")
        frozen=json.loads(Path(args.decisions).read_text(encoding="utf-8"))
        result=score(frozen)
        with Path(args.output).open("x",encoding="utf-8",newline="\n") as f:
            json.dump(result,f,sort_keys=True,indent=2)
            f.write("\n")
        print(json.dumps({"phase":"score","cases":len(result["cases"]),
                          "rows":result["total_heldout_rows"],
                          "frozen_decision_sha256":result["frozen_decision_sha256"],
                          "research_only":True,"HDC_KAN_evaluated":False}))

if __name__=="__main__":
    main()
