"""C02 OFFLINE host-receipt verifier. Not an OS sandbox or launch authority.

Verifies canonical signed binary Protobuf (Ed25519) under a caller-pinned
independent runner public key, one-use caller-issued nonce, expected builds,
OS and test plan. It checks coverage, timestamps, and reported observations.

A signature proves only possession of its signing key, not correct OS probes:
the LU TRUSTED HOST must independently provision and protect that key,
collect actual OS measurements, and consume challenges once. No result from
this function ever enables worker execution or authorizes a CE.
"""
from dataclasses import dataclass
import hashlib
import re

from google.protobuf.message import DecodeError
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .proto import supervisor_acceptance_pb2 as pb
from .supervisor_acceptance import acceptance_plan, encode_acceptance_plan

DOMAIN = b"cognitum.c02.supervisor-evidence.v1\x00"
MAX_SIGNED_BYTES = 32768
MAX_RECEIPT_BYTES = 16384
MAX_REPORT_AGE_MS = 5 * 60 * 1000
MAX_FUTURE_CLOCK_SKEW_MS = 5000
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _require_hex(value, label):
    if type(value) is not str or not _HEX.fullmatch(value) or value == "0" * 64:
        raise ValueError(f"invalid {label}")


def _require_id(value, label):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(f"invalid {label}")


def _parse(blob, cls, limit):
    if type(blob) is not bytes or not 0 < len(blob) <= limit:
        raise ValueError("invalid or oversized host evidence")
    message = cls()
    try:
        message.ParseFromString(blob)
    except DecodeError as error:
        raise ValueError("malformed host evidence Protobuf") from error
    known = cls()
    known.CopyFrom(message)
    known.DiscardUnknownFields()
    if known != message or message.SerializeToString(deterministic=True) != blob:
        raise ValueError("unknown fields, duplicate tags or noncanonical evidence")
    return message


@dataclass(frozen=True)
class OfflineConformanceReview:
    """Receipt structure accepted; OS enforcement and launch stay UNVERIFIED."""
    signed_receipt_valid: bool
    reported_probes_complete: bool
    platform: str
    os_isolation_verified: bool = False
    production_launch_allowed: bool = False


def verify_signed_receipt(
    framed_receipt: bytes, *,
    trusted_public_key: bytes,
    expected_signer_key_id: str,
    expected_runner_id: str,
    expected_challenge_nonce: str,
    expected_platform: int,
    expected_host_build_sha256: str,
    expected_worker_build_sha256: str,
    now_unix_ms: int,
) -> OfflineConformanceReview:
    """Verify signed runner CLAIMS from a pretrusted key and host challenge.

    No keys can be supplied by a model, worker, or receipt. The caller MUST
    obtain public key/builds/runner identity/nonce/clock from a separate trusted
    Lu supervisor, and mark nonce consumed on every attempt. No production
    admission API exists here. Python unit tests use ephemeral TEST keys only.
    """
    if type(trusted_public_key) is not bytes or len(trusted_public_key) != 32:
        raise ValueError("trusted Ed25519 key must be caller-pinned raw 32-byte key")
    _require_id(expected_signer_key_id, "trusted signer key id")
    _require_id(expected_runner_id, "trusted independent runner id")
    for label, value in (
        ("host nonce", expected_challenge_nonce),
        ("host build", expected_host_build_sha256),
        ("worker build", expected_worker_build_sha256),
    ):
        _require_hex(value, label)
    if type(expected_platform) is not int or expected_platform not in (
        pb.PLATFORM_WINDOWS, pb.PLATFORM_LINUX, pb.PLATFORM_MACOS,
    ):
        raise ValueError("unsupported host OS target")
    if type(now_unix_ms) is not int or not 1 <= now_unix_ms < (1 << 63):
        raise ValueError("trusted wall clock timestamp required")

    frame = _parse(framed_receipt, pb.SignedSupervisorReceipt, MAX_SIGNED_BYTES)
    if (frame.signer_key_id != expected_signer_key_id
            or len(frame.signature_ed25519) != 64):
        raise ValueError("unknown signing identity or signature size")
    receipt = _parse(
        frame.serialized_receipt, pb.SupervisorConformanceReceipt, MAX_RECEIPT_BYTES,
    )
    try:
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(
            frame.signature_ed25519, DOMAIN + frame.serialized_receipt)
    except (InvalidSignature, ValueError) as error:
        raise ValueError("invalid host-runner signature") from error

    if receipt.schema_version != 1 or receipt.simulation_only:
        raise ValueError("unsupported or explicitly synthetic host receipt")
    if receipt.acceptance_plan_sha256 != _sha(encode_acceptance_plan()):
        raise ValueError("acceptance plan hash mismatch")
    if (receipt.challenge_nonce != expected_challenge_nonce
            or receipt.host_build_sha256 != expected_host_build_sha256
            or receipt.worker_build_sha256 != expected_worker_build_sha256
            or receipt.platform != expected_platform
            or receipt.independent_runner_id != expected_runner_id):
        raise ValueError("receipt does not match independently pinned host session")
    if (receipt.observed_at_unix_ms > now_unix_ms + MAX_FUTURE_CLOCK_SKEW_MS
            or receipt.observed_at_unix_ms + MAX_REPORT_AGE_MS < now_unix_ms):
        raise ValueError("expired or future-dated host receipt")

    required = [
        p for p in acceptance_plan().probes
        if p.platform in (pb.PLATFORM_ALL, expected_platform)
    ]
    if len(receipt.measurements) != len(required):
        raise ValueError("required OS negative probes missing or extra")
    for spec, measurement in zip(required, receipt.measurements):
        if (measurement.probe_id != spec.id
                or measurement.observed != spec.expected
                or not measurement.attempted):
            raise ValueError("host runner claimed incomplete or failing probe")
        _require_hex(measurement.evidence_sha256, "OS evidence digest")

    return OfflineConformanceReview(
        signed_receipt_valid=True,
        reported_probes_complete=True,
        platform=pb.Platform.Name(expected_platform),
        # Even matching signed observations are unverified claims from a
        # future host-runner until its OS harness and key custody are audited.
        os_isolation_verified=False,
        production_launch_allowed=False,
    )
