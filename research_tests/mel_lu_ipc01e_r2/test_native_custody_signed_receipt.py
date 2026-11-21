"""01E-R2: native OS custody and signed external receipt *proposal* refusals.

The signer is a synthetic test private key, NOT a Lu Core native signer.
An in-process trust pin is not installed publisher enrollment. All tests must
finish with no authorized output delivery, R6 ack or model execution.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from cognitum.mel import admission as mel
from cognitum.mel import lu_ipc_lifecycle as life
from cognitum.mel import lu_ipc_native_custody as custody
from cognitum.mel import lu_ipc_receipt_attestation as attest
from cognitum.mel.ssm_os_credentials import OSCredentialBroker, CredentialUnavailable
from cognitum.mel.ssm_revision_cas import LocalAuthenticatedRevisionCAS
from cognitum.mel.vendor.lu.workspace.v0 import workspace_pb2 as lu
from research_tests.mel_lu_ipc01e.test_outbox_reconcile import (
    combined, reconcile_terminal, observe, EVENT, SESSION, EPOCH,
)

NOW=1837440000000
PKG=hashlib.sha256(b"separately installed Core package fixture").digest()
GRANT=hashlib.sha256(b"original Lu user-turn grant synthetic test").hexdigest()
NONCE=hashlib.sha256(b"one original issuer evidence nonce").hexdigest()


def make_proposal(sample, change=None):
    if change is None:change={}
    verifier=sample["verifier"]
    original=sample["origin"]
    terminal=sample["terminal"]
    issuer=Ed25519PrivateKey.generate()
    pub=issuer.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    pinned=attest.ExternallyPinnedCoreIssuer(
        public_key_ed25519=pub,
        trusted_package_sha256=PKG,
        permitted_core_session_ref=SESSION,
        permitted_core_epoch_ref=EPOCH)
    payload={
        "schema":attest.ENVELOPE_SCHEMA,
        "origin":[original.workspace_ref,original.conversation_ref,
                  original.user_turn_ref,original.task_ref,
                  original.operation_ref],
        "core_session_ref":SESSION,
        "core_epoch_ref":EPOCH,
        "operation_ref":EVENT,
        "capability_id":verifier._prepared and
            "cognitum.ssm.fixed_duration.advance.v1",
        "effect":"PURE_COMPUTE",
        "receipt_sha256":hashlib.sha256(
            terminal.SerializeToString(deterministic=True)).hexdigest(),
        "issuer_package_sha256":PKG.hex(),
        "grant_digest_sha256":GRANT,
        "outbox_sha256":verifier.status()["original_outbox_snapshot_sha256"],
        "nonce_sha256":NONCE,
        "not_before_unix_ms":NOW-2000,
        "expires_unix_ms":NOW+2000,
    }
    payload.update(change)
    raw=attest._canonical(payload)
    sig=issuer.sign(attest.DOMAIN+raw)
    return dict(verifier=verifier,pinned_issuer=pinned,signed_claim=raw,
                signature_ed25519=sig,
                verified_host_grant_digest_sha256=GRANT,now_unix_ms=NOW)


def prepared(sample):
    reconcile_terminal(sample)
    observed=observe(sample)
    assert observed["original_output_count"]==1
    return sample


def check(payload,**changes):
    arg=dict(payload)
    arg.update(changes)
    return attest.inspect_proposed_signed_core_receipt(**arg)


def test_signed_provisional_receipt_bound_to_original_but_all_delivery_denied(combined):
    prepared(combined)
    proof=make_proposal(combined)
    result=check(proof)
    assert result["signer_mathematically_verified_against_supplied_pin"]
    assert result["source_operation_ref"]==EVENT
    assert result["original_typed_request_sha256"]==combined["verifier"]._prepared.typed_request_sha256
    assert result["local_outbox_inventory_sha256"]==combined["verifier"].status()["original_outbox_snapshot_sha256"]
    assert not result["signed_Lu_Core_production_provenance_verified"]
    assert not result["genuine_Core_per_turn_grant_authorized"]
    assert not result["output_delivery_authorized"]
    assert not result["output_acknowledgment_authorized"]
    assert not result["result_publication_authorized"]
    assert combined["journal"].status()["pending_outputs"]==1
    assert combined["verifier"].status()["provisional_issuer_attestation_observed"]


def test_provisional_signature_replay_refused_even_after_original_log_restart(combined):
    prepared(combined)
    proof=make_proposal(combined)
    check(proof)
    with pytest.raises(ValueError,match="lifecycle refused"):
        check(proof)
    old=combined["verifier"]
    old.close()
    args=combined["kwargs"]
    new=life.DurableLuOperationVerifier(
        args["directory"],args["broker"],args["anchor"],
        trusted_origin=args["trusted_origin"],
        request_id=args["request_id"],
        core_session_ref=args["core_session_ref"],
        core_epoch_ref=args["core_epoch_ref"],
        prepared=args["prepared"],original_invoke=args["original_invoke"])
    combined["verifier"]=new
    with pytest.raises(ValueError,match="lifecycle refused"):
        check(dict(proof,verifier=new))
    assert not new.status()["result_publication_authorized"]


@pytest.mark.parametrize("change",[
 {"schema":"wrong"},
 {"core_session_ref":"other-session"},
 {"core_epoch_ref":"wrong-epoch"},
 {"operation_ref":"event-003"},
 {"origin":["workspace","conversation","wrong-turn","task",EVENT]},
 {"capability_id":"cognitum.vfa.evaluate"},
 {"effect":"READ_WORKSPACE"},
 {"receipt_sha256":"f"*64},
 {"issuer_package_sha256":"a"*64},
 {"grant_digest_sha256":"b"*64},
 {"outbox_sha256":"c"*64},
 {"nonce_sha256":"0"*64},
 {"nonce_sha256":"not-a-hex"},
 {"not_before_unix_ms":NOW+3000},
 {"expires_unix_ms":NOW-3000},
 {"expires_unix_ms":NOW+70000},
])
def test_forged_or_expired_original_evidence_denied_without_consumption(combined,change):
    prepared(combined)
    proof=make_proposal(combined,change=change)
    with pytest.raises(ValueError,match="attestation refused"):
        check(proof)
    assert not combined["verifier"].status()["provisional_issuer_attestation_observed"]
    assert not combined["verifier"].status()["result_publication_authorized"]


def test_corrupted_signature_and_foreign_trust_pin_denied(combined):
    prepared(combined)
    proof=make_proposal(combined)
    bad=bytearray(proof["signature_ed25519"])
    bad[0]^=1
    with pytest.raises(ValueError,match="signature"):
        check(proof,signature_ed25519=bytes(bad))
    other=Ed25519PrivateKey.generate()
    other_pub=other.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    foreign=attest.ExternallyPinnedCoreIssuer(
        public_key_ed25519=other_pub,
        trusted_package_sha256=PKG,
        permitted_core_session_ref=SESSION,
        permitted_core_epoch_ref=EPOCH)
    with pytest.raises(ValueError,match="signature"):
        check(proof,pinned_issuer=foreign)
    assert not combined["verifier"].status()["provisional_issuer_attestation_observed"]


def test_original_turn_grant_pin_and_host_epoch_cannot_be_bypassed(combined):
    prepared(combined)
    proof=make_proposal(combined)
    with pytest.raises(ValueError,match="original-turn grant"):
        check(proof,verified_host_grant_digest_sha256="f"*64)
    wrong=attest.ExternallyPinnedCoreIssuer(
        public_key_ed25519=proof["pinned_issuer"].public_key_ed25519,
        trusted_package_sha256=PKG,
        permitted_core_session_ref=SESSION,
        permitted_core_epoch_ref="untrusted-epoch")
    with pytest.raises(ValueError,match="session/epoch"):
        check(proof,pinned_issuer=wrong)


def test_unsigned_unknown_noncanonical_and_oversized_evidence_refused(combined):
    prepared(combined)
    proof=make_proposal(combined)
    for raw in (proof["signed_claim"]+b" ",b"not json",
                b"x"*(attest.MAX_WIRE+1)):
        with pytest.raises(ValueError,match="attestation refused"):
            check(proof,signed_claim=raw)
    with pytest.raises(ValueError,match="attestation refused"):
        check(proof,signature_ed25519=b"bad")


def test_cancel_or_revoked_original_cannot_later_admit_signed_evidence(combined):
    prepared(combined)
    proof=make_proposal(combined)
    combined["verifier"].note_revoke("operator_revoke")
    with pytest.raises(ValueError,match="attestation refused"):
        check(proof)
    assert combined["journal"].status()["pending_outputs"]==1


def test_uncertain_hold_blocks_signature_observation_and_pending_output_delivery(combined):
    prepared(combined)
    proof=make_proposal(combined)
    combined["verifier"].note_uncertain_hold("delivery_unknown")
    with pytest.raises(ValueError,match="attestation refused"):
        check(proof)
    assert combined["journal"].status()["pending_outputs"]==1


def test_unreconciled_original_receipt_cannot_become_signed_authority(combined):
    # R6 still contains a verified row, but the original Lu operation
    # has not observed an authenticated reconciled terminal.
    proof=make_proposal(combined)
    with pytest.raises(ValueError,match="attestation refused"):
        check(proof)


def _native_context(tmp_path,combined):
    root=tmp_path/"native-os-owned"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    original=combined["origin"]
    scope=mel.Scope(SESSION,original.workspace_ref,"scientific-subject",
                    original.user_turn_ref)
    broker=OSCredentialBroker(str(root),namespace="ipc"+uuid.uuid4().hex)
    sid=original.operation_ref
    try:
        broker.provision(scope,sid,bytes(range(1,33)))
    except CredentialUnavailable:
        if sys.platform=="win32":
            pytest.fail("Win32 DPAPI native OS custody required")
        assert sys.platform.startswith("linux")
        with pytest.raises(CredentialUnavailable):
            broker.borrow_key(scope,sid)
        return None
    cas=LocalAuthenticatedRevisionCAS(str(root),broker,
         namespace="ipc"+uuid.uuid4().hex,create=True)
    native=custody.OriginalLuOperationNativeCustody(
        trusted_origin=original,mel_scope=scope,
        core_session_ref=SESSION,
        credential_broker=broker,local_revision_cas=cas)
    return native,broker,cas,scope,root


def test_existing_windows_dpapi_or_linux_kernel_keyring_custody_and_local_CAS(combined,tmp_path):
    result=_native_context(tmp_path,combined)
    if result is None:
        return # Explicit kernel keyring refusal, NO plaintext fallback.
    native,broker,cas,scope,root=result
    try:
        evidence=native.evidence()
        assert evidence["actual_native_os_broker_object_used"]
        assert not evidence["external_independent_monotonic_anchor_verified"]
        assert not evidence["genuine_installed_core_session_verified"]
        args=combined["kwargs"]
        observer=life.DurableLuOperationVerifier(
            str(tmp_path/"native-original-log"),native,native,
            trusted_origin=args["trusted_origin"],
            request_id=args["request_id"],
            core_session_ref=args["core_session_ref"],
            core_epoch_ref=args["core_epoch_ref"],
            prepared=args["prepared"],original_invoke=args["original_invoke"])
        before=observer.status()
        assert before["durable_local_revision"]==1
        observer.note_credit(1,0)
        saved=observer.status()
        observer.close()
        again=life.DurableLuOperationVerifier(
            str(tmp_path/"native-original-log"),native,native,
            trusted_origin=args["trusted_origin"],
            request_id=args["request_id"],
            core_session_ref=args["core_session_ref"],
            core_epoch_ref=args["core_epoch_ref"],
            prepared=args["prepared"],original_invoke=args["original_invoke"])
        try:
            assert again.status()==saved
            with pytest.raises(ValueError,match="custody refused"):
                native.borrow_key(("foreign",)*5,EVENT)
        finally:again.close()
        assert not any(bytes(range(1,33)) in p.read_bytes()
                       for p in root.iterdir() if p.is_file())
    finally:
        cas.close()
        broker.revoke(scope,EVENT)


def test_native_custody_refuses_forged_provider_without_auto_enrollment(combined,tmp_path):
    orig=combined["origin"]
    scope=mel.Scope(SESSION,orig.workspace_ref,"scientific-subject",
                    orig.user_turn_ref)
    with pytest.raises(ValueError,match="custody refused"):
        custody.OriginalLuOperationNativeCustody(
            trusted_origin=orig,mel_scope=scope,
            core_session_ref=SESSION,credential_broker=object(),
            local_revision_cas=object())
    wrong=mel.Scope("other-session",orig.workspace_ref,
                    "scientific-subject",orig.user_turn_ref)
    with pytest.raises(ValueError,match="custody refused"):
        custody.OriginalLuOperationNativeCustody(
            trusted_origin=orig,mel_scope=wrong,
            core_session_ref=SESSION,credential_broker=object(),
            local_revision_cas=object())


def test_no_delivery_ack_worker_or_issuer_private_key_API():
    assert not hasattr(attest,"sign_lu_core_receipt")
    assert not hasattr(attest,"publish")
    assert not hasattr(attest,"deliver")
    assert not hasattr(attest,"acknowledge")
    assert not hasattr(custody,"create_grant")
    assert not hasattr(custody,"start_worker")
    assert not hasattr(custody,"send_outbox")
