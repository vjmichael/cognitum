"""Independent read-only review of an UNSIGNED R3-R1 protected successor.

Intentionally does not import its candidate generator/contract. It rehashes
every runtime import, the full NSIS/PE/child/Python and the source checkout.
Its output is a review OBSERVATION, never an independent human approval,
GPG signature, installed custody, Lu grant or permission to run a worker.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

OLD_SOURCE="8c45869214255fc91af53e88e0bfaff6b943696c"
OLD_NSIS="7fe8165b50e34398bdf44f994382800498af5f0a1c2cbb591fce198fd640e14"
OLD_EXE="cb4793cb0bb6b27d4a47e2d4e06380849580f3fedad9b5a8e97a0b989a91e"
OLD_RUNTIME="765f81d3fcf8c5974324bcaacbe994b2a24d2f8cc0d7243beafa4e445c897f28"
PINS=(
 "protected_service_image_sha256","protected_nsis_installer_sha256",
 "frozen_runtime_manifest_sha256","frozen_runtime_provenance_sha256",
 "frozen_python_image_sha256","protected_ssm_child_sha256",
 "preprovisioned_machine_cng_public_blob_sha256",
 "external_antirollback_authority_public_sha256",
 "original_lu_core_issuer_public_sha256",
)
FALSE=(
 "physical_installed_worker_accepted","original_lu_core_issuer_enrolled",
 "original_lu_core_operation_grant_verified",
 "external_antirollback_freshness_verified",
 "external_persistent_signer_approved",
 "production_CNG_terminal_receipts_verified","output_or_ACK_authorized",
)
META=(
 "schema","role","source_sha","approved_gpg_primary_fingerprint",
 "protected_service_name","replaced_bootstrap_service_name",
 "preprovisioned_machine_cng_key_name","protected_runtime_file_count",
)

class ReviewRefused(ValueError): pass

def need(condition: bool, reason: str) -> None:
    if not condition: raise ReviewRefused("INDEPENDENT_BYTE_REVIEW_REFUSED: "+reason)

def digest(path:Path) -> str:
    need(path.is_file() and not path.is_symlink(),"file is missing or redirected")
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda:fh.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def sha_value(value:object)->bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}",value) is not None and value!="0"*64

def unique(pairs):
    record={}
    for k,v in pairs:
        need(k not in record,"duplicate metadata key")
        record[k]=v
    return record

def exact_json(data:bytes, fields:set[str]):
    need(100<=len(data)<=8192 and data.endswith(b"\n") and b"\r" not in data,
         "bounded canonical original metadata required")
    try:
        value=json.loads(data.decode("ascii"),object_pairs_hook=unique)
    except (UnicodeError,ValueError,TypeError) as e:
        raise ReviewRefused("INDEPENDENT_BYTE_REVIEW_REFUSED: invalid metadata") from e
    need(type(value) is dict and set(value)==fields
         and data==(json.dumps(value,sort_keys=True,separators=(",",":"),
                               ensure_ascii=True,allow_nan=False)+"\n").encode("ascii"),
         "closed original canonical metadata fields required")
    return value

def review(stage:Path,source_sha:str,owner_fp:str,
           original_pin:str|None=None,source_checkout:Path|None=None):
    need(type(source_sha) is str and
         re.fullmatch(r"[0-9a-f]{40}",source_sha) is not None
         and source_sha!=OLD_SOURCE,"reviewed new source SHA absent")
    need(type(owner_fp) is str and
         re.fullmatch(r"(?:[0-9A-F]{40}|[0-9A-F]{64})",owner_fp) is not None,
         "exact owner primary GPG identity required")
    need(stage.is_dir() and not stage.is_symlink(),"original candidate stage unavailable")
    root=stage/"payload"
    runtime=root/"runtime"
    need(root.is_dir() and not root.is_symlink()
         and runtime.is_dir() and not runtime.is_symlink(),
         "original complete import staging root unavailable")
    record=stage/"protected-successor.json"
    raw=record.read_bytes()
    actual_pin=hashlib.sha256(raw).hexdigest()
    if original_pin is not None:
        need(sha_value(original_pin) and original_pin==actual_pin,
             "separately supplied candidate manifest digest differs")
    c=exact_json(raw,set(PINS)|set(FALSE)|set(META))
    need(c["schema"]=="cognitum.ssm.r3r1.private_protected_successor_candidate.v1"
         and c["role"]=="protected_ssm_production_successor_candidate"
         and c["protected_service_name"]=="CognitumSsmProtectedV1"
         and c["replaced_bootstrap_service_name"]=="CognitumSsmSupervisorV1"
         and c["source_sha"]==source_sha
         and c["approved_gpg_primary_fingerprint"]==owner_fp,
         "source/role/owner identity is not the protected original")
    need(type(c["protected_runtime_file_count"]) is int
         and 1<=c["protected_runtime_file_count"]<=12000,
         "bounded original import file count required")
    for field in PINS:
        need(sha_value(c[field]),"incomplete original public/byte SHA256: "+field)
    for field in FALSE:
        need(c[field] is False,"unapproved production/Core/output claim: "+field)
    need(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{11,95}",
                      str(c["preprovisioned_machine_cng_key_name"])) is not None,
         "machine CNG key name unreviewed")
    need(c["protected_nsis_installer_sha256"]!=OLD_NSIS and
         c["protected_service_image_sha256"]!=OLD_EXE and
         c["frozen_runtime_manifest_sha256"]!=OLD_RUNTIME,
         "old accepted no-worker bytes may not be repackaged")
    entries={
      "protected_nsis_installer_sha256":stage/"Cognitum-SSM-R3R1-Protected.exe",
      "protected_service_image_sha256":root/"cognitum-scm-production.exe",
      "frozen_python_image_sha256":runtime/"python.exe",
      "protected_ssm_child_sha256":runtime/"cognitum/mel/ssm_r5_production_child.py",
      "frozen_runtime_manifest_sha256":runtime/"r3-r1-runtime.manifest",
      "frozen_runtime_provenance_sha256":runtime/"r3-r1-runtime-provenance.json",
    }
    for field,path in entries.items():
        need(digest(path)==c[field],"candidate byte differs from signed metadata: "+field)
    manifest=(runtime/"r3-r1-runtime.manifest").read_bytes()
    need(0<len(manifest)<=3145728 and manifest.endswith(b"\n")
         and b"\r" not in manifest,"full original sorted import manifest required")
    try: lines=manifest[:-1].decode("ascii").split("\n")
    except UnicodeError as e:
        raise ReviewRefused("INDEPENDENT_BYTE_REVIEW_REFUSED: non-ASCII runtime manifest") from e
    need(len(lines)==c["protected_runtime_file_count"],
         "original frozen file count mismatch")
    previous=""
    reviewed=set()
    casefolded=set()
    total=0
    for line in lines:
        match=re.fullmatch(r"([0-9a-f]{64})\t([ -~]+)",line)
        need(match is not None,"invalid file-hash tuple")
        expected,name=match.groups()
        bits=name.split("/")
        need(name>previous and not name.startswith("/")
             and "\\" not in name and all(bit not in ("",".","..")
             and not bit.endswith((" ","."))
             and not any(x in bit for x in ':*?"<>|') for bit in bits),
             "unsafe or unsorted source path")
        need(name.casefold() not in casefolded,"case-folding Windows path alias")
        casefolded.add(name.casefold())
        reviewed.add(name)
        previous=name
        file=runtime.joinpath(*bits)
        need(file.stat().st_size<=64*1024*1024,"original import exceeds size budget")
        total+=file.stat().st_size
        need(total<=1400*1024*1024,"original runtime exceeds bounded total")
        need(digest(file)==expected,"runtime file differs from full approved manifest")
    found=set()
    for path in runtime.rglob("*"):
        need(not path.is_symlink(),"redirected frozen code path")
        if path.is_file():
            found.add(path.relative_to(runtime).as_posix())
    need(found==reviewed|{"r3-r1-runtime.manifest","r3-r1-runtime-provenance.json"},
         "frozen runtime contains unlisted/missing original code")
    required={
      "python.exe","cognitum/mel/ssm_r5_fixed_child.py",
      "cognitum/mel/ssm_r5_production_child.py",
      "Lib/site-packages/numpy/__init__.py",
      "Lib/site-packages/scipy/__init__.py",
      "Lib/site-packages/google/protobuf/__init__.py",
      "Lib/site-packages/cryptography/__init__.py",
    }
    need(required<=reviewed,"essential frozen interpreter/math/Protobuf dependencies absent")
    prov=json.loads((runtime/"r3-r1-runtime-provenance.json").read_text("ascii"))
    need(type(prov) is dict
         and prov.get("schema")=="cognitum.ssm.r3r1.production_installer_runtime.v1"
         and prov.get("original_production_source_sha")==source_sha
         and prov.get("runtime_manifest_sha256")==c["frozen_runtime_manifest_sha256"]
         and prov.get("python_sha256")==c["frozen_python_image_sha256"]
         and prov.get("external_python_image_sha256")==c["frozen_python_image_sha256"]
         and type(prov.get("runtime_file_count")) is int
         and prov["runtime_file_count"]==len(reviewed)
         and prov.get("external_manifest_approved_for_production") is True
         and all(prov.get(flag) is False for flag in (
            "actual_Core_grant","external_output_release_authorized",
            "production_release_signer_approved",
            "independent_release_authority_approved")),
         "separate full runtime provenance/authority facts invalid")
    source_checked=False
    if source_checkout is not None:
        need(source_checkout.is_dir(),"externally checked out source absent")
        def git(*args):
            p=subprocess.run(["git","-C",str(source_checkout),*args],
                             check=True,capture_output=True,text=True,timeout=15)
            return p.stdout.strip()
        try:
            need(git("rev-parse","HEAD")==source_sha
                 and git("status","--porcelain","--untracked-files=no")=="",
                 "reviewer's clean exact original Git source differs")
        except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
            raise ReviewRefused("INDEPENDENT_BYTE_REVIEW_REFUSED: source checkout not evidenced") from e
        source_checked=True
    return {
       "status":"PASS_INDEPENDENT_IMPLEMENTATION_BYTE_REVIEW_OBSERVATION_ONLY",
       "source_sha":source_sha,
       "manifest_sha256":actual_pin,
       "complete_frozen_import_count":len(reviewed),
       "complete_frozen_import_bytes":total,
       "all_installer_native_and_runtime_hashes_verified":True,
       "read_only_source_checkout_verified":source_checked,
       "independent_reviewer_approved":False,
       "original_owner_GPG_signature_verified":False,
       "nsis_embedded_payload_compared_to_installed_files":False,
       "physical_protected_worker_installed":False,
       "external_antirollback_accepted":False,
       "original_Lu_Core_grant_verified":False,
       "output_or_ACK_authorized":False,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--source-sha",required=True)
    p.add_argument("--owner-fingerprint",required=True)
    p.add_argument("--source-checkout",type=Path,required=True)
    p.add_argument("--expected-candidate-sha256")
    a=p.parse_args()
    print(json.dumps(review(
        a.stage,a.source_sha,a.owner_fingerprint,
        a.expected_candidate_sha256,a.source_checkout),
        sort_keys=True,separators=(",",":")))
