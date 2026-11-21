"""R5 independent original Actions ZIP scientific replay (offline, standard library).

Use exact original nine ZIP files downloaded through an authenticated GitHub
connection. This is an independent audit of the prior retrospective study,
not new training or prospective weather-data availability evidence.
"""
from __future__ import annotations
from collections import defaultdict
from hashlib import sha256
from math import fsum,sqrt,isclose
from pathlib import Path
from zipfile import ZipFile
import argparse,json,xml.etree.ElementTree as ET

R4 = {
  14694682761:"57d07fb313b68d60fd685e93d42d353672e05037a700a5a230d7b3cf2e2f949d",
  14694214884:"8331b57aee84cd4f598018b56f98287f3aad356edc0dfcc02ed463a30f0cf238",
  14694089529:"81a2afeba74577cd7bc3090519d6af3fd1d35b742fbf54f187b4d2f2f12708f5",
  14694851373:"9ff3d3321015e17adbd833680c23763f19e1a883162b201ae089ef8820742d2f",
}
NATIVE = {
  14695638527:"5534c2a764c5a64f71a06bb5dc7d0d3a62c609ea8d488da2939798f670418f73",
  14695223848:"1c07d0c74215003ebef893ee82538d182813141d79d0a0a9ec2983d057d0121f",
  14695773244:"402941b728dd75a06a11859482628a3c0f31917328e8ce55e83708cd7a93358d",
  14695368459:"3390d2362a3bae703b1ac2bc1017b47a337d5b1c1df4704dddc448d6f2c5ed77",
}
FOURWAY = {
 14696066746:"a73ad4b4656e0d003af80555debb29108b5e51b6dac51fcf8cea659479fef72a"
}
R4_SHA="11ed7697defd2a6df1c75360ddf2e7aca6a890ae"
NATIVE_SHA="06eb4ff9f40fd437992842f6cd7e4d9c3db1cc7f"
PORTABLE_SHA="703f13885bb81db5b63f718cf0c6a7beebb180d5d56f189bfbdf222a649a0789"
STATIONS={
 "KSEA":"2b2772ea7ad91d76f22e1be82269c0b41e86294392241a42bae9d81f061a6205",
 "KDEN":"dd72f4e2b9dde753c2a9c0f964ca86eb2b8091eeaf9b7b807c3b8d7a98618645",
 "KATL":"ac0b69ce3b4755e56e9273310af94be638dd240d9857a98a719812f1dd441622",
}
class Refusal(ValueError):pass
def need(ok,s):
    if not ok:raise Refusal(s)

def artifact(path,aid,expected):
    filename=path/f"github-actions-artifact-{aid}.zip"
    data=filename.read_bytes()
    need(sha256(data).hexdigest()==expected,f"original ZIP {aid} content digest changed")
    z=ZipFile(filename)
    need(z.testzip() is None,f"original ZIP {aid} CRC invalid")
    suites=[]
    for name in z.namelist():
        if name.endswith(".xml"):
            root=ET.fromstring(z.read(name))
            cases=list(root.iter("testcase"))
            need(len(cases)>0 and not any(
                item.find(t) is not None for item in cases
                for t in ("failure","error","skipped")),
                f"original native JUnit negative: {aid}:{name}")
            suites.append(len(cases))
    return z,suites

def metric(y,p):
    n=len(y)
    need(n==len(p) and n>0,"unmatched original observation labels")
    return sqrt(fsum((a-b)**2 for a,b in zip(y,p))/n)

