"""R5 proposed independently signed *stop evidence* verifier.

This module has NO signing/private-key, issuer-enrollment, service starter,
Lu grant, output ACK or delivery API. A positive Ed25519 verification checks
only that an externally pinned signer produced a bounded claim matching the
local original operation and OS-stop observation. Until SCM/systemd/cgroup
service custody and independent signer storage are accepted and measured,
no production host or Lu authorization may be inferred from that signature.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .ssm_r4_protected import (
    DurableOriginalWorkerClaim, NativeSSMCustodyRefused, _read_record,
)

DOMAIN = b"Cognitum.SSM.R5.EXTERNAL_STOP_CLAIM.PROPOSED.v1\x00"
SCHEMA = "cognitum.ssm_r5.externally_signed_stop.proposed.v1"
MAX_SIGNED_WIRE = 4096
MAX_VALIDITY_MS = 60000
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
SHA256 = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
REQUIRED = frozenset((
    "schema", "issuer_id", "issuer_epoch", "service_package_sha256",
    "worker_source_sha256", "original", "identity", "request_sha256",
    "nonce", "mechanism", "worker_pid", "native_job_owned_before_release",
    "kernel_worker_exited", "kernel_scope_empty", "observed_unix_ms",
    "expires_unix_ms", "installed_authority",
))


def _need(ok, reason):
    if not ok:
        raise NativeSSMCustodyRefused("Cognitum R5 stop attestation refused: " + reason)


def _valid_sha(value):
    return type(value) is str and SHA256.fullmatch(value) is not None and value != "0" * 64


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True, slots=True)
class ExternallyPinnedStopSigner:
    """Only previously authenticated independent host DATA, not trust creation."""
    public_key_ed25519: bytes
    issuer_id: str
    issuer_epoch: str
    service_package_sha256: str
    worker_source_sha256: str

    def __post_init__(self):
        _need(type(self.public_key_ed25519) is bytes and
              len(self.public_key_ed25519) == 32 and any(self.public_key_ed25519),
              "pre-enrolled external signer public key required")
        _need(type(self.issuer_id) is str and ID.fullmatch(self.issuer_id) and
              type(self.issuer_epoch) is str and ID.fullmatch(self.issuer_epoch),
              "independently enrolled issuer/epoch required")
        _need(_valid_sha(self.service_package_sha256) and
              _valid_sha(self.worker_source_sha256),
              "host package and worker source pins required")


def verify_proposed_independent_stop(*, claim, signed_bytes, signature,
                                     trusted_signer, trusted_now_ms):
    """Verify external proof matched to *locally HMAC-verified* R4 stop record.

    No signer private key exists here. Verification does not independently
    discover publisher identity, service launch, OS Job/SCM ownership, kernel
    facts or a TPM-backed revision. An installed host must supply evidence
    of those separately and maintain a replay-resistant nonce/issuer epoch.
    """
    _need(type(claim) is DurableOriginalWorkerClaim,
          "original durable claim object required")
    _need(type(trusted_signer) is ExternallyPinnedStopSigner,
          "external enrolled signer required")
    _need(type(signed_bytes) is bytes and 0 < len(signed_bytes) <= MAX_SIGNED_WIRE,
          "bounded external signed bytes")
    _need(type(signature) is bytes and len(signature) == 64,
          "Ed25519 signature byte length")
    _need(type(trusted_now_ms) is int and trusted_now_ms > 0,
          "trusted verifier wall clock")
    # Exact local chain is always checked under OS-backed HMAC custody.
    _need(claim.restart_assessment() ==
          "STOP_LOCALLY_OBSERVED_REPLAY_STILL_DENIED",
          "original kernel stop not locally observed")
    prior = claim._verify(_read_record(claim._pending))
    stop = claim._verify(_read_record(claim._stopped))
    def no_duplicate(pairs):
        obj = {}
        for key, val in pairs:
            _need(key not in obj, "duplicate receipt key")
            obj[key] = val
        return obj
    try:
        body = json.loads(signed_bytes, object_pairs_hook=no_duplicate,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ValueError("nonfinite receipt")))
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise NativeSSMCustodyRefused(
            "Cognitum R5 stop attestation refused: malformed signed receipt") from exc
    _need(type(body) is dict and set(body) == REQUIRED and
          _canonical(body) == signed_bytes and body["schema"] == SCHEMA,
          "closed canonical versioned signed receipt")
    _need(body["installed_authority"] is False,
          "unsigned promotion of installation trust")
    _need(body["issuer_id"] == trusted_signer.issuer_id and
          body["issuer_epoch"] == trusted_signer.issuer_epoch and
          body["service_package_sha256"] == trusted_signer.service_package_sha256 and
          body["worker_source_sha256"] == trusted_signer.worker_source_sha256,
          "external issuer/package/source trust binding")
    _need(body["original"] == claim._tuple and
          body["identity"] == claim._identity and
          body["request_sha256"] == prior["request_sha256"] and
          body["nonce"] == prior["nonce"] and
          body["mechanism"] == stop["mechanism"] and
          body["worker_pid"] == stop["worker_pid"],
          "exact original operation, nonce, kernel worker binding")
    _need(body["native_job_owned_before_release"] is True and
          body["kernel_worker_exited"] is True and
          body["kernel_scope_empty"] is True and
          type(body["worker_pid"]) is int and body["worker_pid"] > 0,
          "independent native kernel observation claim")
    _need(type(body["observed_unix_ms"]) is int and
          type(body["expires_unix_ms"]) is int and
          0 < body["observed_unix_ms"] <= trusted_now_ms + 5000 and
          body["observed_unix_ms"] <= trusted_now_ms <= body["expires_unix_ms"] and
          0 <= body["expires_unix_ms"]-body["observed_unix_ms"] <= MAX_VALIDITY_MS,
          "external terminal receipt freshness")
    try:
        Ed25519PublicKey.from_public_bytes(
            trusted_signer.public_key_ed25519).verify(signature,
                  DOMAIN + signed_bytes)
    except (InvalidSignature, ValueError) as exc:
        raise NativeSSMCustodyRefused(
            "Cognitum R5 stop attestation refused: signature invalid") from exc
    return dict(
        schema=SCHEMA,
        external_signature_checked=True,
        locally_bound_original_operation=True,
        externally_claimed_job_exit_and_empty=True,
        independently_installed_service_verified=False,
        independent_signer_key_custody_verified=False,
        hardware_remote_monotonic_revision_verified=False,
        lu_core_installed_peer_authenticated=False,
        lu_core_per_turn_authorization_verified=False,
        installed_ssm_execution_authorized=False,
        durable_output_delivery_or_ack_authorized=False,
    )
