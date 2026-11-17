"""COG-00 source-bound grouped acceptance. Research only, not a release gate."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.run_crossplatform_regression import LINUX_KERNEL_ONLY

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cog00-artifacts"
RECOVERY = "04d12fdd118f1788d3054167cf942e05b939d621"
ADDED = {".github/workflows/cog00-recovery-acceptance.yml",
         "tools/cog00_recovery_acceptance.py"}
FOCUSED = (
    "test_research_optional", "test_c08_admission", "test_c08_canonical",
    "test_c08_lifecycle_recovery", "test_c08_index_lifecycle",
    "test_c09_signed_approval", "test_research_durable",
    "test_hdc_kan_ssm_recovery", "test_hdc_recovered_extended",
    "test_kan_spline_endpoint_p1", "test_ssm_state_resume_p1",
    "test_cog00_ssm_alias",
)
BASE_EXTRAS = ("security,scientific,causal-stats,planning-graph,"
               "planning-validation,research-hdc-kan")
ALL_EXTRAS = ("security,scientific,research-hdc-kan,formal-z3,formal-cvc5,"
              "optimization-schedule,optimization-mip,planning-graph,"
              "planning-validation,probability-stats,causal-stats,"
              "spatial-core,spatial-vision,physics-ode,temporal-statespace,"
              "temporal-learned,adaptation-classical,topology-rips,topology-verify")
INSTALL = ["grpcio-tools>=1.70,<2", "pytest>=9,<10", "jsonschema>=4,<5",
           "scipy>=1.14,<2", "threadpoolctl>=3,<4"]
PY = sys.executable


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def verify_source():
    sha = git("rev-parse", "HEAD")
    expected = os.environ.get("COG00_EXPECTED_SHA")
    if expected and sha != expected:
        raise RuntimeError("checkout SHA differs from requested run")
    if sha != RECOVERY:
        changed = set(git("diff", "--name-only", RECOVERY, sha).splitlines())
        if changed != ADDED:
            raise RuntimeError(f"acceptance candidate differs from recovery: {sorted(changed)}")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("tracked source differs from committed checkout")
    manifest = json.loads((ROOT / "docs/integration/COG00_SOURCE_PROVENANCE.json").read_text(encoding="utf-8"))
    items = manifest["exact_blobs"]
    if len(items) != manifest["exact_blob_count"] or len({x["path"] for x in items}) != len(items):
        raise RuntimeError("recovery manifest count/uniqueness mismatch")
    if len(items) != 68:
        raise RuntimeError("unexpected recovery inventory")
    for item in items:
        if git("rev-parse", f'HEAD:{item["path"]}') != item["sha"]:
            raise RuntimeError(f'blob mismatch: {item["path"]}')
    return {"commit": sha, "recovery_commit": RECOVERY, "exact_verified": len(items)}


def descriptor_check():
    from google.protobuf.descriptor_pb2 import FileDescriptorSet, FileDescriptorProto
    from cognitum.proto import kan_approval_pb2
    from tools.check_proto_descriptors import normalized_file
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "compiled.pb"
        subprocess.run([PY, "-m", "grpc_tools.protoc", "-Iproto",
                        f"--descriptor_set_out={p}",
                        "proto/cognitum/research/v1/kan_approval.proto"],
                       cwd=ROOT, check=True)
        actual = FileDescriptorSet.FromString(p.read_bytes())
        expected = FileDescriptorProto.FromString(kan_approval_pb2.DESCRIPTOR.serialized_pb)
        if len(actual.file) != 1 or normalized_file(actual.file[0]) != normalized_file(expected):
            raise RuntimeError("KAN approval descriptor mismatch")
    print("KAN approval protobuf compiler/checked-in descriptor match")


def main():
    OUT.mkdir(exist_ok=True)
    evidence = {"schema": "cognitum.cog00.acceptance.v1", "source": None,
                "platform": sys.platform, "python": sys.version,
                "research_only": True, "production_enabled": False,
                "steps": []}
    def save():
        (OUT / "result.json").write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    def run(name, command, timeout=900):
        start = time.monotonic()
        path = OUT / (name + ".log")
        print(f"=== {name} ===", flush=True)
        code = -1
        reason = ""
        try:
            with path.open("wb") as f:
                code = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
                                      timeout=timeout, check=False).returncode
        except subprocess.TimeoutExpired:
            reason = "timeout"
        except OSError as exc:
            reason = type(exc).__name__
        tail = path.read_text(encoding="utf-8", errors="replace").splitlines()[-50:] if path.exists() else []
        print("\n".join(tail), flush=True)
        evidence["steps"].append({"name": name, "exit": code, "reason": reason,
                                 "seconds": round(time.monotonic()-start, 3)})
        save()
        print(f"{name}: exit={code} {reason}", flush=True)
        return code == 0
    try:
        evidence["source"] = verify_source()
        save()
    except Exception as exc:
        evidence["source_error"] = str(exc)
        save()
        raise
    run("manifest", [PY, "-m", "unittest", "discover", "-s", "tests", "-p", "test_pyproject_component_extras.py"])
    if not run("install_baseline", [PY, "-m", "pip", "install", "-e", f".[{BASE_EXTRAS}]", *INSTALL], 1200):
        return 1
    run("baseline_pip_check", [PY, "-m", "pip", "check"])
    run("compile", [PY, "-m", "compileall", "-q", "cognitum", "tests", "tools"])
    run("kan_descriptor", [PY, "-m", "tools.cog00_recovery_acceptance", "--descriptor"])
    run("focused_pytest", [PY, "-m", "pytest", "-q", "-ra", *[f"tests/{n}.py" for n in FOCUSED]])
    run("original_hdc_selftest", [PY, "-m", "cognitum.research.hdc_recovered.selftest"])
    run("family_benchmark", [PY, "-m", "tools.run_hdc_kan_ssm_recovery_benchmark"])
    run("hdc_canonical_benchmark", [PY, "-m", "tools.run_c08_candidate_benchmark"])
    run("hdc_conventional_baselines", [PY, "-m", "tools.run_c08_conventional_baselines"])
    run("baseline_combined_regression", [PY, "-m", "tools.run_crossplatform_regression"], 1200)
    run("source_gate", [PY, "-m", "tools.cognitum_integration_source_gate", "--require-sources",
                        "--report", str(OUT / "source-inventory.json")])
    if not run("install_combined", [PY, "-m", "pip", "install", "-e", f".[{ALL_EXTRAS}]", *INSTALL], 1500):
        return 1
    run("combined_pip_check", [PY, "-m", "pip", "check"])
    run("combined_pip_freeze", [PY, "-m", "pip", "freeze"])
    run("combined_regression", [PY, "-m", "tools.run_crossplatform_regression"], 1200)
    # Original unittest runner does not discover pytest-function tests.
    # Keep its explicit kernel-only Windows ownership; do not invent other exclusions.
    ignores = [f"--ignore=tests/{n}.py" for n in sorted(LINUX_KERNEL_ONLY)] if os.name == "nt" else []
    evidence["kernel_suites_not_run"] = sorted(LINUX_KERNEL_ONLY) if os.name == "nt" else []
    save()
    run("combined_pytest", [PY, "-m", "pytest", "-q", "-ra", "tests", *ignores], 1500)
    run("synthetic_replay", [PY, "-m", "cognitum", "--calculator", "replay", "evals/smoke.json"])
    run("evaluation_smoke", [PY, "tools/run_c03_smoke.py", "--check"])
    evidence["source_after"] = verify_source()
    evidence["all_steps_passed"] = all(x["exit"] == 0 for x in evidence["steps"])
    save()
    return 0 if evidence["all_steps_passed"] else 1


if __name__ == "__main__":
    if sys.argv[1:] == ["--descriptor"]:
        descriptor_check()
    else:
        sys.exit(main())
