"""Cognitum-side installed-host prerequisites for Lu Core Health.

This is NOT an issuer, installer, publisher verifier, host enrollment server or
Lu capability registration. The installed owner must independently attest its
package, service, endpoint, signer and original OS enrollment. An OS-backed
HMAC key can authenticate a protocol session without proving those properties.
No synthetic Health exchange is a real installed Core exchange.
"""
from __future__ import annotations

import sys

from . import admission as mel
from . import lu_ipc_native as native
from .lu_ipc_readonly import LuClientRefused, _key, _package_digest
from .ssm_os_credentials import OSCredentialBroker
from cognitum.research.ssm_stochastic_checkpoints import _identifier


def _need(value, detail):
    if not value:
        raise LuClientRefused("Cognitum installed Health custody refused: " + detail)


def probe_enrolled_core_health(*, broker, trusted_scope, credential_ref,
                               endpoint, package_hash, expected_uid=None,
                               windows_process_pin=None):
    """Borrow an already-enrolled *native OS* key for one OS-local Health probe.

    This cannot provision a key, bootstrap a trust pin, issue a per-turn grant,
    infer a signed publisher from a process hash, or release/ACK an outbox.
    A host-selected scope and package hash remain data, not installer evidence.
    """
    _need(type(broker) is OSCredentialBroker,
          "native OS-backed broker required; no Python fixture provider")
    _need(type(trusted_scope) is mel.Scope,
          "original host-selected MEL scope required")
    _identifier(credential_ref, "installed Core Health credential reference")
    _package_digest(package_hash)
    _need(type(endpoint) is str and endpoint and "\x00" not in endpoint,
          "host-pinned endpoint required")

    # An invalid OS identity pin must be rejected BEFORE unlocking a secret.
    if sys.platform == "win32":
        from .lu_ipc_native import HEX64, SID_RE, PIPE_PREFIX, PIPE_RE
        _need(endpoint.startswith(PIPE_PREFIX) and
              PIPE_RE.fullmatch(endpoint[len(PIPE_PREFIX):]) is not None,
              "trusted native Windows pipe required")
        p = windows_process_pin
        _need(type(p) is dict and
              set(p) == {"pid", "creation_filetime", "user_sid", "image_sha256"} and
              type(p["pid"]) is int and p["pid"] > 0 and
              type(p["creation_filetime"]) is int and p["creation_filetime"] > 0 and
              type(p["user_sid"]) is str and SID_RE.fullmatch(p["user_sid"]) and
              type(p["image_sha256"]) is str and HEX64.fullmatch(p["image_sha256"]),
              "independently host-selected Windows process pin required")
        _need(expected_uid is None, "unexpected Linux peer identity")
    elif sys.platform.startswith("linux"):
        _need(endpoint.startswith("/") and
              len(endpoint.encode("utf-8")) <= 106,
              "trusted absolute Linux UDS endpoint required")
        _need(type(expected_uid) is int and expected_uid >= 0 and
              windows_process_pin is None,
              "independently host-selected Linux service UID required")
    else:
        raise LuClientRefused("Cognitum installed Health custody refused: unsupported OS")

    # No environment variable, IPC message, local JSON or model instruction
    # can provision or rotate this key. The OS broker must already have it.
    key = _key(broker.borrow_key(trusted_scope, credential_ref))
    response = native.installed_core_health_preflight(
        endpoint=endpoint,
        enrolled_key=key,
        package_hash=package_hash,
        expected_uid=expected_uid,
        windows_process_pin=windows_process_pin,
    )
    _need(type(response) is dict and
          response.get("installed_acceptance") ==
              "BLOCKED_CORE_ISSUER_AND_ENROLLMENT",
          "unauthorized installed Health authority escalation")
    _need(response.get("output_delivery_authorized") is False and
          response.get("output_acknowledgment_authorized") is False and
          response.get("model_tool_execution_authorized") is False,
          "Health cannot grant effect or release permissions")
    return response


def linux_existing_worker_cgroup_readiness(delegated_root="/sys/fs/cgroup"):
    """Reuse original Linux kernel cgroup-v2 preflight. Never create a scope."""
    _need(sys.platform.startswith("linux"), "Linux cgroup-v2 only")
    from cognitum.cgroup2_contract import preflight
    status = preflight(delegated_root)
    return {
        "kernel_cgroup2": status.kernel_cgroup2,
        "delegated_fixture_scope_available": status.admitted_for_fixture,
        "reason": status.reason,
        "installed_ssm_worker_protected": False,
        "actual_installed_core_health_verified": False,
        "output_delivery_authorized": False,
    }
