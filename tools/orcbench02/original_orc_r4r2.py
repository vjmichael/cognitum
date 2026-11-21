"""BENCH-02-R4-R2 — actual original Orc decision + native research KAN/HDC.

Exact original R3 NOAA bytes, all original 115/38/39 UTC cohorts, no
retrieval or post-hoc tuning. This is still retrospective: no original
public-availability signatures, no real installed MEL or graph scheduling.
"""
from __future__ import annotations
from dataclasses import asdict
from hashlib import sha1,sha256
from io import StringIO
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np

from cognitum import orc_science_data as data
from cognitum import orc_comparison as compare
from cognitum import orc_selection as select
from cognitum.orc_r3_frozen import ResearchCohort,HOUR,PROTOCOL_SHA
from tools.orcbench02 import benchmark_r4 as original_r4
from tools.orcbench02.cohorts import source_rows as original_rows, canonical

ROOT=Path(__file__).resolve().parents[2]
PRE=ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R4_R2_PREREG.json"
SITES=("KSEA","KDEN","KATL")
HORIZONS=(1,3,6)
R4_R2_PROTOCOL_BLOB="2a746c1737627183fab924466dffb5bf4b034014"
R4_REPORT_ORIGINAL_BLOB="5dc4fa1f980fc7678371cba78dbfdbdfe09fb651"
R4_BASELINE_SCRIPT_BLOB="5ad4c5967ac4c0b44df5cf400bea970054941c73"
METHODS=("persistence","train_mean","direct_ridge","timeaware_ssm",
         "ssm_kan","ssm_hdc","ssm_kan_hdc")
POLICIES=("default","research_opt_in")

class Refusal(ValueError): pass

def require(test,why):
    if not test: raise Refusal(why)

def blob(raw):
    return sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()

def hashed(item):
    return sha256(canonical(item)).hexdigest()

def protocol():
    raw=PRE.read_bytes()
    require(blob(raw)==R4_R2_PROTOCOL_BLOB,"R4-R2 preregistration has changed")
    p=json.loads(raw)
    require(p["schema"]=="cognitum.orc.bench02.r4.r2.full_original_specialists.v1"
       and p["sites"]==list(SITES) and p["horizons_hours"]==list(HORIZONS)
       and p["fold_hours"]==[115,38,39]
       and p["lags_required_hours"]==[0,1,3,6,24]
       and p["original_R3_protocol_sha256"]==PROTOCOL_SHA,
       "R4-R2 frozen method or study cohort changed")
    require(blob((ROOT/"docs/research/orcgraph/ORCH01E_BENCH02_R4.md").read_bytes())
         ==R4_REPORT_ORIGINAL_BLOB,"original R4 negative-results report changed")
    require(blob((ROOT/"tools/orcbench02/benchmark_r4.py").read_bytes())
         ==R4_BASELINE_SCRIPT_BLOB,"original R4 direct ridge benchmark altered")
    require(not p["source_contract"]["only_original_git_archived_NOAA_byte_snapshots"] is False,
            "R3 original source protection weakened")
    return p

