"""Independent four-platform numerical and source identity verifier.

This is a separate successor of all four native jobs. No per-run self-stamp
can qualify cross-platform portability. Historical data remain retrospective.
"""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from math import isclose,fsum,sqrt,isfinite
import argparse
import json
import os
import xml.etree.ElementTree as ET

from tools.orcbench02.portable_r4r2r3 import (
    prereg,digest,BASE_GIT_BLOB,AMEND_GIT_BLOB,METHODS)

EXPECTED={
  "orcbench02-r4r2r3-ubuntu-latest-py3.11",
  "orcbench02-r4r2r3-ubuntu-latest-py3.13",
  "orcbench02-r4r2r3-windows-latest-py3.11",
  "orcbench02-r4r2r3-windows-latest-py3.13",
}
REQUIRED_FILES={
 "bench02-r4r2r3-pretest.xml","bench02-r4r2r3-verified.xml",
 "bench02-r4r2r3-decisions.json","bench02-r4r2r3-results.json",
 "source-blobs.txt","source-sha.txt"
}
CASE_ORDER=[f"{site}_{h}h" for site in ("KSEA","KDEN","KATL") for h in (1,3,6)]
METHODS_REQUIRED={"original_R4_direct_ridge",*METHODS}

def require(ok,reason):
    if not ok:raise ValueError("Independent 4-platform qualification REFUSED: "+reason)

def tests(data):
    root=ET.fromstring(data)
    records=list(root.iter("testcase"))
    issues=[x for x in records if x.find("failure") is not None or
            x.find("error") is not None or x.find("skipped") is not None]
    require(records and not issues,"original JUnit contains missing or nonpassing tests")
    return len(records),tuple((x.get("classname"),x.get("name")) for x in records)

