"""COG-06E source-bound cross-component reasoning and native compatibility safeguards and preserved CPU component acceptance.
No Lu registration, production approval, CH40 continuation or new learned training.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from tools.run_crossplatform_regression import LINUX_KERNEL_ONLY

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"cog06b-artifacts"
PY=sys.executable
EXTRAS=("security,scientific,research-hdc-kan,formal-z3,formal-cvc5,"
        "optimization-schedule,optimization-mip,planning-graph,planning-validation,"
        "probability-stats,causal-stats,spatial-core,spatial-vision,physics-ode,"
        "temporal-statespace,temporal-learned,adaptation-classical,topology-rips,topology-verify")
LEGACY_BINDINGS={
    "composition_pb2", "formal_solver_pb2", "formal_backend_pb2", "formal_advanced_pb2",
    "optimization_legacy_pb2", "optimization_runtime_pb2", "workflows_pb2",
    "planning_classical_pb2", "planning_engines_pb2", "planning_guidance_pb2",
    "planning_stochastic_pb2", "planning_structured_pb2",
    "probability_inference_pb2", "probability_backend_pb2",
    "probability_conjugate_pb2", "probability_continuous_pb2", "probability_diagnostics_pb2",
}

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()

def source_check():
    head=git("rev-parse","HEAD")
    if head!=os.environ["COG06B_EXPECTED_SHA"]:
        raise RuntimeError("wrong checkout SHA")
    if git("status","--porcelain","--untracked-files=no"):
        raise RuntimeError("tracked source changed")
    baseline="5c31406f52919b9f52c29df5714bf14d8a8e5aa6"
    # COG-04G–L: one reviewed C12 semantic-test fixture correction.
    # Keep the original historical provenance record and verify both versions.
    planning_test_path="tests/test_c12_p2_engines.py"
    planning_test_original="b037dd4ccb0778483e38eeb2c8860d982b67cfd7"
    planning_test_repair={planning_test_path:"6ca55aef63114b12fb7bdbf076c237936a3ca1bd"}
    planning_test_origin="1cca0f48960855a0ca121620e8644682563bc175"
    seen_planning_test=0
    # C13 compatibility: retain the original historical and frozen blobs.
    c13_path="cognitum/probability_diagnostics.py"
    c13_original="c94e0f7bb3d2b3e9ce69a47d8dea4d645380004a"
    c13_historical="35190beb1000b6d33039a84cbbc92fc9b844f3cc"
    c13_repair={c13_path:"dbbdc91188446715bb0915e48d37a51bb72d9909"}
    c13_regression={"tests/test_c13_diagnostics_compatibility.py":"24604bd8500481e8340259987011091213cbf2bb"}
    seen_c13=0
    for rel in ("docs/integration/COG06B_C10_SOURCE_PROVENANCE.json",
                "docs/integration/COG06B_C11_C13_SOURCE_PROVENANCE.json"):
        manifest=json.loads((ROOT/rel).read_text(encoding="utf-8"))
        for item in manifest.get("exact",[]):
            if git("rev-parse","HEAD:"+item["path"])!=item["sha"]:
                raise RuntimeError("historical blob drift: "+item["path"])
        for item in manifest.get("records",[]):
            if item.get("destination")==c13_path:
                if (rel!="docs/integration/COG06B_C11_C13_SOURCE_PROVENANCE.json"
                        or manifest["historical_commit"]!=planning_test_origin
                        or item["source_path"]!=c13_path or item["source_blob"]!=c13_historical
                        or item["pre_import_repair_blob"]!=c13_original
                        or git("rev-parse",planning_test_origin+":"+c13_path)!=c13_historical):
                    raise RuntimeError("C13 original provenance mismatch")
                seen_c13+=1
            if item["disposition"]=="exact":
                destination=item["destination"]
                expected=item["source_blob"]
                if destination==planning_test_path:
                    if (rel!="docs/integration/COG06B_C11_C13_SOURCE_PROVENANCE.json"
                            or manifest["historical_commit"]!=planning_test_origin
                            or item["source_path"]!=planning_test_path
                            or expected!=planning_test_original
                            or git("rev-parse",planning_test_origin+":"+planning_test_path)!=planning_test_original):
                        raise RuntimeError("C12 historical provenance mismatch")
                    seen_planning_test+=1
                    expected=planning_test_repair[destination]
                if git("rev-parse","HEAD:"+destination)!=expected:
                    raise RuntimeError("historical blob drift: "+destination)
    if seen_planning_test!=1:
        raise RuntimeError("missing/duplicated original C12 provenance record")
    if seen_c13!=1:
        raise RuntimeError("missing/duplicated C13 provenance record")
    for rel,expected in {**c13_repair,**c13_regression}.items():
        if git("rev-parse","HEAD:"+rel)!=expected:
            raise RuntimeError("unreviewed C13 compatibility mutation: "+rel)
    # Permit only the demonstrated C06/C07 duplicate-message repair, not
    # arbitrary replacement of accepted runtime/schema/test files.
    identity_repair={"proto/cognitum/memory/v1/host_owned.proto",
                     "cognitum/proto/host_owned_memory_pb2.py"}
    for rel in sorted(identity_repair):
        previous=git("show",baseline+":"+rel)
        expected=previous.replace('StateEvent','HostOwnedStateEvent')
        if rel.endswith('_pb2.py'):
            expected+='\n\n# Source compatibility only; the old ambiguous Protobuf type name is not a wire alias.\nStateEvent=HostOwnedStateEvent'
        actual=git("show","HEAD:"+rel)
        # git() strips surrounding whitespace, so compare normalized text edges only.
        if actual!=expected.strip():
            raise RuntimeError("unexpected change within identity repair: "+rel)
    # The exact reviewed COG-06E proof repair is the only additional exception.
    proof_repair={'cognitum/formal_proofs.py':'71f5354a1e1cd0750f7e51acb77cd90e4bd1c711'}
    for rel,expected in proof_repair.items():
        if git('rev-parse','HEAD:'+rel)!=expected:
            raise RuntimeError('unreviewed proof repair mutation: '+rel)
    # COG-07: preserve the exact reviewed practical C14 validation repair.
    causal_repair={"cognitum/causal_specialists.py":"2fcecac96bfa1028a242d6a541eb64c1752e7b51"}
    for rel,expected in causal_repair.items():
        if git("rev-parse","HEAD:"+rel)!=expected:
            raise RuntimeError("unreviewed causal guard mutation: "+rel)
    # COG-07A: narrowly reviewed C11 cancellation race repair, pinned to
    # the locally tested runtime and adversarial regression blobs.
    cancellation_repair={"cognitum/optimization_runtime.py":"364e0426c54fee21757f6e334d82930e280ec9b2"}
    cancellation_regression={"tests/test_c11_cancellation_race.py":"79f8b619eb2a0f1f14de205940e8f15850bbe8d7"}
    for rel,expected in {**cancellation_repair,**cancellation_regression}.items():
        if git("rev-parse","HEAD:"+rel)!=expected:
            raise RuntimeError("unreviewed C11 cancellation mutation: "+rel)
    # Preserve COG-06G and all other earlier accepted runtime/schema/test paths.
    frozen="ce28a7ad6a584e6cce5a77c9be5d63bc5dabeaa0"
    prior_changes=git("diff","--name-only","--diff-filter=MDTRC",frozen,head,"--","cognitum","proto","tests").splitlines()
    if git("rev-parse",frozen+":"+planning_test_path)!=planning_test_original:
        raise RuntimeError("frozen C12 test provenance mismatch")
    if git("rev-parse",frozen+":"+c13_path)!=c13_original:
        raise RuntimeError("frozen C13 runtime provenance mismatch")
    if set(prior_changes)!=set(causal_repair) | set(cancellation_repair) | set(planning_test_repair) | set(c13_repair):
        raise RuntimeError("unexpected COG-06G accepted runtime/schema/test modification: "+repr(prior_changes))
    # No other replacement of accepted mature runtime or existing schemas.
    changed=git("diff","--name-only",baseline,head).splitlines()
    for rel in changed:
        if rel not in identity_repair and rel not in proof_repair and rel not in causal_repair and rel not in cancellation_repair and rel not in planning_test_repair and rel not in c13_repair and rel.startswith(("cognitum/","proto/","tests/test_")):
            if subprocess.run(["git","cat-file","-e",baseline+":"+rel],cwd=ROOT,
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
                raise RuntimeError("accepted existing runtime/schema/test replaced: "+rel)
    return {"commit":head,"baseline":baseline,"changed_paths":changed,
            "c13_compatibility":{"historical_blob":c13_historical,"frozen_blob":c13_original,"candidate_blob":c13_repair[c13_path],"regression":c13_regression},
            "c12_test_repair":{"path":planning_test_path,"historical_commit":planning_test_origin,
                               "historical_blob":planning_test_original,"accepted_candidate_blob":planning_test_repair[planning_test_path]}}

def native_preflight():
    import numpy, scipy, networkx, z3, cvc5
    from cognitum.probability_diagnostics import _diagnostics_backend
    _, diagnostics_version = _diagnostics_backend()
    from scipy.optimize import milp
    from ortools.sat.python import cp_model
    from scipy.integrate import solve_ivp
    from unified_planning.shortcuts import Problem
    from tests.cog06b_z3_fixture import z3_library
    from importlib.metadata import version
    path=z3_library()
    if not path:raise RuntimeError("required C API Z3 library unavailable")
    print(json.dumps({"z3_lib_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                      "diagnostics_backend":"arviz-"+diagnostics_version,
                      "versions":{x:version(x) for x in ("numpy","scipy","networkx","z3-solver","cvc5","ortools","unified-planning")}}))
    # All imported engines are CPU libraries. No GPU execution or checkpoint load.

def descriptors():
    from google.protobuf.descriptor_pb2 import FileDescriptorSet, FileDescriptorProto
    from tools.check_proto_descriptors import EXPECTED,normalized_file
    shipped=dict(EXPECTED)
    for name in sorted(LEGACY_BINDINGS):
        d=importlib.import_module("cognitum.proto."+name).DESCRIPTOR
        if d.name in shipped:raise RuntimeError("duplicate descriptor path "+d.name)
        shipped[d.name]=d
    target=OUT/"compiled-descriptors.pb"
    subprocess.run([PY,"-m","grpc_tools.protoc","-Iproto",
                    "--include_imports","--descriptor_set_out="+str(target),
                    *["proto/"+x for x in sorted(shipped)]],cwd=ROOT,check=True)
    compiled={d.name:d for d in FileDescriptorSet.FromString(target.read_bytes()).file}
    for name,d in sorted(shipped.items()):
        expect=FileDescriptorProto.FromString(d.serialized_pb)
        actual=compiled.get(name)
        if actual is None or normalized_file(actual)!=normalized_file(expect) or list(actual.dependency)!=list(expect.dependency):
            raise RuntimeError("compiled descriptor differs: "+name)
    print("descriptor parity",len(shipped),"source schemas, all coexist in one Python process")

def main():
    OUT.mkdir(exist_ok=True)
    report={"schema":"cognitum.cog07.cpu-regression.v1","platform":sys.platform,
            "python":sys.version,"production_enabled":False,"lu_roundtrip":False,
            "optional_unvalidated":["pgmpy native worker","PyMC native worker","Fast Downward native planner","Carcara actual proof acceptance","official MOT17 TrackEval","reviewed ByteTrack optional separate native matrix","DoWhy/EconML/causal-learn separately required in COG-07 matrix","Tigramite license-gated"],
            "steps":[]}
    def save():(OUT/"result.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    def run(name,args,timeout=900):
        path=OUT/(name+".log");start=time.monotonic();code=-1;reason=""
        print("===",name,"===",flush=True)
        try:
            with path.open("wb") as log:
                code=subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:reason="timeout"
        except OSError as exc:reason=type(exc).__name__
        if path.exists():
            print("\n".join(path.read_text(encoding="utf-8",errors="replace").splitlines()[-40:]),flush=True)
        report["steps"].append({"name":name,"exit":code,"reason":reason,
            "seconds":round(time.monotonic()-start,3),
            "log_sha256":hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None})
        save();print(name+": exit="+str(code),flush=True)
        return code==0
    report["source"]=source_check();save()
    if not run("install_cpu_dependencies",[PY,"-m","pip","install","-e",
        ".["+EXTRAS+"]","grpcio-tools>=1.70,<2",
        "pytest>=9,<10","jsonschema>=4,<5","threadpoolctl>=3,<4"],1500):return 1
    run("pip_check",[PY,"-m","pip","check"])
    run("pip_freeze",[PY,"-m","pip","freeze"])
    run("compile",[PY,"-m","compileall","-q","cognitum","tests","tools"])
    run("native_preflight",[PY,"-m","tools.cog06b_cpu_acceptance","--native"])
    run("descriptor_parity",[PY,"-m","tools.cog06b_cpu_acceptance","--descriptors"])
    prefixes=("test_c05","test_c06","test_c07","test_c10","test_c11","test_c12",
              "test_c13","test_c14_closeout","test_c14_practical_guards","test_c16","test_c17","test_cooperative",
              "test_cognitum_capability_route_proposal","test_c15_trackeval_")
    focused=sorted(str(p.relative_to(ROOT)) for p in (ROOT/"tests").glob("test_*.py")
                   if p.name.startswith(prefixes))
    report["focused_modules"]=focused;save()
    run("focused",[PY,"-m","pytest","-q","-ra","-o","pythonpath=tests",
                   "--junitxml="+str(OUT/"focused.xml"),*focused],1800)
    # Only explicitly unavailable optional workers can be skipped in this gate.
    xml=OUT/"focused.xml"
    if xml.exists():
        skips=[{"test":case.attrib.get("classname","")+"."+case.attrib.get("name",""),
                "reason":case.find("skipped").attrib.get("message","")}
               for case in ET.parse(xml).iter("testcase") if case.find("skipped") is not None]
        report["focused_skips"]=skips
        allowed=("test_real_pgmpy_worker_when_installed","test_optional_runtime_import_compatibility",
                 "test_missing_optional_backend")
        unexpected=[x for x in skips if not any(x["test"].endswith(a) for a in allowed)]
        report["unexpected_focused_skips"]=unexpected
        report["steps"].append({"name":"focused_skip_policy","exit":int(bool(unexpected)),
                                "reason":"unexpected skip" if unexpected else ""});save()
    else:
        report["steps"].append({"name":"focused_skip_policy","exit":1,"reason":"missing junit"});save()
    run("c14_statsmodels_evidence",[PY,"-m","tools.cog07_causal_evidence","--backend","statsmodels","--out",str(OUT/"c14-statsmodels-evidence.json")],300)
    run("cross_component_evidence",[PY,"-m","tools.cog06d_composition_evidence"],300)
    for module in ("c06_c07_benchmark","c11_component_benchmark","c12_component_benchmark",
                   "c13_component_benchmark","c16_physics_benchmark","c17_temporal_benchmark"):
        run(module,[PY,"-m","tools."+module])
    ignores=[f"--ignore=tests/{n}.py" for n in sorted(LINUX_KERNEL_ONLY)] if os.name=="nt" else []
    report["kernel_suites_not_run"]=sorted(LINUX_KERNEL_ONLY) if os.name=="nt" else []
    run("combined_regression",[PY,"-m","pytest","-q","-ra","-o","pythonpath=tests",
        "--junitxml="+str(OUT/"combined.xml"),"tests",*ignores],1800)
    report["source_after"]=source_check()
    report["all_steps_passed"]=all(x["exit"]==0 for x in report["steps"]);save()
    return 0 if report["all_steps_passed"] else 1

if __name__=="__main__":
    if sys.argv[1:]==["--native"]:native_preflight()
    elif sys.argv[1:]==["--descriptors"]:descriptors()
    else:sys.exit(main())