def source_bound(site,h):
    """Independently replay the R3 source and construct a fixed 192-row Orc CSV."""
    p=protocol()
    require(site in SITES and h in HORIZONS,"site/horizon replaced")
    original=original_r4.site_data(site) # original raw hash and derived R3 cohort independently replayed
    cohort=original["cohort"]
    receipt=json.loads((original_r4.DATA/(site+"-receipt.json")).read_bytes())
    raw=(original_r4.DATA/(site+"-original.json")).read_bytes()
    require(original["original_sha256"]==p["original_raw_sha256"][site] and
            hashed(cohort)==p["original_cohort_sha256"][site],
            "original R3 source/cohort identity was modified")
    sr=original_rows(raw,site,
        capture_start_ms=receipt["capture_started_ms"],
        capture_end_ms=receipt["capture_completed_ms"],
        sha256_pin=original["original_sha256"])
    grouping={}
    for v in sr:
        grouping.setdefault(v["hour_bucket_ms"],[]).append(v)
    output=StringIO(newline="")
    writer=csv.writer(output,lineterminator="\n")
    writer.writerow(("timestamp_ms","available_ms","value","observed","observation_id"))
    start=cohort["source_clock_start_inclusive_ms"]
    for i in range(192):
        end=start+(i+1)*HOUR
        members=grouping.get(end-HOUR,[])
        if len(members)==1 and members[0]["has_temperature"]:
            v=members[0]
            value=format(v["temperature_kelvin"],".15g")
            # Receipt after bucket end is NOT allowed as present-time feature.
            available=max(end,v["receipt_ms"])
            seen="1"
        else:
            value="";seen="0";available=end
        writer.writerow((end,available,value,seen,f"obs{i:03d}"))
    csv_bytes=output.getvalue().encode("utf-8")
    folds=cohort["horizons"][HORIZONS.index(h)]["folds"]
    tags=("train","calibration","test")
    fixed=ResearchCohort(
        station=site,original_noaa_sha256=original["original_sha256"],
        original_r3_cohort_sha256=hashed(cohort),
        derived_csv_sha256=sha256(csv_bytes).hexdigest(),
        horizon_ms=h*HOUR,
        fold_pairs=tuple(tuple(tuple(pair) for pair in folds[t][
            "retrospective_origin_target_clock_pairs"]) for t in tags),
        fold_pair_sha256=tuple(folds[t]["retrospective_cohort_sha256"] for t in tags))
    prov=data.Provenance("NOAA_AWC",
        f"https://aviationweather.gov/api/data/metar?ids={site}&format=json&hours=240",
        sha256(csv_bytes).hexdigest(),
        rights_status="unknown",unit_evidence="declared")
    units=data.Units("temperature","K");clock=data.Clock(nominal_interval_ms=HOUR)
    qualified=data.qualify(csv_bytes,site_id=site,units=units,clock=clock,
                           provenance=prov,fixed_research=fixed)
    def current(x):
        return x.identity==qualified.identity and x.fixed_research==fixed
    args=dict(site_id=site,units=units,clock=clock,provenance=prov,
              source_current=current,fixed_research=fixed)
    return {"site":site,"horizon":h,"raw":csv_bytes,"qualified":qualified,
            "selection_kwargs":args,"original":original,
            "fixed":fixed,"cohort":cohort}

def research_policy():
    return select.SelectionPolicy(allow_research_proposals=True,
        max_evaluation_work_proxy=200_000,
        max_research_abstention_fraction=1.0)

def fit_case(site,h):
    source=source_bound(site,h)
    series=source["qualified"]
    model=compare.fit_train(series,horizon_ms=h*HOUR,lag_ms=HOUR,
                            research_kan=True,research_hdc=True)
    cal=compare.calibrate(series,model)
    require(model.research_kan and model.research_hdc and
            model.kan_snapshot is not None and model.kan_snapshot_sha256==
            sha256(model.kan_snapshot).hexdigest() and
            len(model.hdc_prototypes or ())==2,
            "original native HDC/KAN train-only specialist fit absent")
    kwargs=source["selection_kwargs"]
    proposals={
        "default":select.propose_forecast(source["raw"],model=model,calibration=cal,
             policy=select.SelectionPolicy(),**kwargs),
        "research_opt_in":select.propose_forecast(source["raw"],model=model,calibration=cal,
             policy=research_policy(),**kwargs)}
    require(all(v.execution_authorized is False for v in proposals.values()),
            "offline selection cannot authorize MEL execution")
    original_cal=compare._matched(series,model.scaler,"cal",h*HOUR,HOUR,
                     ("statistical.ridge","research.ssm","research.kan","research.hdc"))
    original_train=compare._matched(series,model.scaler,"train",h*HOUR,HOUR,
                     ("statistical.ridge","research.ssm","research.kan","research.hdc"))
    expected_cal=source["fixed"].fold_pairs[1]
    require(tuple((x.origin_ms,x.target_ms) for x in original_cal.examples)==expected_cal,
            "actual Orc 01D model saw different calibration origins")
    return {"source":source,"model":model,"calibration":cal,
            "proposals":proposals,"train_n":len(original_train.examples),
            "cal_n":len(original_cal.examples)}

def frozen_case(site,h):
    x=fit_case(site,h);s=x["source"];m=x["model"]
    result={
        "task":f"{site}_{h}h","site":site,"horizon_hours":h,
        "original_noaa_sha256":s["original"]["original_sha256"],
        "original_r3_cohort_sha256":hashed(s["cohort"]),
        "derived_R3_orc_source_sha256":sha256(s["raw"]).hexdigest(),
        "R3_train_pairs_sha256":s["fixed"].fold_pair_sha256[0],
        "R3_cal_pairs_sha256":s["fixed"].fold_pair_sha256[1],
        "R3_test_pairs_sha256":s["fixed"].fold_pair_sha256[2],
        "native_orc_trained_model_sha256":m.identity,
        "native_kan_snapshot_sha256":m.kan_snapshot_sha256,
        "native_hdc_train_prototype_sha256":hashed(m.hdc_prototypes),
        "train_origin_n":x["train_n"],"cal_origin_n":x["cal_n"],
        "calibration_model_sha256":x["calibration"].model_identity,
        "calibration_cohort_sha256":x["calibration"].cohort_sha256,
        "calibration_methods":list(x["calibration"].methods),
        "calibration_scores":{key:asdict(v) for key,v in x["calibration"].scores},
        "native_original_propose_forecast_invoked":True,
        "native_specialists_trained_only_on_original_train":True,
        "selected_prior_to_heldout":{
            key:asdict(decision) for key,decision in x["proposals"].items()},
        "heldout_labels_not_evaluated":True}
    return result

