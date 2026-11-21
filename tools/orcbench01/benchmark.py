"""BENCH-01: preregistered real-observation Orc vs direct/strong ridge evaluation.

UCI 501 raw excerpts already source-pinned in Cognitum's R4 research tree.
This is historical measured TEMP, *not* a new blinded external acquisition.
Original publication availability and original time-zone metadata are absent;
same-event availability and UTC+08 are identified surrogate assumptions.
No calibration/test labels select a model after the test cohort is exposed.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import StringIO
from pathlib import Path
from time import perf_counter
import argparse
import csv
import json
import math
import tracemalloc

import numpy as np

from cognitum import orc_comparison as comp
from cognitum import orc_science_data as source
from cognitum import orc_selection as choice
from cognitum.research.ssm_timeaware import ridge_fit, ridge_predict


ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"research_tests/ssm_postnative04/data"
SITES=("Changping","Dingling","Guanyuan")
HOURS=(1,6,24)
N_ROWS=1920
HOUR_MS=3_600_000
TZ=timezone(timedelta(hours=8))
SOURCE_URL="https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data"
POLICY_BASE=choice.SelectionPolicy()
POLICY_RESEARCH=choice.SelectionPolicy(
    allow_research_proposals=True,
    max_evaluation_work_proxy=200_000,
    max_research_abstention_fraction=1.0)
CLASSICAL=("direct_ridge","persistence","train_mean",
           "timeaware_ssm","seasonal_naive24","ridge_AR24")


def require(ok,why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return sha256(raw).hexdigest()


def acquire_site(site: str):
    """Only source-locked original bytes; Kelvin and UTC conversion are explicit."""
    require(site in SITES,"fixed site preregistration")
    manifest=json.loads((DATA/"sources.json").read_text(encoding="utf-8"))
    custody=json.loads((DATA/"acquisition.json").read_text(encoding="utf-8"))
    entry=next(e for e in manifest["entries"] if e["site"]==site)
    require(manifest["license"]=="CC BY 4.0" and
            custody["license"]=="CC BY 4.0" and
            custody["dataset_id"]=="UCI-501" and
            custody["sites"][site]==entry["excerpt_sha256"],
            "original UCI attribution and custody mismatch")
    require(manifest["outer_archive_sha256"]==
            custody["source_archive_sha256"] and
            manifest["nested_zip_sha256"]==custody["nested_archive_sha256"],
            "original archive lineage mismatch")
    original=(DATA/(site+".csv")).read_bytes()
    require(digest(original)==entry["excerpt_sha256"] and
            len(original)==entry["excerpt_bytes"],"original site bytes changed")
    parsed=list(csv.DictReader(StringIO(original.decode("utf-8"))))
    require(len(parsed)==6144 and entry["rows"]==6144 and
            tuple(parsed[0])==tuple(entry["columns"]) and
            entry["missing_target_temp"]==0,"source site schema/window changed")
    captured=[]
    out=StringIO(newline="")
    writer=csv.writer(out,lineterminator="\n")
    writer.writerow(("timestamp_ms","available_ms","value","observed","observation_id"))
    for i,item in enumerate(parsed[:N_ROWS]):
        at=datetime(int(item["year"]),int(item["month"]),int(item["day"]),
                    int(item["hour"]),tzinfo=TZ)
        tick=int(at.timestamp()*1000)
        value=item["TEMP"]
        measured=value not in ("","NA","nan")
        converted=(float(value)+273.15) if measured else None
        if measured:
            require(math.isfinite(converted) and converted>0,
                    "Kelvin conversion produced nonphysical result")
        # Explicit assumption, NOT verified historical publication time.
        writer.writerow((tick,tick,format(converted,".12g") if measured else "",
                         1 if measured else 0,"obs"+str(i)))
        captured.append(tick)
    require(len(captured)==N_ROWS and all(
        b-a==HOUR_MS for a,b in zip(captured,captured[1:])),
        "monotonic original source clock and UTC+08 assumption")
    raw=out.getvalue().encode("utf-8")
    prov=source.Provenance(
        "UCI501",SOURCE_URL+"#"+site,digest(raw),
        rights_status="publisher_reported",
        unit_evidence="publisher_documented")
    series=source.qualify(raw,site_id=site,units=source.Units("temperature","K"),
                          clock=source.Clock(nominal_interval_ms=HOUR_MS),
                          provenance=prov)
    require(not series.has_missing,"preregistered TEMP source completeness changed")
    provenance={
        "dataset":"UCI 501 Beijing Multi-Site Air Quality",
        "doi":"10.24432/C5RK5G",
        "attribution":"Song Chen; UCI Machine Learning Repository",
        "license":"CC BY 4.0",
        "original_excerpt_sha256":digest(original),
        "original_raw_bytes":len(original),
        "source_archive_sha256":custody["source_archive_sha256"],
        "derived_orc_sha256":prov.raw_sha256,
        "site":site,"time_interpretation":"ASSUMED fixed Beijing UTC+08",
        "observation_availability":"ASSUMED same-time, NOT historically attested",
        "units":"Original TEMP Celsius converted +273.15 to Kelvin",
        "upstream_sensor_signature_verified":False,
        "previously_used_in_cognitum_ssm_research":True,
    }
    return raw,series,prov,provenance


def same_source(trusted):
    return lambda proposed: proposed.identity==trusted.identity


def prepared(s,model,fold,hours):
    return comp._matched(s,model.scaler,fold,hours*HOUR_MS,HOUR_MS,
                         ("statistical.ridge","research.ssm",
                          "research.kan","research.hdc"))


def _history(s, origins, history=25):
    by_time={r.timestamp_ms:r for r in s.rows}
    features=[];good=[];miss=0
    for row in origins:
        t=row.origin_ms
        source_rows=[by_time.get(t-k*HOUR_MS) for k in range(history)]
        if any(a is None or not a.observed or a.available_ms>t
               for a in source_rows):
            miss+=1
            continue
        features.append([a.value for a in source_rows]+[1.])
        good.append(row)
    return np.asarray(features,dtype=float),tuple(good),miss


def train_strong(s,model,train):
    x,examples,excluded=_history(s,train.examples)
    require(x.ndim==2 and x.shape[1]==26 and len(examples)>=300,
            "training-only seasonal/AR24 history insufficient")
    values=np.asarray([e.target for e in examples],dtype=float)
    learned=ridge_fit(np.column_stack((x[:,:24],np.ones(len(x)))),values)
    return learned,excluded,len(examples)


def strong_predictions(s,fit,batch,fold):
    x,actuals,missing=_history(s,batch.examples)
    if fold in ("cal","test"):
        require(missing==0 and len(actuals)==len(batch.examples) and
                np.array_equal(np.asarray([e.origin_ms for e in actuals]),
                               np.asarray([e.origin_ms for e in batch.examples])),
                "strong baselines cannot silently intersect evaluation cohort")
    return {
        "seasonal_naive24":x[:,24].copy(),
        "ridge_AR24":ridge_predict(fit,np.column_stack((x[:,:24],np.ones(len(x)))))
    },missing


def metric(truth,pred):
    return asdict(comp._metric(truth,np.asarray(pred,dtype=float)))


def cal_classical(cal_truth,cal_preds):
    names=tuple(x for x in CLASSICAL if x in cal_preds)
    require(names==CLASSICAL, "frozen strong classical method list")
    scores={name:metric(cal_truth,cal_preds[name]) for name in CLASSICAL}
    frozen=min(CLASSICAL,key=lambda name:(scores[name]["mae"],
                                         CLASSICAL.index(name)))
    return frozen,scores


def case(site,hours,*,research_kan=True,research_hdc=True):
    """Exactly nine preregistered fixed site/horizon tasks; no cherry-picking."""
    require(site in SITES and hours in HOURS,"unreviewed task")
    tracemalloc.start()
    start=perf_counter()
    raw,s,provenance,publisher=acquire_site(site)
    source_seconds=perf_counter()-start
    work=perf_counter()
    fitted=comp.fit_train(s,horizon_ms=hours*HOUR_MS,
                          lag_ms=HOUR_MS,
                          research_kan=research_kan,
                          research_hdc=research_hdc)
    calibration=comp.calibrate(s,fitted)
    train=prepared(s,fitted,"train",hours)
    cal=prepared(s,fitted,"cal",hours)
    test=prepared(s,fitted,"test",hours)
    ar_model,ar_dropped,ar_train=train_strong(s,fitted,train)
    train_seconds=perf_counter()-work
    # Original mathematically coupled candidates computed only from fitted train.
    c_predictions,_=comp._predict(fitted,cal)
    cal_extra,cal_missing=strong_predictions(s,ar_model,cal,"cal")
    require(cal_missing==0,"calibration seasonal controls must match")
    cal_preds={**c_predictions,**cal_extra}
    _,cal_truth=comp._xy(cal)
    classical_selected,classical_scores=cal_classical(cal_truth,cal_preds)
    # Both policies frozen before test is materialized by this function.
    params=dict(site_id=site,units=s.units,clock=s.clock,provenance=provenance,
                source_current=same_source(s),model=fitted,
                calibration=calibration)
    proposal_t=perf_counter()
    proposals={
        "default":choice.propose_forecast(raw,policy=POLICY_BASE,**params),
        "research_opt_in":choice.propose_forecast(raw,policy=POLICY_RESEARCH,**params)
    }
    proposal_seconds=perf_counter()-proposal_t
    frozen={
        key:{
            "status":v.status,
            "selected":v.selected,
            "basis":v.selection_basis,
            "decision_sha256":v.decision_sha256,
            "reasons":v.reasons,
            "policy_sha256":v.policy_sha256,
            "calibration_cohort_sha256":v.calibration_cohort_sha256,
        } for key,v in proposals.items()
    }
    # Nothing after this point can alter any prechosen selection.
    trial_t=perf_counter()
    p_predictions,_=comp._predict(fitted,test)
    extra,t_missing=strong_predictions(s,ar_model,test,"test")
    require(t_missing==0,"strong baseline test cohort not matched")
    test_preds={**p_predictions,**extra}
    _,truth=comp._xy(test)
    require(all(len(v)==len(truth) and np.isfinite(v).all()
                for v in test_preds.values()),"unmatched or nonfinite forecasts")
    test_metrics={name:metric(truth,v) for name,v in test_preds.items()}
    cal_metric_name="direct_ridge"
    chosen_results={}
    for name,p in proposals.items():
        if p.status=="ABSTAIN":
            chosen_results[name]={"status":"ABSTAIN","selected":None}
            continue
        checked=choice.evaluate_frozen_proposal(p,raw,
                          policy=(POLICY_BASE if name=="default" else POLICY_RESEARCH),
                          **params)
        require(checked.method==p.selected and
                checked.n==len(truth) and
                math.isclose(checked.selected_rmse,test_metrics[p.selected]["rmse"],
                             rel_tol=0,abs_tol=1e-9),
                "frozen method attribution failure")
        paired=comp._bootstrap(truth,test_preds["direct_ridge"],
                               test_preds[p.selected],
                               np.asarray([v.origin_ms for v in test.examples]),
                               HOUR_MS,24)
        chosen_results[name]={
            "status":p.status,"selected":p.selected,
            "signed_mae_gain_vs_ridge":checked.signed_mae_gain_vs_ridge,
            "signed_rmse_gain_vs_ridge":checked.signed_rmse_gain_vs_ridge,
            "paired_block_sensitivity":asdict(paired)}
    frozen_strong=classical_selected
    classical_paired=comp._bootstrap(truth,test_preds["direct_ridge"],
                                    test_preds[frozen_strong],
                                    np.asarray([v.origin_ms for v in test.examples]),
                                    HOUR_MS,24)
    original_cal=comp._cal_internal(s,fitted)
    cal_times=np.asarray([v.origin_ms for v in cal.examples],dtype=np.int64)
    test_times=np.asarray([v.origin_ms for v in test.examples],dtype=np.int64)
    selected=proposals["default"].selected
    dep=(asdict(comp._interval(cal_truth,cal_preds[selected],
        cal_times,truth,test_preds[selected],test_times,HOUR_MS,24))
        if selected is not None else {"status":"ABSTAIN"})
    score_seconds=perf_counter()-trial_t
    rows=[]
    for i,v in enumerate(test.examples):
        rows.append({
            "origin_ms":v.origin_ms,"target_ms":v.target_ms,
            "observed_temperature_K":v.target,
            "predictions_K":{name:float(y[i]) for name,y in test_preds.items()}
        })
    _,tracemalloc_peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    require(all(v["n"]==len(rows) for v in test_metrics.values()),
            "unmatched sample count")
    return {
        "task":site+"_"+str(hours)+"h",
        "site":site,"horizon_hours":hours,
        "source":publisher,
        "source_identity":s.identity,
        "source_sha256":provenance.raw_sha256,
        "model_sha256":fitted.identity,
        "kan_snapshot_sha256":fitted.kan_snapshot_sha256,
        "calibration_cohort_sha256":calibration.cohort_sha256,
        "test_cohort_sha256":comp._hash(tuple((v.origin_ms,v.target_ms)
                                           for v in test.examples)),
        "rows_total":len(s.rows),
        "train_origin_examples":len(train.examples),
        "calibration_origin_examples":len(cal.examples),
        "test_origin_examples":len(test.examples),
        "train_ar24_examples":ar_train,
        "train_ar24_insufficient_history":ar_dropped,
        "cal_skipped":dict(cal.skipped),
        "test_eligible_origins":test.eligible_origins,
        "test_skipped":dict(test.skipped),
        "selector_prior_to_test":frozen,
        "classical_selected_cal_only":frozen_strong,
        "classical_calibration_metrics":classical_scores,
        "all_heldout_metrics":test_metrics,
        "orc_frozen_heldout":chosen_results,
        "classical_frozen_heldout":{
            "selected":frozen_strong,
            "signed_mae_gain_vs_ridge":
               test_metrics["direct_ridge"]["mae"]-test_metrics[frozen_strong]["mae"],
            "signed_rmse_gain_vs_ridge":
               test_metrics["direct_ridge"]["rmse"]-test_metrics[frozen_strong]["rmse"],
            "paired_block_sensitivity":asdict(classical_paired),
        },
        "dependent_interval":dep,
        "source_parse_seconds_measured":source_seconds,
        "fit_and_calibration_seconds_measured":train_seconds,
        "proposal_seconds_measured":proposal_seconds,
        "score_holdout_seconds_measured":score_seconds,
        "python_tracemalloc_peak_bytes_partial_only":tracemalloc_peak,
        "memory_limitations":"tracemalloc misses native NumPy/BLAS allocations and total RSS",
        "full_heldout_predictions":rows,
        "same_time_availability_originally_verified":False,
        "real_source_new_to_existing_cognitum_research":False,
        "execution_authorized":False,
    }


def run():
    """Frozen order, all nine tasks; a failed task refuses all result promotion."""
    cases=[case(site,h) for site in SITES for h in HOURS]
    require(len(cases)==9 and len({v["task"] for v in cases})==9,
            "all original preregistered site/horizons mandatory")
    arms=("default","research_opt_in")
    summaries={}
    for arm in arms:
        vals=[row["orc_frozen_heldout"][arm]["signed_rmse_gain_vs_ridge"]
              for row in cases]
        summaries[arm]={
            "case_count":len(vals),
            "positive":sum(v>1e-12 for v in vals),
            "negative":sum(v< -1e-12 for v in vals),
            "ties":sum(abs(v)<=1e-12 for v in vals),
            "macro_mean_signed_rmse_gain_K":float(np.mean(vals)),
            "no_test_based_model_selection":True,
        }
    return {
        "schema":"orc.bench01.real_observations.v1",
        "source_class":"REAL HISTORICAL ORIGINAL EXCERPTS, not newly blind/acquired",
        "physical_quantity":"hourly air temperature converted Celsius to Kelvin",
        "sites":SITES,"horizon_hours":HOURS,
        "preregistered_protocol":
            "docs/research/orcgraph/ORCH01E_BENCH01_PREREG.md",
        "same_time_availability_is_an_unverified_historical_assumption":True,
        "timezone_fixed_UTC_plus_08_is_an_assumption":True,
        "owner_required_benchmark_not_claimed_to_prove_superiority":True,
        "results":cases,
        "macro_summary":summaries,
        "not_independent_original_sensor_publisher_signature":True,
        "not_unseen_source_site_transfer":True,
        "no_mel_grants_created":True,
        "human_ai_synergy_not_measured":True,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--summary",required=True)
    opts=parser.parse_args()
    payload=run()
    original=json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+"\n"
    require(len(original)<12_000_000,"bounded real benchmark artifact")
    Path(opts.output).write_text(original,encoding="utf-8",newline="\n")
    brief={k:v for k,v in payload.items() if k!="results"}
    brief["case_summary"]=[{
        "task":v["task"],
        "n":v["test_origin_examples"],
        "chosen_default":v["orc_frozen_heldout"]["default"]["selected"],
        "chosen_research":v["orc_frozen_heldout"]["research_opt_in"]["selected"],
        "default_rmse_gain_K":v["orc_frozen_heldout"]["default"]["signed_rmse_gain_vs_ridge"],
        "research_rmse_gain_K":v["orc_frozen_heldout"]["research_opt_in"]["signed_rmse_gain_vs_ridge"],
        "ridge_rmse_K":v["all_heldout_metrics"]["direct_ridge"]["rmse"],
        "strongest_cal_classical":v["classical_selected_cal_only"],
        "strongest_classical_rmse_K":v["all_heldout_metrics"][v["classical_selected_cal_only"]]["rmse"],
    } for v in payload["results"]]
    Path(opts.summary).write_text(json.dumps(brief,indent=2,sort_keys=True,
                                            allow_nan=False)+"\n",
                                  encoding="utf-8",newline="\n")
    for v in brief["case_summary"]:
        print(v["task"],"n",v["n"],"direct Ridge",v["ridge_rmse_K"],
              "Orc",v["chosen_default"],"signed RMSE improvement",
              v["default_rmse_gain_K"],"research",v["research_rmse_gain_K"])


if __name__=="__main__":
    main()
