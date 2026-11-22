"""Closed, read-only R3-R1 private GPG protected-successor admission contract.

This validates metadata and externally supplied SHA-256 pins; the caller must
verify a detached OWNER-GPG signature over the exact original bytes before
calling validate(). The caller must separately verify *installed* OS custody.
Even a valid signed contract is NOT a Lu Core grant, an independent signer
approval, a live antirollback authority, an installed service or output release.

No key creation, files written, service registration, network or subprocess.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

CURRENT_NO_WORKER_SOURCE = "8c45869214255fc91af53e88e0bfaff6b943696c"
CURRENT_NO_WORKER_SERVICE = "CognitumSsmSupervisorV1"
CI_QUALIFIER_SERVICE = "CognitumSsmProductionQualifierV1"
REQUIRED_SUCCESSOR_SERVICE = "CognitumSsmProtectedV1"
SCHEMA = "cognitum.ssm.r3r1.private_protected_successor_candidate.v1"
PIN_FIELDS = frozenset({
    "protected_service_image_sha256", "protected_nsis_installer_sha256",
    "frozen_runtime_manifest_sha256", "frozen_runtime_provenance_sha256",
    "frozen_python_image_sha256", "protected_ssm_child_sha256",
    "preprovisioned_machine_cng_public_blob_sha256",
    "external_antirollback_authority_public_sha256",
    "original_lu_core_issuer_public_sha256",
})
REFUSAL_FIELDS = frozenset({
    "physical_installed_worker_accepted",
    "original_lu_core_issuer_enrolled",
    "original_lu_core_operation_grant_verified",
    "external_antirollback_freshness_verified",
    "external_persistent_signer_approved",
    "production_CNG_terminal_receipts_verified",
    "output_or_ACK_authorized",
})
FIELDS = frozenset({
    "schema", "role", "source_sha", "approved_gpg_primary_fingerprint",
    "protected_service_name", "replaced_bootstrap_service_name",
    "preprovisioned_machine_cng_key_name", "protected_runtime_file_count",
}) | PIN_FIELDS | REFUSAL_FIELDS


class RefusedSuccessor(ValueError):
    pass


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise RefusedSuccessor("R3R1_PROTECTED_SUCCESSOR_REFUSED: " + reason)


def is_sha(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None and value != "0" * 64


def is_commit(value: Any) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _no_dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_exact(raw: bytes) -> dict[str, Any]:
    need(type(raw) is bytes and 300 <= len(raw) <= 8192,
         "bounded signed successor manifest required")
    need(raw.endswith(b"\n") and not raw.endswith(b"\r\n"),
         "canonical LF termination required")
    need(all(b in (10,) or 32 <= b <= 126 for b in raw),
         "ASCII-only canonical manifest required")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_no_dupes,
                           parse_constant=lambda _: need(False, "NaN/Infinity refused"))
    except (UnicodeError, ValueError, TypeError) as e:
        raise RefusedSuccessor("R3R1_PROTECTED_SUCCESSOR_REFUSED: invalid exact JSON") from e
    need(type(value) is dict and set(value) == FIELDS,
         "closed successor manifest fields required")
    canonical = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    need(raw == canonical, "manifest must be exact canonical signed bytes")
    return value


def validate(
    raw: bytes, *, externally_approved_manifest_sha256: str,
    externally_approved_source_sha: str,
    externally_approved_gpg_primary_fingerprint: str,
) -> dict[str, Any]:
    """Read-only semantic observation AFTER independent GPG signature verification.

    No authority is created: pins and independent public fingerprints must
    come from outside the manifest and not from a caller-controlled CI env.
    """
    need(is_sha(externally_approved_manifest_sha256),
         "external canonical manifest digest missing")
    need(is_commit(externally_approved_source_sha),
         "externally selected full source SHA missing")
    need(type(externally_approved_gpg_primary_fingerprint) is str and
         re.fullmatch(r"(?:[0-9A-F]{40}|[0-9A-F]{64})",
                      externally_approved_gpg_primary_fingerprint) is not None,
         "external full owner-GPG primary fingerprint missing")
    need(hashlib.sha256(raw).hexdigest() == externally_approved_manifest_sha256,
         "signed manifest differs from independently approved digest")
    claim = parse_exact(raw)
    need(claim["schema"] == SCHEMA and
         claim["role"] == "protected_ssm_production_successor_candidate",
         "signed candidate role/schema missing")
    need(claim["source_sha"] == externally_approved_source_sha and
         claim["source_sha"] != CURRENT_NO_WORKER_SOURCE,
         "old no-worker source cannot masquerade as protected worker")
    need(claim["approved_gpg_primary_fingerprint"] ==
         externally_approved_gpg_primary_fingerprint,
         "GPG primary identity not bound to external pin")
    need(claim["protected_service_name"] == REQUIRED_SUCCESSOR_SERVICE and
         claim["protected_service_name"] not in
         (CURRENT_NO_WORKER_SERVICE, CI_QUALIFIER_SERVICE),
         "existing no-worker or CI service cannot become protected successor")
    need(claim["replaced_bootstrap_service_name"] == CURRENT_NO_WORKER_SERVICE,
         "original accepted no-worker SCM identity must remain explicit")
    key_name = claim["preprovisioned_machine_cng_key_name"]
    need(type(key_name) is str and
         re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{11,95}", key_name) is not None,
         "existing machine signer key name must be fixed and bounded")
    need(type(claim["protected_runtime_file_count"]) is int and
         1 <= claim["protected_runtime_file_count"] <= 12000,
         "complete bounded original runtime file count required")
    for key in PIN_FIELDS:
        need(is_sha(claim[key]), "nonzero independently observed digest missing: " + key)
    # This is admission CANDIDATE metadata. Setting any of these booleans
    # to True claims authority not established by owner GPG or local CNG.
    for key in REFUSAL_FIELDS:
        need(claim[key] is False, "premature independent authority claim: " + key)
    return {
        "schema": "cognitum.ssm.r3r1.protected_successor_metadata_observation.v1",
        "status": "PASS_CLOSED_PROTECTED_SUCCESSOR_METADATA_PINS_OBSERVATION_ONLY",
        "source_sha": claim["source_sha"],
        "protected_service_name": claim["protected_service_name"],
        "owner_gpg_manifest_digest": externally_approved_manifest_sha256,
        "manifest_bytes_closed": True,
        "owner_gpg_signature_verified_by_this_function": False,
        "independent_publisher_or_signer_approved": False,
        "installed_worker_verified": False,
        "external_antirollback_accepted": False,
        "real_Lu_Core_grant_verified": False,
        "output_or_ACK_authorized": False,
    }


def canonical_candidate(value: Mapping[str, Any]) -> bytes:
    """Serialization helper for TEST VECTORS only. Never signs or approves."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
