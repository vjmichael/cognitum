"""R1 ephemeral CI-only one-use original SSM fixture.

This is NOT an installed Core issuer or an enrolled Cognitum credential. A
random per-run MAC key is compiled into an unsigned SCM test executable and
is recoverable from it; it cannot authorize production work. Never reuse an
original nonce, file, user turn, or service fixture as a production grant.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sys

# CI runs the script by filename; resolve the reviewed project tree explicitly.
PROJECT_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT_ROOT))

from cognitum.mel.ssm_supervisor import OP
from cognitum.research import ssm_stochastic_checkpoints as cp
from cognitum.research import ssm_stochastic_streaming as streaming

DOMAIN=b"Cognitum.SCM.R1.test.intent.v1\x00"


def prepare(root:Path,env_file:Path,*,runtime_root:Path|None=None,
            worker_root:Path|None=None):
    root=root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("fixture root unavailable")
    if worker_root is None:
        worker_root=root
    else:
        worker_root=Path(worker_root)
        if not worker_root.is_absolute() or worker_root.is_symlink():
            raise ValueError("worker I/O must be independently pinned absolute directory")
        worker_root=worker_root.resolve(strict=True)
        if not worker_root.is_dir() or worker_root==root:
            raise ValueError("worker I/O cannot be original signed host journal")

    if runtime_root is None:
        python=Path(sys.executable).resolve(strict=True)
        script=(Path(__file__).resolve().parents[1] /
                "cognitum/mel/ssm_r5_fixed_child.py").resolve(strict=True)
        frozen_pins={}
    else:
        runtime_root=Path(runtime_root)
        if not runtime_root.is_absolute() or runtime_root.is_symlink():
            raise ValueError("not an externally staged absolute immutable SSM runtime")
        runtime_root=runtime_root.resolve(strict=True)
        python=runtime_root/"python.exe"
        script=runtime_root/"cognitum/mel/ssm_r5_fixed_child.py"
        manifest=runtime_root/"r3-r1-runtime.manifest"
        provenance=runtime_root/"r3-r1-runtime-provenance.json"
        if not all(p.is_file() and not p.is_symlink()
                   for p in (python,script,manifest,provenance)):
            raise ValueError("R3 original frozen image/script/manifest not installed")
        report=json.loads(provenance.read_text(encoding="ascii"))
        digest=hashlib.sha256(manifest.read_bytes()).hexdigest()
        if report["schema"]!="cognitum.ssm.r3r1.test_installer_style_frozen_runtime.v1" or (
           report["runtime_manifest_sha256"]!=digest or
           report["python_sha256"]!=hashlib.sha256(python.read_bytes()).hexdigest() or
           report["fixed_script_sha256"]!=hashlib.sha256(script.read_bytes()).hexdigest() or
           report["signed_installer_publisher_approved"] is not False):
            raise ValueError("original frozen numerical package pin mismatch")
        frozen_pins={
          "COG_R3_R1_RUNTIME_ROOT":str(runtime_root),
          "COG_R3_R1_RUNTIME_MANIFEST_SHA256":digest,
        }
    engine=streaming.FixedDurationIncrementSmoother(
        [[-.2]],[[.3]],[[1]],[[.5]],[.1],[[.7]],lag_duration=1.0,
        noise_cross=[[.1]],max_pending_states=16)
    payload={"state":cp._encode_state(engine),"kind":"increment",
             "end_time":.3,"increment":[.2]}
    request=json.dumps({"operation":OP,"payload":payload},
                       sort_keys=True,separators=(",",":"),
                       ensure_ascii=True,allow_nan=False).encode("ascii")
    request_sha=hashlib.sha256(request).hexdigest()
    paths={
        "COG_R1_CI_PYTHON":python,
        "COG_R1_CI_SCRIPT":script,
        "COG_R1_CI_REQUEST":worker_root/"input.frame",
        "COG_R1_CI_OUTPUT":worker_root/"output.frame",
        "COG_R1_CI_INTENT":root/"intent.frame",
        "COG_R1_CI_PRELAUNCH":root/"prelaunch.json",
        "COG_R1_CI_STOP":root/"stop.json",
    }
    for path in paths.values():
        if path in (python,script):
            continue
        if path.exists():
            raise ValueError("existing R1 fixture attempt, no replay")
    paths["COG_R1_CI_REQUEST"].write_bytes(request)
    fields=[
        "cognitum.ssm.r1.original_fixture.v1",
        "ci-workspace","ci-conversation","ci-user-turn","ci-task",
        "ci-original-operation","ci-session","ci-ssm-subject",
        "ci-stream","ci-event",request_sha,secrets.token_hex(16),
    ]
    raw="\t".join(fields).encode("ascii")
    key=secrets.token_bytes(32)
    tag=hmac.new(key,DOMAIN+raw,hashlib.sha256).hexdigest()
    paths["COG_R1_CI_INTENT"].write_bytes(raw+b"\n"+tag.encode("ascii")+b"\n")
    pins={
        **{n:str(p) for n,p in paths.items()},
        **frozen_pins,
        "COG_R1_CI_PYTHON_SHA256":hashlib.sha256(python.read_bytes()).hexdigest(),
        "COG_R1_CI_SCRIPT_SHA256":hashlib.sha256(script.read_bytes()).hexdigest(),
        "COG_R1_CI_REQUEST_SHA256":request_sha,
        "COG_R1_CI_MAC_KEY_HEX":key.hex(),
    }
    # Never print/emit the per-run test key into CI logs. Github Env file is
    # read at build time only; CI artifact must exclude key and intent.
    with env_file.open("a",encoding="utf-8") as out:
        for name,value in pins.items():
            if "\n" in value or "\r" in value:
                raise ValueError("invalid CI fixture path")
            out.write(f"{name}={value}\n")
    return {"schema":"cognitum.ssm.r1.staged_test_only.v1",
            "request_sha256":request_sha,
            "original_intent_hmac_verified_by_scm":False,
            "installed_core_enrollment":False,
            "independent_signer":False}


def verify(root:Path,*,worker_root:Path|None=None):
    from cognitum.mel.ssm_supervisor import SSMComputeFactory
    root=root.resolve(strict=True)
    worker_root=Path(worker_root).resolve(strict=True) if worker_root is not None else root
    request=json.loads((worker_root/"input.frame").read_text(encoding="ascii"))
    output=json.loads((worker_root/"output.frame").read_text(encoding="ascii"))
    stop=json.loads((root/"stop.json").read_text(encoding="ascii"))
    intent=(root/"intent.frame").read_bytes().split(b"\n")
    fields=intent[0].decode("ascii").split("\t")
    if output.keys()!={"reply","status"} or output["status"]!="ok":
        raise ValueError("fixed SSM reply invalid")
    expected=SSMComputeFactory().handle(request["operation"],request["payload"])
    if output["reply"] != expected:
        raise ValueError("SCM worker did not run real unchanged SSM math")
    expected_result=hashlib.sha256((worker_root/"output.frame").read_bytes()).hexdigest()
    if stop != {
        "schema":"cognitum.ssm.r1.scm_local_stop.v1",
        "original_nonce":fields[11],
        "request_sha256":hashlib.sha256((worker_root/"input.frame").read_bytes()).hexdigest(),
        "result_sha256":expected_result,
        "service_pid":stop["service_pid"],"worker_pid":stop["worker_pid"],
        "kernel_job_empty":True,"independently_signed":False,
        "installed_core_authenticated":False,"production_authority":False,
        "output_release_authorized":False
    }:
        raise ValueError("SCM stop receipt not exact original service/worker")
    if any(type(stop[k]) is not int or stop[k]<=0 for k in ("service_pid","worker_pid")):
        raise ValueError("kernel worker/service identity absent")
    return {
        "schema":"cognitum.ssm.r1.real_fixed_math_scm_ci.v1",
        "real_ssm_factory_output_matches":True,
        "original_request_and_nonce_bound":True,
        "scm_service_owned_job_kernel_empty":True,
        "service_owned_durable_write_once_stop":True,
        "stop_receipt_independently_signed":False,
        "signed_installed_publisher":False,
        "worker_restricted_appcontainer":False,
        "core_installed_health_authenticated":False,
        "core_per_turn_grant_verified":False,
        "external_output_authorized":False,
    }


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("prepare","verify"))
    parser.add_argument("--root",required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--runtime-root")
    parser.add_argument("--worker-root")
    args=parser.parse_args()
    if args.mode=="prepare":
        if not args.env_file:
            raise ValueError("GitHub Env path required")
        result=prepare(Path(args.root),Path(args.env_file),
                       runtime_root=Path(args.runtime_root) if args.runtime_root else None,
                       worker_root=Path(args.worker_root) if args.worker_root else None)
    else:
        result=verify(Path(args.root),worker_root=Path(args.worker_root) if args.worker_root else None)
    print(json.dumps(result,sort_keys=True))
