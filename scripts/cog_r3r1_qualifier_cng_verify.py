"""Independent read-only verification of SCM's source-level CNG terminal.

This program has no NCrypt signing/open-private-key operation, no Windows SCM
control API, and cannot issue an original Lu Core grant, output or ACK.
The signature is checked against the independently provisioned CI machine
public blob. Positive evidence remains CI-only pending installed authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

DOMAIN=b"Cognitum.R3R1.CI.PROTECTED_TERMINAL.v1\x00"
HEX="0123456789abcdef"
REQUIRED_BODY={
    "schema", "scm_pid", "worker_pid", "original_request_sha256",
    "candidate_output_sha256", "kernel_job_empty_after_child_exit",
    "original_lu_core_grant_verified", "installed_signer_approved",
    "output_or_ACK_authorized"
}
REQUIRED_ENVELOPE={
    "schema", "terminal_sha256", "public_blob_sha256", "signature_p256_raw",
    "production_issuer_enrollment_verified", "Core_grant_verified",
    "output_or_ACK_authorized"
}

def need(ok:bool,description:str):
    if not ok:
        raise ValueError("Independent CNG terminal refused: "+description)

def parse(raw:bytes, expected:set[str]):
    need(type(raw) is bytes and 80<=len(raw)<=4096 and raw.endswith(b"\n"),
         "closed original terminal bytes required")
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result,"duplicate JSON key")
            result[key]=value
        return result
    try:
        value=json.loads(raw.decode("ascii"),object_pairs_hook=unique)
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Independent CNG terminal JSON refused") from exc
    need(type(value) is dict and set(value)==expected,"exact schema fields")
    return value

def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()

def valid_sha(value):
    return type(value) is str and len(value)==64 and all(c in HEX for c in value)

def verify_exact(body:bytes,envelope:bytes,blob:bytes,
                 original_request:bytes,output:bytes,
                 independently_pinned_public_sha:str):
    need(len(blob)==72 and blob[:8]==b"ECS1\x20\x00\x00\x00",
         "actual Windows ECCPUBLICBLOB P256 public key")
    need(valid_sha(independently_pinned_public_sha),"independent pin format")
    need(hash_bytes(blob)==independently_pinned_public_sha,
         "external signer public key identity mismatch")
    local=parse(body,REQUIRED_BODY)
    claim=parse(envelope,REQUIRED_ENVELOPE)
    need(local["schema"]=="cognitum.ssm.r3r1.ci_protected_terminal.v1"
         and claim["schema"]=="cognitum.ssm.r3r1.ci_p256_terminal_signature.v1",
         "terminal or signer frame schema")
    need(type(local["scm_pid"]) is int and local["scm_pid"]>0
         and type(local["worker_pid"]) is int and local["worker_pid"]>0
         and local["scm_pid"]!=local["worker_pid"],
         "distinct original SCM and OS child PIDs required")
    need(local["kernel_job_empty_after_child_exit"] is True
         and local["original_lu_core_grant_verified"] is False
         and local["installed_signer_approved"] is False
         and local["output_or_ACK_authorized"] is False,
         "signed terminal MUST NOT imply installed production or Core authority")
    need(claim["production_issuer_enrollment_verified"] is False
         and claim["Core_grant_verified"] is False
         and claim["output_or_ACK_authorized"] is False,
         "signature MUST NOT imply original result release")
    need(local["original_request_sha256"]==hash_bytes(original_request)
         and local["candidate_output_sha256"]==hash_bytes(output),
         "same original request/answer bound in signed terminal")
    need(claim["terminal_sha256"]==hash_bytes(body)
         and claim["public_blob_sha256"]==independently_pinned_public_sha,
         "signed exact original terminal/public digests")
    raw=claim["signature_p256_raw"]
    need(type(raw) is str and len(raw)==128 and all(c in HEX for c in raw),
         "CNG P256 raw signature length/encoding")
    sig=bytes.fromhex(raw)
    public=ec.EllipticCurvePublicNumbers(
        int.from_bytes(blob[8:40],"big"),
        int.from_bytes(blob[40:72],"big"),
        ec.SECP256R1()).public_key()
    der=encode_dss_signature(int.from_bytes(sig[:32],"big"),
                             int.from_bytes(sig[32:],"big"))
    try:
        public.verify(der,DOMAIN+body,ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise ValueError("Independent CNG signature verification refused") from exc
    return {"kernel_job_stopped_claim_signed": True,
            "original_request_bound":True,
            "candidate_output_bound":True,
            "actual_installed_production_authority":False,
            "Lu_Core_per_operation_grant":False,
            "independently_monotonic_replay_protection":False,
            "output_or_ACK_authorized":False}

def main():
    need(sys.platform=="win32" and os.environ.get("GITHUB_ACTIONS")=="true",
         "original disposable native Windows verification required")
    base=Path(os.environ["GITHUB_WORKSPACE"])/"native/windows_scm_production/target"
    host=base/"q-host"
    io=base/"q-io"
    body=(host/"production-terminal.json").read_bytes()
    envelope=(host/"production-terminal-signed.json").read_bytes()
    blob=(host/"r2-public-p256.blob").read_bytes()
    data=(io/"input.frame").read_bytes()
    answer=(io/"output.frame").read_bytes()
    pin=os.environ["COG_R2_CI_PUBLIC_SHA256"]
    verified=verify_exact(body,envelope,blob,data,answer,pin)
    original_claim=parse(body,REQUIRED_BODY)
    receipt=json.loads(Path("q-scm-receipt.json").read_text())
    need(original_claim["worker_pid"]==receipt["original_non_SYSTEM_worker_pid"]
         and original_claim["candidate_output_sha256"]==receipt["output_sha256"],
         "signed candidate not the original observed kernel SCM operation")
    tamper=0
    attacks=[
      (body.replace(b'"kernel_job_empty_after_child_exit":true',
                    b'"kernel_job_empty_after_child_exit":false'),
       envelope,blob,data,answer,pin),
      (body,envelope,blob,data+b"x",answer,pin),
      (body,envelope,blob,data,answer+b"x",pin),
      (body,envelope,blob,data,answer,("b" if pin[0]!="b" else "a")+pin[1:]),
      (body,envelope.replace(b'"Core_grant_verified":false',
                              b'"Core_grant_verified":true'),
       blob,data,answer,pin),
    ]
    for index,params in enumerate(attacks):
        need(params!=(body,envelope,blob,data,answer,pin),
             "adversarial mutation did not change original bytes")
        try:
            verify_exact(*params)
        except (ValueError,TypeError):
            tamper+=1
        else:
            raise AssertionError("tampered CNG terminal accepted at case "+str(index))
    need(tamper==len(attacks),"all original malicious variants must fail")
    print(json.dumps({
      "schema":"cognitum.ssm.r3r1.ci_independent_p256_terminal_audit.v1",
      "status":"PASS_CI_INDEPENDENT_ORIGINAL_SSM_MACHINE_CNG_TERMINAL_VERIFIED",
      "same_original_request_and_worker":True,
      "adversarial_signer_or_terminal_mutations_refused":tamper,
      "CNG_signing_authority_independent_production":False,
      "Lu_Core_grant_verified":False,
      "external_antirollback_accepted":False,
      "output_release_authorized":False,
    },sort_keys=True))
if __name__=="__main__":
    main()
