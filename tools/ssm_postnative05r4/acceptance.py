"""POST-NATIVE-05-R4: immutable publisher/data/native-source four-platform science gate."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
NEW={
 "cognitum/research/ssm_timeaware.py":"1b0802a9d997b1d51136ce040947ba0d0c57cae0",
 "research_tests/ssm_postnative05r4/test_timeaware.py":"0065b73830d5ab06ccccc46be9c6f73a4e72f9c4",
 "research_tests/ssm_postnative05r4/data/Rac_daily_Q.csv":"0277bb41d84dc49d85b9a016fbfbce4f4ac59ed7",
 "research_tests/ssm_postnative05r4/data/Musk_daily_Q.csv":"964a615050252f4a05ebca9d69caffed847444d1",
 "research_tests/ssm_postnative05r4/data/USGS_siteInfo.csv":"174a59d509ceb3a56d6b7c44f38cb687ed24648d",
 "research_tests/ssm_postnative05r4/data/.gitattributes":"85e1151363e1cdea1ff69e7ed8b06220bbf59037",
}
EXPECTED=25

def need(ok,msg):
    if not ok: raise ValueError(msg)

def git(*args):
    return subprocess.check_output(("git",*args),cwd=ROOT,text=True).strip()

def hash256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def validate_xml(path):
    tree=ET.parse(path).getroot()
    all_suites=[tree] if tree.tag=="testsuite" else tree.findall("testsuite")
    need(bool(all_suites),"genuine JUnit suites")
    count={x:sum(int(s.get(x,"0")) for s in all_suites) for x in ("tests","failures","errors","skipped")}
    need(count==dict(tests=EXPECTED,failures=0,errors=0,skipped=0),
         "exact R4 JUnit inventory "+repr(count))
    identities=[(case.get("classname"),case.get("name"))
                for suite in all_suites for case in suite.iter("testcase")]
    need(len(identities)==EXPECTED and len(set(identities))==EXPECTED,
         "unique real R4 JUnit identities")
    return count,identities

def main(directory):
    from tools.ssm_postnative05.acceptance import PINS as P05_PINS
    from tools.ssm_postnative04.acceptance import PINS as P04_PINS, PRIOR_SOURCE as P03_PINS
    from cognitum.research import ssm_timeaware as m
    head=git("rev-parse","HEAD")
    need(not os.getenv("GITHUB_SHA") or head==os.environ["GITHUB_SHA"],"workflow SHA drift")
    need(not git("status","--porcelain","--untracked-files=no"),"dirty tracked source")
    locked={**P03_PINS,**P04_PINS,**P05_PINS,**NEW}
    for path,blob in locked.items():
        need(git("rev-parse",head+":"+path)==blob,"exact source Git blob mismatch: "+path)
    target=Path(directory).resolve()
    need(not target.exists(),"refuse to overwrite science evidence")
    target.mkdir(parents=True)
    studies=[]
    for key,path in (
        ("Rac","research_tests/ssm_postnative05r4/data/Rac_daily_Q.csv"),
        ("Musk","research_tests/ssm_postnative05r4/data/Musk_daily_Q.csv"),
        (m.NOAA,"research_tests/ssm_postnative05/data/NOAA_RA_station_2025.csv")):
        raw=(ROOT/path).read_bytes()
        meta=(ROOT/"research_tests/ssm_postnative05r4/data/USGS_siteInfo.csv").read_bytes() if key!=m.NOAA else None
        s=m.ingest(key,raw,meta)
        need(s["source_blob"]==locked[path],"publisher originals changed: "+key)
        report=m.evaluate(s)
        need(not report["physical_law_discovered"]
             and not report["full_hybrid_universal_superiority_proven"]
             and not report["conditional_dependent_coverage_guaranteed"]
             and not report["execution_authorized"],
             "model scientific authorization escalation")
        studies.append(report)
    (target/"science.json").write_text(
        json.dumps(studies,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    command=[sys.executable,"-m","pytest","-q","research_tests/ssm_postnative05r4",
             "--junitxml",str(target/"tests.xml")]
    run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,
                       encoding="utf-8",errors="replace",timeout=1600)
    (target/"tests.log").write_text(run.stdout+"\n"+run.stderr,encoding="utf-8")
    need(run.returncode==0,"native research suite FAILED; see tests.log")
    count,identities=validate_xml(target/"tests.xml")
    report={"task":"COG-05-SSM-POST-NATIVE-05-R4","status":"PASS_BOUNDED_TIME_AWARE_PHYSICAL_OBSERVATIONAL_MATH",
            "source_sha":head,"os":platform.platform(),"python":sys.version,
            "publisher_original_blobs":{k:locked[k] for k in (
                "research_tests/ssm_postnative05r4/data/Rac_daily_Q.csv",
                "research_tests/ssm_postnative05r4/data/Musk_daily_Q.csv",
                "research_tests/ssm_postnative05/data/NOAA_RA_station_2025.csv")},
            "r4_new_pins":NEW,"inherited_P05_source_pins":P05_PINS,
            "inherited_P04_source_pins":P04_PINS,"inherited_P03_source_pins":P03_PINS,
            "tests":count,"testcase_identities":identities,
            "artifacts_sha256":{path.name:hash256(path) for path in
                                (target/"science.json",target/"tests.xml",target/"tests.log")},
            "physical_law_discovered":False,"causal_parameter_estimation_verified":False,
            "time_series_conditional_coverage_guaranteed":False,
            "signed_original_instrument_source_verified":False,
            "HDC_KAN_SSM_universal_superiority_verified":False,"execution_authorized":False,
            "prior_scoped_r3_accepted_sha":"127672af94fb126163efd51057dfd5adf0f9bb4e"}
    (target/"receipt.json").write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n",
                                       encoding="utf-8")
    print(json.dumps({"status":report["status"],"sha":head,"tests":count},sort_keys=True))
if __name__=="__main__":
    need(len(sys.argv)==2,"output dir required")
    main(sys.argv[1])
