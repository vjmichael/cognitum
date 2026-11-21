"""Independent R3 CNG original-operation prelaunch and restart verifier.

Native Windows KSP alone signs. This verifier does NOT open the machine
private key, trust a model-selected issuer, call Core, infer a successful
operation from an unsigned file, replay original math, deliver output, or
convert uncertain restart into a terminal success.

The public key pin here is an externally supplied CI test manifest, NOT an
independently approved production publisher/issuer or antirollback anchor.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

DOMAINS={
 "prelaunch_no_execution_proof":b"Cognitum.R3.CI.PRELAUNCH.v1\x00",
 "uncertain_restart":b"Cognitum.R3.CI.UNCERTAIN_RESTART.v1\x00",
 "replay_refused":b"Cognitum.R3.CI.REPLAY_REFUSED.v1\x00",
}
FRAME_SCHEMA="cognitum.ssm.r3.CI_original_receipt_frame.v1"
ENVELOPE_SCHEMA="cognitum.ssm.r3.CI_machine_signed_envelope.v1"


class RefusedR3Claim(ValueError):
    pass


def need(valid, why):
    if not valid:
        raise RefusedR3Claim(why)


def lower_hex(value,size):
    need(type(value) is str and len(value)==size and
         all(c in "0123456789abcdef" for c in value),
         "not exact bounded lowercase hexadecimal")
    return bytes.fromhex(value)


def verify_signature(envelope:dict, public_blob:bytes, public_pin:str):
    need(type(public_blob) is bytes and len(public_blob)==72 and
         public_blob[:8]==b"ECS1\x20\x00\x00\x00",
         "not native Windows CNG ECDSA P256 public blob")
    pin=hashlib.sha256(public_blob).hexdigest()
    need(public_pin==pin and type(envelope) is dict and
         set(envelope)=={
          "schema","frame_hex","signature_p256_raw","public_blob_sha256",
          "production_authority","output_release_authorized"},
         "R3 original signed envelope has missing or invented fields")
    need(envelope["schema"]==ENVELOPE_SCHEMA and
         envelope["public_blob_sha256"]==pin and
         envelope["production_authority"] is False and
         envelope["output_release_authorized"] is False,
         "R3 test issuer differs or invents authorization")
    frame_bytes=lower_hex(envelope["frame_hex"],len(envelope["frame_hex"]))
    sig=lower_hex(envelope["signature_p256_raw"],128)
    need(len(frame_bytes)<=2048 and len(frame_bytes)>0,
         "original R3 signed frame too large or empty")
    x=int.from_bytes(public_blob[8:40],"big")
    y=int.from_bytes(public_blob[40:72],"big")
    try:
        key=ec.EllipticCurvePublicNumbers(x,y,ec.SECP256R1()).public_key()
        r=int.from_bytes(sig[:32],"big")
        s=int.from_bytes(sig[32:],"big")
        der=encode_dss_signature(r,s)
        frame=json.loads(frame_bytes)
        need(type(frame) is dict and set(frame)=={
          "schema","kind","original_nonce","request_sha256",
          "source_record_sha256","service_pid","service_creation_filetime",
          "kernel_job_empty_claimed","original_replay_authorized",
          "installed_Core_grant","installed_publisher_approved",
          "production_receipt_issuer_approved","external_output_release_authorized"},
          "R3 signed frame is not a closed original custody record")
        need(frame["schema"]==FRAME_SCHEMA and
             frame["kind"] in DOMAINS and
             type(frame["service_pid"]) is int and frame["service_pid"]>0 and
             type(frame["service_creation_filetime"]) is int and
             frame["service_creation_filetime"]>0 and
             all(frame[k] is False for k in (
              "kernel_job_empty_claimed","original_replay_authorized",
              "installed_Core_grant","installed_publisher_approved",
              "production_receipt_issuer_approved","external_output_release_authorized")),
             "signed R3 prelaunch/restart cannot assert completion or grants")
        lower_hex(frame["original_nonce"],32)
        lower_hex(frame["request_sha256"],64)
        lower_hex(frame["source_record_sha256"],64)
        key.verify(der,DOMAINS[frame["kind"]]+frame_bytes,
                   ec.ECDSA(hashes.SHA256()))
    except (ValueError,UnicodeDecodeError,InvalidSignature,TypeError,KeyError) as exc:
        raise RefusedR3Claim("R3 P256 signature, domain, or closed custody claim rejected") from exc
    return frame


def verify_original_chain(*,prelaunch:bytes,signed_pre:dict,
                          signed_restart:dict,public_blob:bytes,
                          external_pin:str,expected_kind:str):
    need(type(prelaunch) is bytes and 1<=len(prelaunch)<=512,
         "original write-once prelaunch marker missing")
    try:
        marker=json.loads(prelaunch)
    except (ValueError,UnicodeDecodeError) as exc:
        raise RefusedR3Claim("original prelaunch JSON invalid") from exc
    need(type(marker) is dict and
         set(marker)=={"schema","nonce","request_sha256",
                       "replay_authorized","production_authority"} and
         marker["schema"]=="cognitum.ssm.r1.fixture_prelaunch.v1" and
         marker["replay_authorized"] is False and
         marker["production_authority"] is False,
         "untrusted original operation marker cannot be admitted")
    pre=verify_signature(signed_pre,public_blob,external_pin)
    new=verify_signature(signed_restart,public_blob,external_pin)
    need(pre["kind"]=="prelaunch_no_execution_proof" and
         new["kind"]==expected_kind and
         expected_kind in ("uncertain_restart","replay_refused") and
         pre["original_nonce"]==new["original_nonce"]==marker["nonce"] and
         pre["request_sha256"]==new["request_sha256"]==marker["request_sha256"],
         "original operation, nonce or restart status differs")
    original_sha=hashlib.sha256(prelaunch).digest()
    need(pre["source_record_sha256"]==original_sha.hex(),
         "R3 admission signature is not bound to original prelaunch bytes")
    prior_bytes=(json.dumps(signed_pre,separators=(",",":"),ensure_ascii=True)+"\n").encode("ascii")
    # Canonical original signed admission bytes are part of the restart
    # digest: do not recompute from untrusted unordered JSON for native logs.
    # Caller may pass original signed bytes to verify_original_chain_bytes.
    return {
        "pre":pre,"restart":new,
        "original_marker_sha256":original_sha.hex(),
        "expected_restart_link_requires_raw_signed_prelaunch":True,
        "source_signature_valid":True,
        "output_release_authorized":False,
        "production_issuer_accepted":False,
    }


def verify_original_chain_bytes(*,prelaunch:bytes,signed_pre_bytes:bytes,
                                signed_restart_bytes:bytes,public_blob:bytes,
                                external_pin:str,expected_kind:str):
    if any(type(data) is not bytes or len(data)>4096 or not data
           for data in (signed_pre_bytes,signed_restart_bytes)):
        raise RefusedR3Claim("bounded native signed custody records required")
    try:
        signed_pre=json.loads(signed_pre_bytes)
        signed_restart=json.loads(signed_restart_bytes)
    except (ValueError,UnicodeDecodeError) as exc:
        raise RefusedR3Claim("native signed custody bytes not JSON") from exc
    accepted=verify_original_chain(
        prelaunch=prelaunch,signed_pre=signed_pre,
        signed_restart=signed_restart,public_blob=public_blob,
        external_pin=external_pin,expected_kind=expected_kind)
    sha_pre=hashlib.sha256(prelaunch).digest()
    expected=hashlib.sha256(sha_pre+signed_pre_bytes).hexdigest()
    need(accepted["restart"]["source_record_sha256"]==expected,
         "R3 restarted service did not bind original signed prelaunch bytes")
    need(accepted["restart"]["service_creation_filetime"]!=
         accepted["pre"]["service_creation_filetime"],
         "R3 restart not observed in a different real Windows service generation")
    return {
       "schema":"cognitum.ssm.r3.independent_original_recovery_validation.v1",
       "signed_original_prelaunch":True,
       "signed_original_restart":True,
       "restart_kind":expected_kind,
       "two_distinct_kernel_service_generations":True,
       "original_operation_cannot_replay":True,
       "original_status_success":False,
       "kernel_job_empty_from_uncertain_replay_claim":False,
       "external_output_release_authorized":False,
       "independently_approved_production_issuer":False,
    }


def verify_fixture(root:Path,expected_kind:str):
    root=root.resolve(strict=True)
    enroll=json.loads((root/"r2-external-provision.json").read_text(encoding="utf-8-sig"))
    need(enroll["independent_production_publisher_approved"] is False,
         "CI key cannot be an installer-approved production publisher")
    return verify_original_chain_bytes(
       prelaunch=(root/"prelaunch.json").read_bytes(),
       signed_pre_bytes=(root/"r3-signed-prelaunch.json").read_bytes(),
       signed_restart_bytes=(root/"r3-signed-restart.json").read_bytes(),
       public_blob=(root/"r2-public-p256.blob").read_bytes(),
       external_pin=enroll["public_blob_sha256"],
       expected_kind=expected_kind)


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",required=True)
    parser.add_argument("--expected-kind",choices=["uncertain_restart","replay_refused"],
                        required=True)
    args=parser.parse_args()
    print(json.dumps(verify_fixture(Path(args.root),args.expected_kind),sort_keys=True))