def read_all(root,sha):
    folders=[x for x in root.iterdir() if x.is_dir()]
    require({x.name for x in folders}==EXPECTED,"missing/duplicate native Windows or Linux target")
    data={}
    for f in sorted(folders):
        require({x.name for x in f.iterdir()}>=REQUIRED_FILES,
                f"missing native original artifact in {f.name}")
        row={"name":f.name,"source_sha":(f/"source-sha.txt").read_text().strip(),
             "source_blobs":(f/"source-blobs.txt").read_text().strip().splitlines(),
             "decision":json.loads((f/"bench02-r4r2r3-decisions.json").read_bytes()),
             "result":json.loads((f/"bench02-r4r2r3-results.json").read_bytes())}
        for step in ("pretest","verified"):
            n,keys=tests((f/f"bench02-r4r2r3-{step}.xml").read_bytes())
            row[step+"_n"]=n
            row[step+"_keys"]=keys
        require(row["source_sha"]==sha, "native run source SHA is not exact expected original head")
        d=row["decision"];s=row["result"]
        require(d["schema"]=="cognitum.orc.bench02.r4r2r3.portable_original_frozen.v1"
                and d["R4R2R3_precommit_git_blobs"]==[BASE_GIT_BLOB,AMEND_GIT_BLOB],
                "portable prereg pinned content changed")
        require(s["portable_aggregate_decision_sha256"]==d["portable_aggregate_decision_sha256"],
                "full heldout result not bound to frozen decision")
        require(s["site_horizon_cases"]==9 and s["matched_heldout_origins"]==265
                and len(s["matched_native_forecasts"])==265 and
                len(s["cases"])==9,"missing original full nine cases or 265 rows")
        require(not s["historical_publication_proven"]
                and not s["installed_MEL_authorized"]
                and s["original_first_capture_eligible_origins"]==0,
                "unapproved history/source/host promotion")
        require(set(d["source_locked_cases"])==set(CASE_ORDER)
                and [x["task"] for x in s["cases"]]==CASE_ORDER,
                "nine original R3 sites/horizons altered")
        for case in s["cases"]:
            task=case["task"]
            receipt=d["source_locked_cases"][task]
            require(receipt["portable_receipt_sha256"]==digest(
                receipt["portable_source_bound_receipt"]), "forged portable source certificate")
            require(receipt["portable_source_bound_receipt"]["original_selection"][
                "research_opt_in"]["policy_sha256"]==
                receipt["full_precision_original_decisions"]["research_opt_in"]["policy_sha256"],
                "portable policy not matched to original typed decision")
            require(case["portable_receipt_sha256"]==receipt["portable_receipt_sha256"]
                    and case["original_R3_test_cohort_sha256"]==receipt["original_test_pair_SHA256"],
                    "native science model/receipt does not match frozen source")
            if task=="KATL_1h":
                decision=receipt["full_precision_original_decisions"]["research_opt_in"]
                require(decision["status"]=="ABSTAIN"
                    and decision["selected"] is None
                    and decision["selection_basis"]=="portable_near_tie_abstention",
                    "KATL research numerical near-tie was not refused")
                require("original_orc_research_opt_in" not in case["all_native_model_metrics"],
                    "refused near-tied research predictions silently fabricated")
            require(METHODS_REQUIRED.issubset(case["all_native_model_metrics"]),
                    "missing any real native specialist benchmark")
            pred=[x for x in s["matched_native_forecasts"] if x["task"]==task]
            require(len(pred)==case["origin_n"],"original R3 cohort size differs")
            for name,v in case["all_native_model_metrics"].items():
                y=[float(x["target_kelvin"]) for x in pred]
                p=[float(x["native_method_predictions_kelvin"][name]) for x in pred]
                require(len(y)>0 and len(y)==len(p) and
                        all(isfinite(z) for z in [*y,*p]),"unmatched nonfinite predictions")
                calc_mae=fsum(abs(a-b) for a,b in zip(y,p))/len(y)
                calc_rmse=sqrt(fsum((a-b)**2 for a,b in zip(y,p))/len(y))
                require(abs(calc_mae-v["mae"])<=1e-10 and
                        abs(calc_rmse-v["rmse"])<=1e-10,
                        "native MAE/RMSE cannot be independently reconstructed")
        data[f.name]=row
    return data

