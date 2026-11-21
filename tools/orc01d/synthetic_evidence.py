"""ORCH-01D deterministic *synthetic* model comparison evidence, not real data.

This is research-only test instrumentation: it never grants MEL operations.
It emits the actual heldout predictions AFTER calibration selection plus source,
fit and cohort hashes for independent reproducibility and negative criticism.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from math import cos, sin
from pathlib import Path
import argparse
import json
import sys

from cognitum import orc_science_data as s, orc_comparison as c

STEP=60_000
START=1_700_000_000_000
N=480


def raw_synthetic(*, scenario):
    if scenario not in ("oscillatory_synthetic","shifted_synthetic"):
        raise ValueError("unreviewed synthetic scenario")
    out=["timestamp_ms,available_ms,value,observed,observation_id"]
    for i in range(N):
        now=START+i*STEP
        value=10 + .3*sin(i/4) + .2*cos(i/15) + .007*i
        if scenario=="shifted_synthetic" and i>=N*4//5:
            value+=4.0
        is_missing=i in (340,415,416) if scenario=="shifted_synthetic" else False
        delay=i in (280,331,401) if scenario=="shifted_synthetic" else False
        out.append(f"{now},{now+2*STEP if delay else now},"
                   f"{format(value,'.12g') if not is_missing else ''},"
                   f"{0 if is_missing else 1},obs{i}")
    return ("\n".join(out)+"\n").encode("ascii")


def profile(scenario):
    raw=raw_synthetic(scenario=scenario)
    provenance=s.Provenance("syntheticGenerator","synthetic:orc01d/"+scenario,
                            sha256(raw).hexdigest(),"unknown","declared")
    series=s.qualify(raw,site_id=scenario,units=s.Units("water_level","m"),
                     clock=s.Clock(nominal_interval_ms=STEP),
                     provenance=provenance)
    fitted=c.fit_train(series,horizon_ms=STEP,lag_ms=STEP,
                       research_kan=True,research_hdc=True)
    calibration=c.calibrate(series,fitted)
    audit=c.evaluate_holdout(series,fitted,calibration,block_size=4)
    names=("statistical.ridge","research.ssm","research.kan","research.hdc")
    batch=c._matched(series,fitted.scaler,"test",STEP,STEP,names)
    prediction,counters=c._predict(fitted,batch)
    original=set(fitted.methods)
    if set(prediction)!=original:
        raise RuntimeError("candidate mismatched before output")
    selected=calibration.selected
    rows=[{
        "origin_ms":item.origin_ms,
        "target_ms":item.target_ms,
        "measured_target":item.target,
        "predictions":{name:float(prediction[name][i]) for name in fitted.methods},
    } for i,item in enumerate(batch.examples)]
    assert len(rows)==dict(audit.test_scores)["direct_ridge"].n
    assert len(rows)+sum(v for _,v in audit.test_skipped)==audit.test_eligible_origins
    return {
        "scenario":scenario,
        "data_kind":"deterministically_generated_synthetic_no_original_instrument",
        "not_independent_orc_vs_ridge_benchmark":True,
        "source_sha256":provenance.raw_sha256,
        "source_identity":series.identity,
        "data_bytes":len(raw),
        "n_observations":len(series.rows),
        "horizon_ms":STEP,"lag_ms":STEP,
        "train_cutoff_ms":fitted.train_cutoff_ms,
        "model_sha256":fitted.identity,
        "kan_research_snapshot_sha256":fitted.kan_snapshot_sha256,
        "hdc_dimension":256,
        "methods":fitted.methods,
        "calibration_method":selected,
        "calibration_scores":{name:asdict(score) for name,score in calibration.scores},
        "calibration_cohort_sha256":calibration.cohort_sha256,
        "test_scores":{name:asdict(score) for name,score in audit.test_scores},
        "test_cohort_sha256":audit.test_cohort_sha256,
        "signed_selected_rmse_gain_vs_direct_ridge":audit.selected_rmse_gain_vs_ridge,
        "signed_selected_mae_gain_vs_direct_ridge":audit.selected_mae_gain_vs_ridge,
        "selected_dependent_interval":asdict(audit.selected_interval),
        "ridge_dependent_interval":asdict(audit.ridge_interval),
        "paired_test_gain":asdict(audit.paired_gain),
        "cohort_counters":{"eligible_origins":audit.test_eligible_origins,
                           "skipped":dict(audit.test_skipped),
                           "research_fallback":counters},
        "work_proxy":{"train_eligible_observations":fitted.scaler.count,
                      "cal_scored_examples":calibration.scores[0][1].n,
                      "test_scored_examples":len(rows),
                      "method_count":len(fitted.methods),
                      "prediction_rows":len(rows)*len(fitted.methods)},
        "test_rows":rows,
        "limitations":audit.limitations,
        "selection_on_test":False,
        "execution_authorized":False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    opts=ap.parse_args()
    cases=tuple(profile(x) for x in ("oscillatory_synthetic","shifted_synthetic"))
    payload={
        "schema":"orc.orch01d.synthetic-evidence.v1",
        "classification":"SYNTHETIC_ONLY_NOT_REAL_INDEPENDENT_BENCHMARK",
        "source_replay_script":"tools/orc01d/synthetic_evidence.py",
        "scenarios":cases,
        "outcome_rule":"report signed positive/negative ridge gains unchanged; method fixed by cal",
        "no_authority_or_original_sensor_attestation":True,
    }
    encoded=json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if len(encoded)>500_000:
        raise ValueError("oversize synthetic evidence artifact")
    Path(opts.output).write_text(encoded,encoding="utf-8",newline="\n")
    print("ORCH-01D synthetic source-locked evidence",len(cases),
          "scenarios; bytes",len(encoded))
    for case in cases:
        print(case["scenario"],"cal-selected",case["calibration_method"],
              "test RMSE gain vs ridge",case["signed_selected_rmse_gain_vs_direct_ridge"],
              "holdout n",len(case["test_rows"]))
    return 0


if __name__=="__main__":
    sys.exit(main())
