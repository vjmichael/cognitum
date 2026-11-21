"""Bounded synthetic ORCH-01E choice evidence; not physical ridge validation."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import perf_counter
import argparse
import json

from cognitum import orc_comparison as comparison, orc_selection as selector
from cognitum import orc_science_data as science
from runpy import run_path

# Load the already-accepted repository-local 01D synthetic generator by its
# exact path. The standalone tools/ directory is not a Python package.
raw_synthetic = run_path(
    str(Path(__file__).resolve().parent.parent / "orc01d" / "synthetic_evidence.py"),
    run_name="orc01e_shared_fixture")["raw_synthetic"]

STEP=60_000


def scenario(name):
    raw=raw_synthetic(scenario=name)
    prov=science.Provenance("syntheticGenerator","synthetic:orc01e/"+name,
                            sha256(raw).hexdigest(),"unknown","declared")
    series=science.qualify(raw,site_id="orc01e_"+name,
                          units=science.Units("water_level","m"),
                          clock=science.Clock(nominal_interval_ms=STEP),
                          provenance=prov)
    started=perf_counter()
    fitted=comparison.fit_train(series,horizon_ms=STEP,lag_ms=STEP,
                                 research_kan=True,research_hdc=True)
    cal=comparison.calibrate(series,fitted)
    fit_seconds=perf_counter()-started
    inputs=dict(site_id=series.site_id,units=series.units,clock=series.clock,
                provenance=prov,source_current=lambda source:True,
                model=fitted,calibration=cal)
    policy=selector.SelectionPolicy()
    before=perf_counter()
    choice=selector.propose_forecast(raw,policy=policy,**inputs)
    select_seconds=perf_counter()-before
    assert choice.status=="PROPOSED_OFFLINE"
    assert not choice.research_only and not choice.execution_authorized
    holdout=selector.evaluate_frozen_proposal(choice,raw,policy=policy,**inputs)
    assert choice.decision_sha256==holdout.decision_sha256
    abstain=selector.propose_forecast(raw,policy=selector.SelectionPolicy(
            max_evaluation_work_proxy=1),**inputs)
    assert abstain.status=="ABSTAIN" and abstain.selected is None
    user=selector.UserOverride("train_mean","synthetic_operator",
                                "explicit baseline review")
    override=selector.propose_forecast(raw,policy=policy,override=user,**inputs)
    assert override.selected=="train_mean" and not override.execution_authorized
    return {
        "source_sha256":prov.raw_sha256,
        "source_identity":series.identity,
        "calibration_only_proposal":asdict(choice),
        "after_frozen_decision_test_audit":asdict(holdout),
        "budget_refusal":{"status":abstain.status,"reasons":abstain.reasons},
        "unauthenticated_user_override":{
            "selected":override.selected,
            "execution_authorized":override.execution_authorized,
            "decision_sha256":override.decision_sha256},
        "fit_and_calibration_seconds_this_runner":fit_seconds,
        "selection_seconds_this_runner":select_seconds,
        "synthetic_no_physical_or_operator_attestation":True
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    opt=parser.parse_args()
    reports={name:scenario(name) for name in
             ("oscillatory_synthetic","shifted_synthetic")}
    payload={
        "schema":"orc01e.synthetic_selection.v1",
        "classification":"SYNTHETIC_OFFLINE_NOT_INDEPENDENT_RIDGE_OR_USER_BENCHMARK",
        "source_script":"tools/orc01e/selection_evidence.py",
        "scenarios":reports,
        "no_mel_authorization":True,
        "cost_proxy_not_measured_ram_or_compute_budget":True,
        "model_frozen_before_test_scores":True
    }
    result=json.dumps(payload,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if len(result)>100_000:raise ValueError("oversize evidence")
    Path(opt.output).write_text(result,encoding="utf-8",newline="\n")
    for name,report in reports.items():
        c=report["calibration_only_proposal"]
        h=report["after_frozen_decision_test_audit"]
        print(name,c["selected"],"test n",h["n"],"signed RMSE gain vs ridge",
              h["signed_rmse_gain_vs_ridge"])


if __name__=="__main__":
    main()
