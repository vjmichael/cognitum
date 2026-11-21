"""Compile both exact Lu-owned workspace and Cognitum-owned SSM v1 sources.

Native grpcio-tools protoc only: no model-generated serializers or copied
Lu Core implementations. Output is reproducible descriptor+Python artifacts.
"""
from __future__ import annotations
import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path

LU="lu/workspace/v0/workspace.proto"
SSM="cognitum/ssm/v1/ssm.proto"
PINS={
    LU:"4e01d921197fb1c58c99958479b1cede36e13c9a",
    SSM:"755562254afdbea686ee33b95567c505f2f85e49",
}

def compile_pair(root: Path, descriptor: Path):
    from grpc_tools import protoc
    from google.protobuf.descriptor_pb2 import FileDescriptorSet
    root=root.resolve(strict=True)
    if not descriptor.is_absolute():
        raise ValueError("absolute binary descriptor output required")
    identities={}
    for relative,expected in PINS.items():
        raw=(root/relative).read_bytes()
        git=sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()
        if git!=expected:raise ValueError("Lu/Cognitum native proto source drift: "+relative)
        identities[relative]=dict(git_blob_sha=git,sha256=sha256(raw).hexdigest())
    descriptor.parent.mkdir(parents=True,exist_ok=True)
    result=protoc.main([
        "grpc_tools.protoc","-I"+str(root),
        "--python_out="+str(root),
        "--descriptor_set_out="+str(descriptor),
        "--include_imports",
        str(root/LU),str(root/SSM),
    ])
    if result!=0:raise RuntimeError("real native protoc Lu/SSM compile failed")
    fds=FileDescriptorSet.FromString(descriptor.read_bytes())
    if {f.name for f in fds.file}!={LU,SSM}:
        raise ValueError("compiled descriptor dependency set differs")
    expected_packages={LU:"lu.workspace.v0",SSM:"cognitum.mel.ssm.v1"}
    if any(f.package!=expected_packages[f.name] for f in fds.file):
        raise ValueError("compiled owner namespace differs")
    built={}
    for relative in PINS:
        py=root/relative.replace(".proto","_pb2.py")
        if not py.exists():raise RuntimeError("generated native code missing: "+str(py))
        built[relative]=sha256(py.read_bytes()).hexdigest()
    return dict(schema="cognitum.lu_ipc01c_r1.native_protoc_compilation.v1",
        exact_owner_sources=identities,
        generated_python_sha256=built,
        composite_descriptor_sha256=sha256(descriptor.read_bytes()).hexdigest(),
        exact_lu_workspace_proto_preserved=True,
        cognitum_domain_proto_compiled=True,
        live_registration_authorized=False,
        genuine_installed_lu_core_connected=False)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True)
    ap.add_argument("--descriptor-out",required=True)
    ap.add_argument("--receipt",required=True)
    args=ap.parse_args()
    record=compile_pair(Path(args.root),Path(args.descriptor_out))
    Path(args.receipt).write_text(json.dumps(record,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,sort_keys=True))

if __name__=="__main__":
    main()
