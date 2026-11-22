"""Produce unapproved, canonical *actual byte* manifest for a protected successor.

Does NOT sign, install, approve, create secrets, provision a signer, or unlock Lu.
Requires existing staged closed payload and NSIS from a separate Windows build.
The original frozen runtime must already be independently prepared and pinned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import cog_r3r1_protected_successor_contract as contract


def refuse(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError("PROTECTED_SUCCESSOR_CANDIDATE_REFUSED: " + why)


def sha(path: Path) -> str:
    refuse(path.is_file() and not path.is_symlink(), "real pinned regular file required")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closure(runtime: Path, expected_manifest: str, expected_prov: str, expected_source: str) -> int:
    manifest = runtime / "r3-r1-runtime.manifest"
    provenance = runtime / "r3-r1-runtime-provenance.json"
    refuse(sha(manifest) == expected_manifest and sha(provenance) == expected_prov,
           "independently approved complete runtime manifest/provenance differ")
    body = manifest.read_bytes()
    refuse(body.endswith(b"\n") and 0 < len(body) <= 3145728
           and b"\r" not in body, "canonical frozen import manifest required")
    entries = body[:-1].decode("ascii").split("\n")
    refuse(0 < len(entries) <= 12000, "bounded nonempty original runtime")
    last = ""
    seen = set()
    for entry in entries:
        match = re.fullmatch(r"([0-9a-f]{64})\t([ -~]+)", entry)
        refuse(match is not None, "noncanonical original manifest entry")
        digest, rel = match.groups()
        bits = rel.split("/")
        refuse(rel > last and "\\" not in rel
               and all(b and b not in (".", "..") and not b.endswith((" ", "."))
                       and not any(c in b for c in ':*?"<>|') for b in bits)
               and rel not in seen and not rel.startswith("/"),
               "unsafe, duplicate or out-of-order frozen file path")
        seen.add(rel)
        last = rel
        refuse(sha(runtime.joinpath(*bits)) == digest,
               "frozen code/import changed after external review")
    actual = {p.relative_to(runtime).as_posix() for p in runtime.rglob("*")
              if p.is_file()}
    refuse(actual == seen | {"r3-r1-runtime.manifest",
                              "r3-r1-runtime-provenance.json"},
           "missing or additional production runtime import")
    refuse(not any(p.is_symlink() for p in runtime.rglob("*")),
           "redirecting runtime import prohibited")
    p = json.loads(provenance.read_text(encoding="ascii"))
    refuse(p.get("schema") == "cognitum.ssm.r3r1.production_installer_runtime.v1"
           and p.get("runtime_manifest_sha256") == expected_manifest
           and p.get("external_manifest_approved_for_production") is True
           and p.get("original_production_source_sha") == expected_source
           and p.get("python_sha256") == sha(runtime / "python.exe")
           and p.get("external_python_image_sha256") == sha(runtime / "python.exe")
           and type(p.get("runtime_file_count")) is int
           and p["runtime_file_count"] == len(entries)
           and p.get("actual_Core_grant") is False
           and p.get("external_output_release_authorized") is False
           and p.get("production_release_signer_approved") is False
           and p.get("independent_release_authority_approved") is False,
           "original runtime provenance/source, Python image or authority flags invalid")
    return len(entries)


def candidate(args: argparse.Namespace) -> None:
    root = args.stage.resolve(strict=True)
    payload = root / "payload"
    runtime = payload / "runtime"
    exe = payload / "cognitum-scm-production.exe"
    installer = root / "Cognitum-SSM-R3R1-Protected.exe"
    out = root / "protected-successor.json"
    refuse(root.is_dir() and payload.is_dir() and runtime.is_dir()
           and not out.exists(), "fresh stage without existing manifest required")
    refuse(contract.is_commit(args.source_sha)
           and args.source_sha != contract.CURRENT_NO_WORKER_SOURCE,
           "new original protected source SHA required")
    fp = args.owner_fingerprint
    refuse(re.fullmatch(r"(?:[0-9A-F]{40}|[0-9A-F]{64})", fp) is not None,
           "complete externally confirmed owner primary fingerprint required")
    for name in ("runtime_manifest", "runtime_provenance", "cng_public",
                 "antirollback_public", "lu_issuer_public"):
        refuse(contract.is_sha(getattr(args, name)), "externally pinned "+name)
    count = closure(runtime, args.runtime_manifest, args.runtime_provenance, args.source_sha)
    child = runtime / "cognitum/mel/ssm_r5_production_child.py"
    image_digest = sha(exe)
    nsis_digest = sha(installer)
    refuse(image_digest != contract.CURRENT_NO_WORKER_SERVICE_SHA256
           and nsis_digest != contract.CURRENT_NO_WORKER_INSTALLER_SHA256,
           "old no-worker executable or NSIS cannot masquerade as protected")
    data = {
        "schema": contract.SCHEMA,
        "role": "protected_ssm_production_successor_candidate",
        "source_sha": args.source_sha,
        "approved_gpg_primary_fingerprint": fp,
        "protected_service_name": contract.REQUIRED_SUCCESSOR_SERVICE,
        "replaced_bootstrap_service_name": contract.CURRENT_NO_WORKER_SERVICE,
        "preprovisioned_machine_cng_key_name": args.cng_key_name,
        "protected_runtime_file_count": count,
        "protected_service_image_sha256": image_digest,
        "protected_nsis_installer_sha256": nsis_digest,
        "frozen_runtime_manifest_sha256": args.runtime_manifest,
        "frozen_runtime_provenance_sha256": args.runtime_provenance,
        "frozen_python_image_sha256": sha(runtime / "python.exe"),
        "protected_ssm_child_sha256": sha(child),
        "preprovisioned_machine_cng_public_blob_sha256": args.cng_public,
        "external_antirollback_authority_public_sha256": args.antirollback_public,
        "original_lu_core_issuer_public_sha256": args.lu_issuer_public,
    }
    data.update({key: False for key in contract.REFUSAL_FIELDS})
    raw = contract.canonical_candidate(data)
    digest = hashlib.sha256(raw).hexdigest()
    result = contract.validate(
        raw,
        externally_approved_manifest_sha256=digest,
        externally_approved_source_sha=args.source_sha,
        externally_approved_gpg_primary_fingerprint=fp)
    refuse(result["output_or_ACK_authorized"] is False,
           "candidate manifest cannot create output authority")
    with out.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({
        "status": "UNAPPROVED_PROTECTED_SUCCESSOR_BYTE_CANDIDATE_ONLY",
        "exact_source_sha": args.source_sha,
        "owner_gpg_signature_created": False,
        "candidate_manifest_sha256": digest,
        "protected_service_image_sha256": image_digest,
        "protected_installer_sha256": nsis_digest,
        "frozen_import_file_count": count,
        "independent_reviewer_approved": False,
        "installed_worker_verified": False,
        "external_antirollback_accepted": False,
        "original_lu_core_grant_verified": False,
        "output_or_ACK_authorized": False,
    }, sort_keys=True))



def inspect(args: argparse.Namespace) -> None:
    """Check candidate exact staged bytes before external approval or GPG sign."""
    stage = args.stage.resolve(strict=True)
    raw = (stage / "protected-successor.json").read_bytes()
    manifest_pin = args.approved_candidate
    claim = contract.parse_exact(raw)
    outcome = contract.validate(
        raw, externally_approved_manifest_sha256=manifest_pin,
        externally_approved_source_sha=args.source_sha,
        externally_approved_gpg_primary_fingerprint=args.owner_fingerprint)
    runtime = stage / "payload/runtime"
    count = closure(
        runtime, claim["frozen_runtime_manifest_sha256"],
        claim["frozen_runtime_provenance_sha256"],
        claim["source_sha"])
    checks = (
        ("protected_service_image_sha256",
         stage / "payload/cognitum-scm-production.exe"),
        ("protected_nsis_installer_sha256",
         stage / "Cognitum-SSM-R3R1-Protected.exe"),
        ("frozen_python_image_sha256", runtime / "python.exe"),
        ("protected_ssm_child_sha256",
         runtime / "cognitum/mel/ssm_r5_production_child.py"),
    )
    for key, path in checks:
        refuse(sha(path) == claim[key], "staged original protected bytes: " + key)
    refuse(count == claim["protected_runtime_file_count"],
           "closed original import count changed since review")
    refuse(outcome["output_or_ACK_authorized"] is False,
           "staged original candidate cannot authorize output")
    print(json.dumps({
        "status": "PASS_CANDIDATE_EXACT_STAGED_BYTES_RECHECKED_NOT_APPROVED",
        "manifest_sha256": manifest_pin,
        "all_staged_code_hashes_match": True,
        "complete_frozen_runtime_count": count,
        "independent_approver_identity_verified": False,
        "owner_gpg_signed": False,
        "installed_protected_worker_accepted": False,
        "output_or_ACK_authorized": False,
    },sort_keys=True))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["candidate","inspect"])
    p.add_argument("--stage", type=Path, required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--owner-fingerprint", required=True)
    p.add_argument("--runtime-manifest")
    p.add_argument("--runtime-provenance")
    p.add_argument("--cng-key-name")
    p.add_argument("--cng-public")
    p.add_argument("--antirollback-public")
    p.add_argument("--lu-issuer-public")
    p.add_argument("--approved-candidate")
    args = p.parse_args()
    if args.action=="inspect":
        inspect(args)
    else:
        candidate(args)


if __name__ == "__main__":
    main()
