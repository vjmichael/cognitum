"""Reproducible compilation of exact Lu-owned workspace v0 Protobuf source.

Run under the pinned grpcio-tools and protobuf dependencies. The vendored
.proto is a source-locked input for an otherwise uninstalled Cognitum client,
not an independent protocol authority. Generated Python code is build output.
"""
from __future__ import annotations

import argparse
from hashlib import sha1, sha256
from pathlib import Path
import sys

PIN = "4e01d921197fb1c58c99958479b1cede36e13c9a"
PROTO_RELATIVE = Path("lu/workspace/v0/workspace.proto")


def compile_workspace_proto(root: Path, descriptor_path: Path) -> dict:
    from grpc_tools import protoc
    root = root.resolve(strict=True)
    path = root / PROTO_RELATIVE
    raw = path.read_bytes()
    git_blob = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    if git_blob != PIN:
        raise ValueError("Lu-owned Protobuf source drift or newline conversion: " + git_blob)
    if not descriptor_path.is_absolute():
        raise ValueError("absolute descriptor output path required")
    descriptor_path.parent.mkdir(parents=True, exist_ok=True)
    result = protoc.main([
        "grpc_tools.protoc", "-I" + str(root),
        "--python_out=" + str(root),
        "--descriptor_set_out=" + str(descriptor_path),
        str(path),
    ])
    if result != 0:
        raise RuntimeError("Lu workspace v0 native protoc compilation failed")
    py = root / "lu/workspace/v0/workspace_pb2.py"
    if not py.is_file() or not descriptor_path.is_file():
        raise RuntimeError("missing compiled Lu workspace Protobuf artifacts")
    return dict(
        source_git_blob=git_blob,
        source_sha256=sha256(raw).hexdigest(),
        descriptor_sha256=sha256(descriptor_path.read_bytes()).hexdigest(),
        python_generated_sha256=sha256(py.read_bytes()).hexdigest(),
        source_path=str(PROTO_RELATIVE).replace("\\", "/"),
        generated_py="lu/workspace/v0/workspace_pb2.py",
        contract_compiled=True,
        installed_lu_host_connection_qualified=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--descriptor-out", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    import json
    receipt = compile_workspace_proto(Path(args.root), Path(args.descriptor_out))
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