def verify(root, sha):
    cfg,_=prereg()
    data=read_all(root,sha)
    first=data[sorted(data)[0]]
    same={}
    for name,record in data.items():
        require(record["source_blobs"]==first["source_blobs"],
                "source Git blobs vary across native runners")
        require((record["pretest_n"],record["verified_n"])==
                (first["pretest_n"],first["verified_n"]),
                "original test count diverges across native runners")
        require(record["pretest_keys"]==first["pretest_keys"] and
                record["verified_keys"]==first["verified_keys"],
                "native original JUnit inventories diverge")
        require(record["decision"]["portable_aggregate_decision_sha256"]==
                first["decision"]["portable_aggregate_decision_sha256"],
                "source-bound portable decision differs across native runners")
        for task in CASE_ORDER:
            x=record["decision"]["source_locked_cases"][task]
            y=first["decision"]["source_locked_cases"][task]
            require(x["portable_receipt_sha256"]==y["portable_receipt_sha256"] and
                    x["portable_source_bound_receipt"]==y["portable_source_bound_receipt"],
                    "one portable source/bounded numeric receipt differs")
    max_cal=0.;max_forecast=0.
    for (name,a),(other,b) in combinations(data.items(),2):
        for task in CASE_ORDER:
            ca=a["decision"]["source_locked_cases"][task]["full_precision_original_decisions"]
            cb=b["decision"]["source_locked_cases"][task]["full_precision_original_decisions"]
            for policy in ("default","research_opt_in"):
                require((ca[policy]["status"],ca[policy]["selected"],ca[policy]["selection_basis"])==
                        (cb[policy]["status"],cb[policy]["selected"],cb[policy]["selection_basis"]),
                        "original full-precision selected method varies between platforms")
            metrics_a=a["decision"]["source_locked_cases"][task]["portable_source_bound_receipt"]["calibration_numeric_receipts"]
            metrics_b=b["decision"]["source_locked_cases"][task]["portable_source_bound_receipt"]["calibration_numeric_receipts"]
            require(metrics_a==metrics_b,"native rounded original calibration source score differs")
            raw_a=a["decision"]["source_locked_cases"][task]["full_precision_original_decisions"]["default"]["candidates"]
            raw_b=b["decision"]["source_locked_cases"][task]["full_precision_original_decisions"]["default"]["candidates"]
            for x,y in zip(raw_a,raw_b):
                require(x["method"]==y["method"],"original candidate method inventory differs")
                for k in ("calibration_mae","calibration_rmse"):
                    diff=abs(x[k]-y[k]);max_cal=max(max_cal,diff)
                    require(diff<=cfg["portable_numerical_identity"][
                        "candidate_MAE_RMSE_per_platform_allowed_max_delta_kelvin"],
                        "original calibration numeric residual exceeds bounded comparison")
        ra=a["result"]["matched_native_forecasts"]
        rb=b["result"]["matched_native_forecasts"]
        for row1,row2 in zip(ra,rb):
            require((row1["task"],row1["origin_ms"],row1["target_ms"])==
                    (row2["task"],row2["origin_ms"],row2["target_ms"]),
                    "cross-platform original withheld observation clock altered")
            require(row1["target_kelvin"]==row2["target_kelvin"],
                    "measured original NOAA heldout source differs across platforms")
            require(set(row1["native_method_predictions_kelvin"])==
                    set(row2["native_method_predictions_kelvin"]),
                    "original Orc selection method/abstention differs across platforms")
            for k,v in row1["native_method_predictions_kelvin"].items():
                diff=abs(v-row2["native_method_predictions_kelvin"][k])
                max_forecast=max(max_forecast,diff)
                require(diff<=cfg["portable_numerical_identity"][
                    "native_same_method_per_prediction_allowed_max_delta_kelvin"],
                    "original same-method native forecast mismatch")
    result={
        "schema":"cognitum.orc.bench02.r4r2r3.independent_four_native_receipt.v1",
        "status":"PASS_PORTABLE_ABSTENTION_AND_ORIGINAL_SOURCE_REPLAY",
        "source_sha":sha,
        "preregistration_git_blobs":[BASE_GIT_BLOB,AMEND_GIT_BLOB],
        "native_original_targets":list(sorted(data)),
        "native_test_counts":{name:{"pretest":v["pretest_n"],
                                     "result_replay":v["verified_n"]}
                               for name,v in data.items()},
        "original_native_all_sources_and_JUnit_equal":True,
        "original_4way_portable_decision_SHA256":first["decision"]["portable_aggregate_decision_sha256"],
        "original_raw_Fitted_and_Decision_SHA256_may_differ":True,
        "original_research_near_tie_KATL_1h_refused":True,
        "total_heldout_matched_original_pairs_per_platform":265,
        "cross_platform_max_original_MAE_RMSE_delta_kelvin":max_cal,
        "cross_platform_max_same_method_native_prediction_delta_kelvin":max_forecast,
        "original_legacy_negative_results_preserved":True,
        "trusted_original_public_availability_proven":False,
        "installed_MEL_permission_granted":False,
        "prospective_blind_method_accuracy_verified":False
    }
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--expected-sha",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=verify(Path(a.root),a.expected_sha)
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
         "test_counts":result["native_test_counts"],
         "portable_decision_sha":result["original_4way_portable_decision_SHA256"],
         "max_calibration_numeric_drift":result["cross_platform_max_original_MAE_RMSE_delta_kelvin"],
         "max_prediction_numeric_drift":result["cross_platform_max_same_method_native_prediction_delta_kelvin"]}))

if __name__=="__main__":
    main()
