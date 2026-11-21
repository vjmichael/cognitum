"""R3 original-operation signed prelaunch and uncertain-restart refusal.

An ephemeral Python P256 signer emulates mathematical shape ONLY.
Native Windows CI separately proves machine CNG signer, SCM process
generations and interrupted-service restart against exact original blobs.
"""
from __future__ import annotations
import copy
import hashlib
import json
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from scripts.cog_r5_r3_verify_recovery import (
    DOMAINS,FRAME_SCHEMA,ENVELOPE_SCHEMA,RefusedR3Claim,
    verify_original_chain_bytes,
)


def example(kind="uncertain_restart"):
    signer=ec.generate_private_key(ec.SECP256R1())
    pub=signer.public_key().public_numbers()
    blob=b"ECS1\x20\x00\x00\x00"+pub.x.to_bytes(32,"big")+pub.y.to_bytes(32,"big")
    pin=hashlib.sha256(blob).hexdigest()
    original={"schema":"cognitum.ssm.r1.fixture_prelaunch.v1",
       "nonce":"a"*32,"request_sha256":"b"*64,
       "replay_authorized":False,"production_authority":False}
    prelaunch=(json.dumps(original,separators=(",",":"))+"\n").encode()
    sha=hashlib.sha256(prelaunch).digest()

    def sign(which,link,birth,pid):
        body={
          "schema":FRAME_SCHEMA,"kind":which,
          "original_nonce":"a"*32,"request_sha256":"b"*64,
          "source_record_sha256":link,
          "service_pid":pid,"service_creation_filetime":birth,
          "kernel_job_empty_claimed":False,
          "original_replay_authorized":False,"installed_Core_grant":False,
          "installed_publisher_approved":False,
          "production_receipt_issuer_approved":False,
          "external_output_release_authorized":False,
        }
        raw=json.dumps(body,separators=(",",":")).encode()
        signature=signer.sign(DOMAINS[which]+raw,ec.ECDSA(hashes.SHA256()))
        r,s=decode_dss_signature(signature)
        envelope={
           "schema":ENVELOPE_SCHEMA,"frame_hex":raw.hex(),
           "signature_p256_raw":(r.to_bytes(32,"big")+s.to_bytes(32,"big")).hex(),
           "public_blob_sha256":pin,"production_authority":False,
           "output_release_authorized":False,
        }
        return (json.dumps(envelope,separators=(",",":"))+"\n").encode()
    admission=sign("prelaunch_no_execution_proof",sha.hex(),500,100)
    link=hashlib.sha256(sha+admission).hexdigest()
    restart=sign(kind,link,600,200)
    return dict(prelaunch=prelaunch,signed_pre_bytes=admission,
                signed_restart_bytes=restart,public_blob=blob,
                external_pin=pin,expected_kind=kind)


@pytest.mark.parametrize("kind",["uncertain_restart","replay_refused"])
def test_signatures_bind_exact_original_across_two_generations(kind):
    result=verify_original_chain_bytes(**example(kind))
    assert result["signed_original_prelaunch"]
    assert result["signed_original_restart"]
    assert result["restart_kind"]==kind
    assert result["two_distinct_kernel_service_generations"]
    assert result["original_status_success"] is False
    assert result["external_output_release_authorized"] is False


@pytest.mark.parametrize("bad",[
    "prelaunch","signed_pre_bytes","signed_restart_bytes",
    "public_blob","external_pin","expected_kind",
])
def test_tamper_or_foreign_issuer_refused(bad):
    f=example()
    if bad=="prelaunch":f[bad]=f[bad].replace(b"a"*32,b"c"*32)
    elif bad=="signed_pre_bytes":f[bad]=f[bad].replace(b"frame_hex",b"frame_pwn")
    elif bad=="signed_restart_bytes":f[bad]=f[bad].replace(b"output_release_authorized",b"output_release_authorize_")
    elif bad=="public_blob":f[bad]=b"\0"*72
    elif bad=="external_pin":f[bad]="0"*64
    else:f[bad]="replay_refused"
    with pytest.raises(RefusedR3Claim):
        verify_original_chain_bytes(**f)


def test_replayed_service_generation_refused():
    f=example()
    new=json.loads(f["signed_restart_bytes"])
    # Untrusted editor cannot change generation without invalidating signer.
    frame=json.loads(bytes.fromhex(new["frame_hex"]))
    frame["service_creation_filetime"]=500
    new["frame_hex"]=json.dumps(frame,separators=(",",":")).encode().hex()
    f["signed_restart_bytes"]=(json.dumps(new,separators=(",",":"))+"\n").encode()
    with pytest.raises(RefusedR3Claim):
        verify_original_chain_bytes(**f)


def test_new_status_cannot_invent_terminal_kernel_success():
    f=example()
    new=json.loads(f["signed_restart_bytes"])
    frame=json.loads(bytes.fromhex(new["frame_hex"]))
    frame["kernel_job_empty_claimed"]=True
    frame["external_output_release_authorized"]=True
    new["frame_hex"]=json.dumps(frame,separators=(",",":")).encode().hex()
    f["signed_restart_bytes"]=(json.dumps(new,separators=(",",":"))+"\n").encode()
    with pytest.raises(RefusedR3Claim):
        verify_original_chain_bytes(**f)


def test_signed_prelaunch_cannot_be_reused_for_unrelated_nonce():
    f=example()
    orig=json.loads(f["prelaunch"])
    orig["nonce"]="d"*32
    f["prelaunch"]=(json.dumps(orig,separators=(",",":"))+"\n").encode()
    with pytest.raises(RefusedR3Claim):
        verify_original_chain_bytes(**f)