def freeze():
    protocol()
    cases={f"{site}_{h}h":frozen_case(site,h)
           for site in SITES for h in HORIZONS}
    require(len(cases)==9,"frozen original study missing sites")
    out={"schema":"cognitum.orc.bench02.r4.r2.native_frozen_decisions.v1",
         "R4_R2_original_prereg_git_blob":R4_R2_PROTOCOL_BLOB,
         "R3_original_protocol_sha256":PROTOCOL_SHA,
         "source_original_R4_negative_results_unmodified":True,
         "native_original_orc_propose_forecast":True,
         "native_KAN_and_HDC_fitted":True,
         "previous_R4_heldout_data_already_viewed":True,
         "real_historical_first_public_availability_attested":False,
         "all_model_fits_train_only_and_selections_cal_only":True,
         "heldout_labels_scored":False,"cases":cases}
    out["decision_sha256"]=hashed(out)
    return out

def metric(y,p):
    y=np.asarray(y);p=np.asarray(p)
    require(len(y)>0 and len(p)==len(y) and np.isfinite(y).all() and np.isfinite(p).all(),
            "unequal/invalid original source-matched forecasts")
    d=y-p
    return {"n":len(y),"mae":float(np.mean(np.abs(d))),
            "rmse":float(np.sqrt(np.mean(d*d)))}

