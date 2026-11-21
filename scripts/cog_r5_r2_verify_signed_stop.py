"""Independent verification of an externally provisioned Windows CNG P256 test stop.

This verifier never opens an OS signing key, grants Core execution, creates
a service, or releases model/SSM output. The independently approved production
issuer, publisher and monotonic antirollback remain absent. A valid temporary
CI signature is NOT installed identity or Core authorization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

DOMAIN=b"Cognitum.R2.CI.SCM_STOP.v1\x00"
SCHEMA="cognitum.ssm.r2.CI_CNG_signed_stop.v1"


class RejectedSignedStop(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise RejectedSignedStop(reason)


def verify_raw(*, local_stop:bytes,signed:dict,public_blob:bytes,
               approved_public_sha256:str, original_request_sha256:str,
               original_nonce:str,expected_service_pid:int,
               expected_worker_pid:int):
    need(type(local_stop) is bytes and 1<=len(local_stop)<=2048,
         "bounded original local kernel stop")
    need(type(public_blob) is bytes and len(public_blob)==72 and
         public_blob[:8]==b"ECS1\x20\x00\x00\x00",
         "exact Windows CNG P256 public key")
    keyhash=hashlib.sha256(public_blob).hexdigest()
    need(type(approved_public_sha256) is str and
         len(approved_public_sha256)==64 and
         keyhash==approved_public_sha256,"independently approved R2 test signer pin")
    need(type(signed) is dict and set(signed)=={
         "schema","kernel_stop_sha256","public_blob_sha256",
         "signature_p256_raw","preprovisioned_os_machine_key",
         "installed_publisher_accepted","independent_prod_signer_accepted",
         "Core_authenticated","output_release_authorized"},
         "closed signed envelope")
    need(signed["schema"]==SCHEMA and
         signed["kernel_stop_sha256"]==hashlib.sha256(local_stop).hexdigest() and
         signed["public_blob_sha256"]==keyhash and
         signed["preprovisioned_os_machine_key"] is True and
         signed["installed_publisher_accepted"] is False and
         signed["independent_prod_signer_accepted"] is False and
         signed["Core_authenticated"] is False and
         signed["output_release_authorized"] is False,
         "signed kernel-stop link and no production authority")
    try:
        bytes64=bytes.fromhex(signed["signature_p256_raw"])
    except (TypeError,ValueError) as exc:
        raise RejectedSignedStop("missing exact P256 signature") from exc
    need(len(bytes64)==64 and len(signed["signature_p256_raw"])==128 and
         signed["signature_p256_raw"]==bytes64.hex(),
         "canonical P256 raw signing bytes")
    x=int.from_bytes(public_blob[8:40],"big")
    y=int.from_bytes(public_blob[40:72],"big")
    try:
        pk=ec.EllipticCurvePublicNumbers(x,y,ec.SECP256R1()).public_key()
        sig=encode_dss_signature(int.from_bytes(bytes64[:32],"big"),
                                 int.from_bytes(bytes64[32:],"big"))
        pk.verify(sig,DOMAIN+local_stop,ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature,ValueError) as exc:
        raise RejectedSignedStop("native CNG P256 signature invalid") from exc
    try:
        body=json.loads(local_stop)
    except (ValueError,UnicodeDecodeError) as exc:
        raise RejectedSignedStop("original local stop is not JSON") from exc
    need(type(body) is dict and
         body["schema"]=="cognitum.ssm.r1.scm_local_stop.v1" and
         body["original_nonce"]==original_nonce and
         body["request_sha256"]==original_request_sha256 and
         body["service_pid"]==expected_service_pid and
         body["worker_pid"]==expected_worker_pid and
         body["kernel_job_empty"] is True and
         body["independently_signed"] is False and
         body["installed_core_authenticated"] is False and
         body["output_release_authorized"] is False and
         body["production_authority"] is False,
         "original nonce/request/service/worker kernel binding differs")
    return {
        "schema":"cognitum.ssm.r2.external_CNG_source_verification.v1",
        "real_native_CNG_signature_valid":True,
        "exact_original_SSM_request_and_nonce_bound":True,
        "scm_job_kernel_empty_record_linked":True,
        "public_blob_sha256":keyhash,
        "production_issuer_independently_enrolled":False,
        "signed_publisher_installed":False,
        "external_monotonic_antirollback":False,
        "real_core_health_authenticated":False,
        "external_output_release_authorized":False,
    }


def verify_files(root:Path):
    root=root.resolve(strict=True)
    signed=json.loads((root/"r2-signed-stop.json").read_text(encoding="ascii"))
    provision=json.loads((root/"r2-external-provision.json").read_text(encoding="utf-8-sig"))
    prelaunch=json.loads((root/"prelaunch.json").read_text(encoding="ascii"))
    stop=json.loads((root/"stop.json").read_text(encoding="ascii"))
    need(provision["schema"]=="cognitum.ssm.r2.CI_external_KSP_enrollment.v1" and
         provision["independent_production_publisher_approved"] is False and
         provision["externally_anchored_antirollback"] is False,
         "external test KSP signer marker absent or claims installed")
    return verify_raw(
        local_stop=(root/"stop.json").read_bytes(),
        signed=signed,public_blob=(root/"r2-public-p256.blob").read_bytes(),
        approved_public_sha256=provision["public_blob_sha256"],
        original_request_sha256=prelaunch["request_sha256"],
        original_nonce=prelaunch["nonce"],
        expected_service_pid=stop["service_pid"],
        expected_worker_pid=stop["worker_pid"],
    )


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",required=True)
    args=parser.parse_args()
    print(json.dumps(verify_files(Path(args.root)),sort_keys=True))