def verify(directory):
    path=Path(directory);r4={};native={};original_suites={}
    for group,dests,expected_sha,filename,test_n in (
       ("R4",r4,R4_SHA,"bench02-r4-results.json",104),
       ("R4R2R3",native,NATIVE_SHA,"bench02-r4r2r3-results.json",322)):
        ids=R4 if group=="R4" else NATIVE
        for aid,pin in ids.items():
            z,suites=artifact(path,aid,pin)
            need(sum(suites)==test_n,f"{group} source-native tests changed")
            need(z.read("source-sha.txt").decode().strip()==expected_sha,
                 f"{group} exact tested source SHA changed")
            obj=json.loads(z.read(filename))
            rows=(obj["full_original_heldout_predictions"] if group=="R4"
                  else obj["matched_native_forecasts"])
            need(len(rows)==265 and len(obj["cases"])==9,
                 f"{group} original case/origin denominator changed")
            dests[aid]=(obj,rows)
            original_suites[str(aid)]=suites
    four,other=artifact(path,14696066746,FOURWAY[14696066746])
    receipt=json.loads(four.read("bench02-r4r2r3-cross-native-receipt.json"))
    need(receipt["status"]=="PASS_PORTABLE_ABSTENTION_AND_ORIGINAL_SOURCE_REPLAY" and
         receipt["original_4way_portable_decision_SHA256"]==PORTABLE_SHA and
         receipt["total_heldout_matched_original_pairs_per_platform"]==265,
         "independent native original four-platform reconciliation was not accepted")
    source_rows=next(iter(r4.values()))[1]
    cross_clock=0;max_temp=0.;max_reference=0.
    for (aid,(obj,rows)) in native.items():
        need(obj["portable_aggregate_decision_sha256"]==PORTABLE_SHA and
             obj["original_first_capture_eligible_origins"]==0 and
             obj["historical_publication_proven"] is False and
             obj["installed_MEL_authorized"] is False,
             "unattested retrospective source promoted to production evidence")
        for previous,current in zip(source_rows,rows):
            need((previous["task"],previous["origin_ms"],previous["target_ms"])==
                 (current["task"],current["origin_ms"],current["target_ms"]),
                 "original R4 station/horizon clocks changed")
            source_sha=STATIONS[previous["task"].split("_")[0]]
            need(previous["source_sha256"]==source_sha,
                 "original R3 NOAA source digest replaced")
            td=abs(previous["observed_target_kelvin"]-current["target_kelvin"])
            rd=abs(previous["predictions_kelvin"]["direct_ridge"]-
                   current["native_method_predictions_kelvin"]["original_R4_direct_ridge"])
            max_temp=max(max_temp,td);max_reference=max(max_reference,rd)
            need(td<=1e-10 and rd<=1e-10,
                 "original R4 target or identical fixed ridge was modified")
            cross_clock+=1
        for method,summary in obj["methods"].items():
            completed=[]
            for case in obj["cases"]:
                if method not in case["all_native_model_metrics"]:continue
                same=[r for r in rows if r["task"]==case["task"]]
                y=[r["target_kelvin"] for r in same]
                p=[r["native_method_predictions_kelvin"][method] for r in same]
                rmse=metric(y,p)
                need(abs(rmse-case["all_native_model_metrics"][method]["rmse"])<=1e-10,
                     "actual native scientific error not reproducible")
                ref=case["all_native_model_metrics"]["original_R4_direct_ridge"]["rmse"]
                completed.append((ref-rmse)/ref)
            need(len(completed)==summary["reported"] and
                 summary["complete_nine_case_macro"]==(len(completed)==9),
                 "original Orc refusals excluded or hidden")
            if completed:
                need(abs(sum(completed)/len(completed)-
                         summary["reported_only_macro"])<=1e-10,
                     "original nine-case macro was rewritten")
    for obj,rows in r4.values():
        need(obj["strict_first_capture_eligible_test_origins"]==0 and
             obj["historical_publication_attested"] is False,
             "historical retro receipts misrepresented as first publication")
    return {
        "schema":"cognitum.orc.bench02.r5.independent_original_ZIP_replay.v1",
        "R4_archive_originals_checked":len(r4),
        "R4R2R3_native_archive_originals_checked":len(native),
        "independent_cross_native_archive_checked":True,
        "same_original_R4_and_R4R2R3_source_clock_pairs":265,
        "R4_R4R2R3_source_target_comparisons":cross_clock,
        "max_original_target_numeric_roundoff_K":max_temp,
        "max_original_ridge_numeric_roundoff_K":max_reference,
        "original_4way_portable_decision_sha256":PORTABLE_SHA,
        "original_zip_archive_sha256":{str(k):v for k,v in {**R4,**NATIVE,**FOURWAY}.items()},
        "original_suite_counts":original_suites,
        "original_R3_first_capture_eligible_origins":0,
        "historical_publisher_publication_witnessed":False,
        "prior_negative_results_and_policy_abstentions_preserved":True,
        "future_prospective_results_available":False,
    }

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--archives",required=True)
    parser.add_argument("--out",required=True)
    a=parser.parse_args(argv)
    result=verify(a.archives)
    with Path(a.out).open("x",encoding="utf-8",newline="\n") as f:
        json.dump(result,f,sort_keys=True,indent=2);f.write("\n")
    print(json.dumps({"R4":result["R4_archive_originals_checked"],
         "native":result["R4R2R3_native_archive_originals_checked"],
         "original_pairs":265,"out":a.out}))
if __name__=="__main__":main()