def score(original_freeze):
    original=freeze()
    require(original_freeze==original,
            "original HDC/KAN fit or calibration proposals changed after freeze")
    rows=[];cases=[]
    for site in SITES:
        for h in HORIZONS:
            name=f"{site}_{h}h";f=original["cases"][name]
            x=fit_case(site,h);s=x["source"];model=x["model"]
            series=s["qualified"]
            holdout=compare._matched(series,model.scaler,"test",h*HOUR,HOUR,
                ("statistical.ridge","research.ssm","research.kan","research.hdc"))
            native_preds,counters=compare._predict(model,holdout)
            expected=s["fixed"].fold_pairs[2]
            pairs=tuple((q.origin_ms,q.target_ms) for q in holdout.examples)
            require(pairs==expected and
                len(pairs)==len(s["original"]["cohort"]["horizons"][HORIZONS.index(h)]["folds"]["test"]["retrospective_origin_target_clock_pairs"]),
                "heldout cohorts not identical to original R3 source")
            original_r4_test=original_r4.batch(s["original"],h,"test")
            require(pairs==tuple(tuple(p) for p in original_r4_test["clocks"]),
                    "full specialist test origin mismatch vs accepted R4")
            previous_r4_fit=original_r4.fit(original_r4.batch(s["original"],h,"train"),h)
            r4_reference=original_r4.predict(previous_r4_fit,original_r4_test)["direct_ridge"]
            truth=np.asarray([q.target for q in holdout.examples],dtype=float)
            require(np.allclose(truth,original_r4_test["y"],rtol=0,atol=1e-9),
                    "original R4 historical measured target changed")
            predictions={"original_R4_direct_ridge":r4_reference,**native_preds}
            original_decisions={}
            for key,decision in x["proposals"].items():
                if decision.status=="ABSTAIN":
                    require(decision.selected is None,"abstaining selector chose a method")
                    original_decisions[key]={"status":"ABSTAIN","selected":None,
                                             "reason":list(decision.reasons)}
                    continue
                select_policy=(select.SelectionPolicy() if key=="default" else research_policy())
                verified=select.evaluate_frozen_proposal(
                    decision,s["raw"],model=model,calibration=x["calibration"],
                    policy=select_policy,**s["selection_kwargs"])
                need_key=decision.selected
                require(need_key in native_preds and verified.method==need_key and
                    verified.n==len(truth) and
                    math.isclose(verified.selected_rmse,
                        metric(truth,native_preds[need_key])["rmse"],abs_tol=1e-9),
                    "original frozen selection numerical audit differed")
                predictions["original_orc_"+key]=native_preds[need_key].copy()
                original_decisions[key]={
                    "status":decision.status,"selected":need_key,
                    "decision_sha256":decision.decision_sha256,
                    "real_original_evaluate_frozen_proposal_called":True}
            native_methods={key:metric(truth,p) for key,p in predictions.items()}
            benchmark_ridge=native_methods["original_R4_direct_ridge"]
            gains={k:{
                "signed_rmse_gain_kelvin":benchmark_ridge["rmse"]-v["rmse"],
                "signed_mae_gain_kelvin":benchmark_ridge["mae"]-v["mae"],
                "fractional_rmse_gain":(benchmark_ridge["rmse"]-v["rmse"])/max(
                    benchmark_ridge["rmse"],1e-12)}
                for k,v in native_methods.items()}
            cases.append({
                "task":name,"site":site,"horizon_hours":h,"unit":"K",
                "R3_test_original_cohort_sha256":s["fixed"].fold_pair_sha256[2],
                "tested_origin_count":len(truth),"frozen_decision_sha256":original["decision_sha256"],
                "actual_orc_proposals":original_decisions,
                "all_matched_native_metrics":native_methods,
                "all_signed_gains_vs_accepted_R4_direct_ridge":gains,
                "actual_native_KAN_HDC_counters":counters,
                "first_capture_bounded_origin_count":0,
                "historical_provider_first_availability_signed":False})
            for i,(origin,target) in enumerate(pairs):
                rows.append({
                    "task":name,"origin_ms":origin,"target_ms":target,
                    "target_kelvin":float(truth[i]),
                    "original_NOAA_sha256":s["original"]["original_sha256"],
                    "predictions_kelvin":{k:float(v[i]) for k,v in predictions.items()},
                    "selection":{k:v.get("selected") for k,v in original_decisions.items()}})
    require(len(cases)==9 and len(rows)==265,
            "original R3 nine cases and all 265 retrospective predictions mandatory")
    methods=["original_R4_direct_ridge",*METHODS,
             "original_orc_default","original_orc_research_opt_in"]
    summaries={}
    for method in methods:
        values=[x["all_signed_gains_vs_accepted_R4_direct_ridge"][method]["fractional_rmse_gain"]
                for x in cases if method in x["all_matched_native_metrics"]]
        abstains=[x["task"] for x in cases if method not in x["all_matched_native_metrics"]]
        eps=1e-10
        summaries[method]={
            "reported":len(values),"abstained_cases":abstains,
            "win":sum(a>eps for a in values),"loss":sum(a < -eps for a in values),
            "tie":sum(abs(a)<=eps for a in values),
            "macro_signed_fractional_rmse_gain":float(np.mean(values)) if values else None,
            "complete_nine_case_macro":len(values)==9}
    return {
        "schema":"cognitum.orc.bench02.r4.r2.original_native_comparison.v1",
        "prior_r4_retrospective_source_and_results_preserved":True,
        "frozen_calibration_decision_sha256":original["decision_sha256"],
        "R4_R2_prereg_original_git_blob":R4_R2_PROTOCOL_BLOB,
        "source_cases":9,"original_matched_test_origins":len(rows),
        "models_fitted_original_native_KAN_HDC_SSM":True,
        "direct_original_propose_and_frozen_evaluate_called":True,
        "all_noaa_historical_publication_attested":False,
        "strict_first_capture_test_origins":0,
        "production_MEL_authorized":False,
        "all_task_summaries":summaries,"cases":cases,
        "original_rows_and_predictions":rows}

def main(argv=None):
    arg=argparse.ArgumentParser()
    arg.add_argument("--phase",choices=("freeze","score"),required=True)
    arg.add_argument("--decisions",required=True)
    arg.add_argument("--output")
    a=arg.parse_args(argv)
    if a.phase=="freeze":
        frozen=freeze()
        with Path(a.decisions).open("x",encoding="utf-8",newline="\n") as file:
            json.dump(frozen,file,indent=2,sort_keys=True);file.write("\n")
        print(json.dumps({"phase":"freeze","cases":9,"decision_sha256":frozen["decision_sha256"],
                          "heldout_scored":False,"native_propose_called":True}))
    else:
        require(a.output is not None,"original native heldout result path required")
        frozen=json.loads(Path(a.decisions).read_bytes())
        result=score(frozen)
        with Path(a.output).open("x",encoding="utf-8",newline="\n") as file:
            json.dump(result,file,indent=2,sort_keys=True);file.write("\n")
        print(json.dumps({"phase":"score","cases":9,"rows":len(result["original_rows_and_predictions"]),
                          "retrospective_only":True,"original_orc_select_called":True}))

if __name__=="__main__":
    main()
