"""COG-LU-IPC-01E-R2: inspect a proposed *external* signed Core receipt.

This is Cognitum-owned decoding and Ed25519 verification of an externally
supplied attestation, NOT an amendment to Lu Core workspace v0 Protobuf.
The signed envelope format is a PROPOSAL requiring Lu Core #248 agreement.
The current installed Lu Core does not issue this exact envelope.

No signer private key, issuer authority or trust anchor is minted here.
A public key provided by an arbitrary caller is NOT trusted enrollment.
Even a cryptographically valid signature, native DPAPI/keyring credential
and a locally matched R6 outbox do not establish installed Core publisher
custody, independent OS peer identity, a still-current Lu per-turn effect
grant, or permission to deliver/ack anything. All outputs stay withheld.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Final

from . import lu_ipc_lifecycle as life
from . import lu_ssm_contract as ssm
from .vendor.lu.workspace.v0 import workspace_pb2 as lu

ENVELOPE_SCHEMA: Final = "cognitum.lu_ipc01e_r2.proposed_core_receipt.v1"
DOMAIN: Final = b"Cognitum.Lu.IPC01E.R2.PROPOSED_CORE_RECEIPT.v1\x00"
MAX_WIRE = 4096
MAX_VALIDITY_MS = 60_000
HEX64=re.compile(r"[a-f0-9]{64}\Z",re.ASCII)
NAME=re.compile(r"[A-Za-z0-9_.:/-]{1,128}\Z",re.ASCII)
REQUIRED=frozenset({
    "schema","origin","core_session_ref","core_epoch_ref",
    "operation_ref","capability_id","effect","receipt_sha256",
    "issuer_package_sha256","grant_digest_sha256","outbox_sha256",
    "nonce_sha256","not_before_unix_ms","expires_unix_ms",
})


def _need(condition, what):
    if not condition:
        raise ValueError("Cognitum Lu receipt attestation refused: "+what)


def _hex(value):
    return type(value) is str and HEX64.fullmatch(value) is not None


def _canonical(data):
    return json.dumps(data,sort_keys=True,separators=(",",":"),
                      allow_nan=False,ensure_ascii=True).encode("ascii")


@dataclass(frozen=True, slots=True)
class ExternallyPinnedCoreIssuer:
    """Read-only pin DATA, not verified installer provenance or signer custody.

    Actual root authority/publisher pin MUST be chosen independently by a
    privileged OS credential/enrollment service, not parsed from signed input
    or inferred from a Lu session string.
    """
    public_key_ed25519: bytes
    trusted_package_sha256: bytes
    permitted_core_session_ref: str
    permitted_core_epoch_ref: str

    def __post_init__(self):
        _need(type(self.public_key_ed25519) is bytes and
              len(self.public_key_ed25519)==32 and
              any(self.public_key_ed25519),
              "separately enrolled 32-byte public key required")
        _need(type(self.trusted_package_sha256) is bytes and
              len(self.trusted_package_sha256)==32 and
              any(self.trusted_package_sha256),
              "independently pinned package digest required")
        _need(type(self.permitted_core_session_ref) is str and
              NAME.fullmatch(self.permitted_core_session_ref) is not None and
              type(self.permitted_core_epoch_ref) is str and
              NAME.fullmatch(self.permitted_core_epoch_ref) is not None,
              "bounded separately pinned original Core session/epoch")


def _verified_local_original(verifier):
    """Read original 01D HMAC/anchor trace under its own original RLock.

    Never trust a caller-supplied terminal digest or unsigned process flag.
    This is a source-local observation; NOT actual Core signed provenance.
    """
    _need(type(verifier) is life.DurableLuOperationVerifier,
          "accepted local Lu original observer only")
    with verifier._lock:
        _need(not verifier._closed,"original observer closed")
        key=life._key(verifier._broker,verifier._scope,verifier._op)
        verifier._db.execute("BEGIN IMMEDIATE")
        try:
            items,head=verifier._verified_items(key)
            _need(life._trust_read(verifier._anchor,verifier._scope,
                  verifier._op)==(len(items),head),
                  "independently supplied current source revision")
            state=verifier._derive(items)
            _need(state["terminal"]==lu.TERMINAL_STATE_APPLIED and
                  state["reconcile_status"]=="matched" and
                  state["receipt_raw"] is not None and
                  state["outbox_sha"] is not None and
                  not state["cancel_requested"] and
                  not state["cancel_ack"] and
                  not state["revoked"] and
                  not state["uncertain_hold"],
                  "original applied/reconciled outbox absent, revoked or held")
            result=(hashlib.sha256(state["receipt_raw"]).hexdigest(),
                    state["outbox_sha"],verifier._origin,
                    verifier._session,verifier._epoch,verifier._op,
                    verifier._prepared.typed_request_sha256)
            verifier._db.commit()
            return result
        except BaseException:
            verifier._db.rollback()
            raise


def inspect_proposed_signed_core_receipt(
        verifier, *, pinned_issuer, signed_claim, signature_ed25519,
        verified_host_grant_digest_sha256, now_unix_ms):
    """Verify signature over a proposed Core issuer payload, fail CLOSED.

    Grant digest supplied by the trusted host is a *binding input only*.
    The real Lu owner must independently prove that the original user turn
    currently authorizes PURE_COMPUTE and the exact scope. We cannot do that
    until #248 supplies an accepted format and genuinely signed enrollment.
    Returns only withheld/simulation-safe evidence. Never a delivery token.
    """
    _need(type(pinned_issuer) is ExternallyPinnedCoreIssuer,
          "externally pinned Core issuer input required")
    _need(type(signed_claim) is bytes and
          0<len(signed_claim)<=MAX_WIRE,
          "bounded exact signed payload")
    _need(type(signature_ed25519) is bytes and
          len(signature_ed25519)==64,
          "64-byte detached Ed25519 signature")
    _need(_hex(verified_host_grant_digest_sha256) and
          verified_host_grant_digest_sha256!="0"*64,
          "externally checked original turn-grant digest")
    _need(type(now_unix_ms) is int and now_unix_ms>0,
          "externally trusted positive clock")
    try:
        value=json.loads(signed_claim.decode("ascii"))
    except (UnicodeError,ValueError) as exc:
        raise ValueError("Cognitum Lu receipt attestation refused: invalid JSON") from exc
    _need(type(value) is dict and set(value)==REQUIRED and
          _canonical(value)==signed_claim,
          "canonical signed payload and exact domain schema")
    _need(value["schema"]==ENVELOPE_SCHEMA and
          value["capability_id"]==ssm.OPERATION and
          value["effect"]=="PURE_COMPUTE" and
          type(value["origin"]) is list and len(value["origin"])==5 and
          all(type(s) is str and NAME.fullmatch(s) is not None
              for s in value["origin"]),
          "approved original capability/effect/origin identity")
    _need(all(_hex(value[k]) for k in (
          "receipt_sha256","issuer_package_sha256",
          "grant_digest_sha256","outbox_sha256","nonce_sha256")) and
          value["nonce_sha256"]!="0"*64,
          "bounded signed hashes and unique nonce digest")
    _need(type(value["not_before_unix_ms"]) is int and
          type(value["expires_unix_ms"]) is int and
          value["not_before_unix_ms"]<=now_unix_ms<=value["expires_unix_ms"] and
          0<value["expires_unix_ms"]-value["not_before_unix_ms"]<=MAX_VALIDITY_MS,
          "short-lived original issuer evidence")
    _need(hmac.compare_digest(
            value["issuer_package_sha256"],
            pinned_issuer.trusted_package_sha256.hex()) and
          hmac.compare_digest(
            value["grant_digest_sha256"],verified_host_grant_digest_sha256),
          "unapproved package or original-turn grant digest")
    receipt_hash,inventory_sha,origin,session,epoch,operation,request_hash=(
        _verified_local_original(verifier))
    _need(value["origin"]==list(origin) and
          value["core_session_ref"]==session==
              pinned_issuer.permitted_core_session_ref and
          value["core_epoch_ref"]==epoch==
              pinned_issuer.permitted_core_epoch_ref and
          value["operation_ref"]==operation and
          hmac.compare_digest(value["receipt_sha256"],receipt_hash) and
          hmac.compare_digest(value["outbox_sha256"],inventory_sha),
          "session/epoch/original receipt or R6 inventory mismatch")
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(
            pinned_issuer.public_key_ed25519).verify(
            signature_ed25519,DOMAIN+signed_claim)
    except (ImportError,ValueError,InvalidSignature) as exc:
        raise ValueError("Cognitum Lu receipt attestation refused: Ed25519 signature/key unavailable or invalid") from exc

    # A valid signed *proposal* is not an existing Lu Core grant or a native
    # installed signer. The receipt is still unpublishable until the Core
    # contract, OS credential enrollment and independently authoritative
    # monotonic replay/consumption receipts have all been qualified.
    return dict(
        schema="cognitum.lu_ipc01e_r2.verified_provisional_receipt.v1",
        source_operation_ref=operation,
        original_typed_request_sha256=request_hash,
        local_original_receipt_sha256=receipt_hash,
        local_outbox_inventory_sha256=inventory_sha,
        signer_mathematically_verified_against_supplied_pin=True,
        original_issuer_pin_installed_trust_verified=False,
        signed_Lu_Core_production_provenance_verified=False,
        genuine_Core_per_turn_grant_authorized=False,
        independent_replay_protected_consumption=False,
        installed_OS_worker_custody_verified=False,
        output_delivery_authorized=False,
        output_acknowledgment_authorized=False,
        result_publication_authorized=False,
    )
