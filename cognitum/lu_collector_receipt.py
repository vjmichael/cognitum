"""C04 OFFLINE receipt format verification for a future Lu-owned collector.

A caller-supplied, pinned Ed25519 key, challenge, expected build hashes,
runner identity, and expected plan digest constrain receipt substitution.
A valid signature proves possession of that key, NOT that Lu ran a model,
the measurements are true, a trial was scored independently, the nonce was
consumed, or the OS security gate passed. This module NEVER authorizes launch.

The receipt is *separate* binary Protobuf; its signed hashes bind the exact
validated BenchmarkPlan and BenchmarkCapture bytes. No JSON/MCP transport.
"""
from dataclasses import dataclass
from hashlib import sha256
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from google.protobuf.message import DecodeError

from .benchmark_capture import decode_plan, decode_capture
from .proto import collector_pb2 as pb

DOMAIN = b"cognitum.c04.lu-benchmark-collector.v1\x00"
COLLECTOR_RECEIPT_TYPE_URL = "type.googleapis.com/cognitum.benchmark.v1.CollectorReceipt"
SIGNED_COLLECTOR_RECEIPT_TYPE_URL = "type.googleapis.com/cognitum.benchmark.v1.SignedCollectorReceipt"
MAX_SIGNED_BYTES = 8 * 1024
MAX_RECEIPT_BYTES = 4 * 1024
MAX_AGE_MS = 5 * 60 * 1000
MAX_FUTURE_SKEW_MS = 5000
_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)


def _valid_hash(s, desc):
    if type(s) is not str or not _HASH.fullmatch(s) or s == "0" * 64:
        raise ValueError(f"invalid {desc}")


def _valid_id(s, desc):
    if type(s) is not str or not _ID.fullmatch(s):
        raise ValueError(f"invalid {desc}")


def _strict_parse(blob, cls, max_bytes):
    if type(blob) is not bytes or not 0 < len(blob) <= max_bytes:
        raise ValueError("invalid bounded Protobuf collector frame")
    msg = cls()
    try:
        msg.ParseFromString(blob)
    except DecodeError as error:
        raise ValueError("malformed collector protobuf") from error
    known = cls()
    known.CopyFrom(msg)
    known.DiscardUnknownFields()
    if known != msg or msg.SerializeToString(deterministic=True) != blob:
        raise ValueError("unknown, shadowed or noncanonical collector fields")
    return msg


@dataclass(frozen=True)
class CollectorReceiptReview:
    """Signature/structure findings; never a production promotion grant."""
    signature_matches_pinned_key: bool
    plan_and_capture_bound: bool
    reported_trials: int
    planned_trials: int
    reported_data_present: bool
    collector_runtime_authenticated: bool = False
    metric_provenance_verified: bool = False
    paired_effect_verified: bool = False
    production_promotion_evidence: bool = False


def verify_host_collector_receipt(
    plan_frame: bytes, capture_frame: bytes, signed_frame: bytes, *,
    trusted_public_key: bytes,
    expected_signing_key_id: str,
    expected_collector_id: str,
    expected_collector_build_sha256: str,
    expected_lu_build_sha256: str,
    expected_model_artifact_sha256: str,
    expected_plan_sha256: str,
    expected_challenge_nonce: str,
    now_unix_ms: int,
) -> CollectorReceiptReview:
    """Validate a signed *claim* against separately pinned Lu host metadata.

    Trust pinning, independent grader/source assurance, one-use challenge
    issuance/consumption and durable audit all remain Lu-owned; callers MUST
    NOT let workers/models provide trusted_* or expected_* values.
    """
    if type(trusted_public_key) is not bytes or len(trusted_public_key) != 32:
        raise ValueError("expected independently pinned 32-byte Ed25519 key")
    for desc, val in (
        ("signer", expected_signing_key_id),
        ("collector", expected_collector_id),
    ):
        _valid_id(val, desc)
    for desc, val in (
        ("collector build", expected_collector_build_sha256),
        ("Lu build", expected_lu_build_sha256),
        ("model artifact", expected_model_artifact_sha256),
        ("plan digest", expected_plan_sha256),
        ("host challenge", expected_challenge_nonce),
    ):
        _valid_hash(val, desc)
    if type(now_unix_ms) is not int or not 1 <= now_unix_ms < (1 << 63):
        raise ValueError("trusted host clock required")

    plan = decode_plan(plan_frame)
    capture, shape = decode_capture(plan, capture_frame)
    plan_digest = sha256(plan_frame).hexdigest()
    capture_digest = sha256(capture_frame).hexdigest()
    if (plan_digest != expected_plan_sha256
            or plan.lu_build_sha256 != expected_lu_build_sha256
            or plan.model_artifact_sha256 != expected_model_artifact_sha256
            or capture.host_collector_id != expected_collector_id
            or capture.host_collector_build_sha256 != expected_collector_build_sha256):
        raise ValueError("host plan/collector not pinned by trusted caller")

    envelope = _strict_parse(signed_frame, pb.SignedCollectorReceipt, MAX_SIGNED_BYTES)
    if (envelope.signing_key_id != expected_signing_key_id
            or len(envelope.signature_ed25519) != 64):
        raise ValueError("unexpected signer or invalid signature size")
    receipt = _strict_parse(
        envelope.serialized_receipt, pb.CollectorReceipt, MAX_RECEIPT_BYTES)
    try:
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(
            envelope.signature_ed25519, DOMAIN + envelope.serialized_receipt)
    except (ValueError, InvalidSignature) as exc:
        raise ValueError("host collector receipt signature invalid") from exc

    if (receipt.schema_version != 1 or receipt.contains_raw_user_data
            or receipt.execution_security_verified
            or receipt.declared_source != pb.LU_HOST_DECLARED):
        raise ValueError("unsupported receipt, claimed security, or raw content")
    if (receipt.plan_sha256 != plan_digest
            or receipt.capture_sha256 != capture_digest
            or receipt.challenge_nonce != expected_challenge_nonce
            or receipt.lu_build_sha256 != expected_lu_build_sha256
            or receipt.model_artifact_sha256 != expected_model_artifact_sha256
            or receipt.collector_build_sha256 != expected_collector_build_sha256
            or receipt.collector_id != expected_collector_id
            or receipt.run_id != capture.capture_id
            or receipt.reported_observed_trials != shape.observed_trials):
        raise ValueError("collector statement inconsistent with captured bytes")
    if (receipt.collected_at_unix_ms > now_unix_ms + MAX_FUTURE_SKEW_MS
            or receipt.collected_at_unix_ms + MAX_AGE_MS < now_unix_ms):
        raise ValueError("expired or future dated collector receipt")
    return CollectorReceiptReview(
        signature_matches_pinned_key=True,
        plan_and_capture_bound=True,
        reported_trials=shape.observed_trials,
        planned_trials=shape.planned_trials,
        reported_data_present=shape.observed_trials > 0,
        # Never attest identity, permission, OS counters, grading or efficacy
        # simply because a matching framed signature was observed.
    )
