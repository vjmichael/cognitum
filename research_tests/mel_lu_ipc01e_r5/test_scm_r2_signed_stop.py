"""R2 independent signed-stop verification; no test cert is production authority."""
import copy
import hashlib
import json
import pytest
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from scripts.cog_r5_r2_verify_signed_stop import (
    DOMAIN,SCHEMA,RejectedSignedStop,verify_raw,
)


def example():
    key=ec.generate_private_key(ec.SECP256R1())
    pub=key.public_key().public_numbers()
    blob=b"ECS1\x20\x00\x00\x00"+pub.x.to_bytes(32,"big")+pub.y.to_bytes(32,"big")
    body={
        "schema":"cognitum.ssm.r1.scm_local_stop.v1",
        "original_nonce":"a"*32,
        "request_sha256":"b"*64,
        "result_sha256":"c"*64,
        "service_pid":101,"worker_pid":102,
        "kernel_job_empty":True,
        "independently_signed":False,
        "installed_core_authenticated":False,
        "production_authority":False,
        "output_release_authorized":False,
    }
    local=(json.dumps(body,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
    d=key.sign(DOMAIN+local,ec.ECDSA(hashes.SHA256()))
    r,s=decode_dss_signature(d)
    signed={
        "schema":SCHEMA,
        "kernel_stop_sha256":hashlib.sha256(local).hexdigest(),
        "public_blob_sha256":hashlib.sha256(blob).hexdigest(),
        "signature_p256_raw":(r.to_bytes(32,"big")+s.to_bytes(32,"big")).hex(),
        "preprovisioned_os_machine_key":True,
        "installed_publisher_accepted":False,
        "independent_prod_signer_accepted":False,
        "Core_authenticated":False,
        "output_release_authorized":False,
    }
    kwargs={
        "local_stop":local,"signed":signed,"public_blob":blob,
        "approved_public_sha256":hashlib.sha256(blob).hexdigest(),
        "original_request_sha256":"b"*64,"original_nonce":"a"*32,
        "expected_service_pid":101,"expected_worker_pid":102,
    }
    return kwargs


def test_separately_verifiable_p256_signature_never_grants_output():
    result=verify_raw(**example())
    assert result["real_native_CNG_signature_valid"]
    assert result["exact_original_SSM_request_and_nonce_bound"]
    assert result["external_output_release_authorized"] is False
    assert result["production_issuer_independently_enrolled"] is False


@pytest.mark.parametrize("alter",[
    {"approved_public_sha256":"0"*64},
    {"original_request_sha256":"0"*64},
    {"original_nonce":"0"*32},
    {"expected_service_pid":999},
    {"expected_worker_pid":999},
    {"public_blob":b"bad"},
    {"local_stop":b"{}"},
])
def test_foreign_original_or_signer_pin_is_refused(alter):
    kwargs=dict(example(),**alter)
    with pytest.raises(RejectedSignedStop):
        verify_raw(**kwargs)


@pytest.mark.parametrize("field,value",[
    ("schema","foreign"),
    ("kernel_stop_sha256","0"*64),
    ("public_blob_sha256","0"*64),
    ("signature_p256_raw","0"*128),
    ("preprovisioned_os_machine_key",False),
    ("installed_publisher_accepted",True),
    ("independent_prod_signer_accepted",True),
    ("Core_authenticated",True),
    ("output_release_authorized",True),
])
def test_tampered_signature_link_and_production_flags_refused(field,value):
    kwargs=example()
    signed=copy.deepcopy(kwargs["signed"])
    signed[field]=value
    kwargs["signed"]=signed
    with pytest.raises(RejectedSignedStop):
        verify_raw(**kwargs)


def test_extra_signed_field_refused_not_reinterpreted_as_grant():
    kwargs=example()
    signed=dict(kwargs["signed"],execute_tools=True)
    with pytest.raises(RejectedSignedStop):
        verify_raw(**dict(kwargs,signed=signed))
