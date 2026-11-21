"""COG-LU-IPC-01A: inert, source-pinned Lu workspace v0 provider proposal.

Lu Core owns the canonical Protobuf schema, transport admission, signed package
enrollment, user-turn grants, cancellation, journal and inference. This module
neither implements an IPC listener nor mints or exercises those authorities.

Cognitum's existing MEL adapter supplies five exact typed compute-only
descriptors; only those are proposed. SSM R6 remains unregistered until a
reviewed SSM request/result Protobuf codec and installed pure-compute bridge.
"""
from __future__ import annotations

import hashlib
import json
import re

from . import lu_adapter

PROFILE = "cognitum.mel.lu_workspace.v0.provider_proposal.v1"
LU_REPOSITORY = "vjmichael/Lu-AI-GUI"
LU_REVIEWED_SOURCE_SHA = "ea6e35e6a10a0754e166eb4c34a794eb0c9b5551"
LU_WORKSPACE_PROTO_GIT_BLOB = "4e01d921197fb1c58c99958479b1cede36e13c9a"
LU_PROTO_PATH = "src-tauri/lu-core/proto/lu/workspace/v0/workspace.proto"
MODULE_ID = "cognitum.mel"
MODULE_ROLE = "MODULE_ROLE_CORE_EXTENSION"
PURE_EFFECT = "EFFECT_CLASS_PURE_COMPUTE"
WIRE_MAJOR, WIRE_MINOR = 1, 0
MAX_TYPED_BYTES = 64 * 1024
REVIEWED_OPERATIONS = frozenset({
    "vfa.evaluate", "vfa.gradient", "hdc.bind", "hdc.query", "kan.evaluate",
})
SSM_PENDING_OPERATION = "cognitum.ssm.fixed_duration.advance.v1"
HEX_SHA = re.compile(r"[a-f0-9]{64}\Z")
TYPED_URL = re.compile(r"type\.googleapis\.com/[A-Za-z0-9_.]{1,160}\Z")


def _need(test, why):
    if not test:
        raise ValueError("Lu/Cognitum proposal refused: " + why)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("ascii")


def _reviewed_routes():
    candidate = lu_adapter.proposal()
    _need(candidate["profile"] == lu_adapter.PROFILE and
          candidate["registered"] is False and
          candidate["model_advertised"] is False and
          candidate["execution_authorized"] is False,
          "reference-only MEL adapter required")
    routes = candidate["routes"]
    _need(type(routes) is list and len(routes) == len(REVIEWED_OPERATIONS),
          "exact five reviewed MEL routes")
    seen = set()
    cap = []
    audit = []
    for route in routes:
        _need(type(route) is dict and
              route.get("operation") in REVIEWED_OPERATIONS and
              route["operation"] not in seen and
              route.get("required_effect") == "compute_only",
              "unexpected/unapproved effect or operation")
        seen.add(route["operation"])
        input_type = route["input_type_url"]
        output_type = route["output_type_url"]
        descriptor_sha = route["descriptor_sha256"]
        codec_sha = route["codec_sha256"]
        _need(type(input_type) is str and TYPED_URL.fullmatch(input_type)
              and type(output_type) is str and TYPED_URL.fullmatch(output_type),
              "native generated Protobuf type URLs required")
        _need(type(descriptor_sha) is str and HEX_SHA.fullmatch(descriptor_sha)
              and type(codec_sha) is str and HEX_SHA.fullmatch(codec_sha),
              "exact source/codec identity required")
        operation = route["operation"]
        cap.append(dict(
            capability_id="cognitum." + operation,
            capability_version=1,
            input_type_url=input_type,
            output_type_url=output_type,
            declared_effects=[PURE_EFFECT],
            streams_progress=False,
            display_name=route["public_name"],
        ))
        audit.append(dict(operation=operation,descriptor_sha256=descriptor_sha,
                          codec_sha256=codec_sha,
                          operation_version=route["operation_version"],
                          input_type_url=input_type,
                          output_type_url=output_type))
    _need(seen == REVIEWED_OPERATIONS, "incomplete MEL route coverage")
    return sorted(cap,key=lambda x:x["capability_id"]), sorted(audit,key=lambda x:x["operation"])


def proposal():
    """Return audit metadata and an *unsubmitted* Lu RegisterWorkspace candidate.

    Even a manifest hash is NOT a package signature, a Lu registration grant,
    a verified installed peer or a user-turn authorization.
    """
    caps, audit = _reviewed_routes()
    manifest = dict(module_id=MODULE_ID,kind=MODULE_ROLE,
                    capabilities=caps,manifest_revision=1)
    digest = hashlib.sha256(b"Cognitum.LuWorkspaceV0.ManifestCandidate.v1\x00"
                            + _canonical(manifest)).hexdigest()
    return dict(schema=PROFILE,
                lu_owner=LU_REPOSITORY,
                lu_source_sha=LU_REVIEWED_SOURCE_SHA,
                lu_proto_path=LU_PROTO_PATH,
                lu_proto_git_blob_sha=LU_WORKSPACE_PROTO_GIT_BLOB,
                protocol_major=WIRE_MAJOR,protocol_minor=WIRE_MINOR,
                candidate_manifest_sha256=digest,
                register_workspace=manifest,
                reviewed_mel_bindings=audit,
                pending_ssm_operation=SSM_PENDING_OPERATION,
                **dict(
                    registered=False,model_advertised=False,
                    connection_authenticated=False,
                    pure_compute_host_bridge_qualified=False,
                    execution_authorized=False,
                    installed_service_qualified=False,
                    host_grant_issued=False,
                ))


def validate_external_lu_proto_blob(actual_blob_sha):
    """Host preflight must source-pin Lu's real schema before any compilation.

    Git blob identity is distinct from a Git commit and a signed installer.
    This check cannot independently authenticate GitHub or a peer.
    """
    _need(type(actual_blob_sha) is str
          and actual_blob_sha == LU_WORKSPACE_PROTO_GIT_BLOB,
          "Lu workspace v0 source drift; refresh review before enabling")
    return True


def refuse_unsupported_invoke(effect_class, capability_id, *, host_pure_bridge=False):
    """Never 'upgrade' inert metadata into a tool grant.

    A future installed host must implement the pure-compute effect mapping
    and independently validate every exact typed input/turn/receipt.
    """
    _need(effect_class == PURE_EFFECT and type(capability_id) is str
          and capability_id in {"cognitum." + x for x in REVIEWED_OPERATIONS},
          "unreviewed effect or capability")
    _need(host_pure_bridge is True, "Lu Core PURE_COMPUTE admission missing")
    # Even an asserted true flag is not OS/host admission evidence.
    raise ValueError("Lu/Cognitum proposal refused: no installed authenticated Lu invocation")
