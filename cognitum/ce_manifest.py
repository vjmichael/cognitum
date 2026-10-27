"""Inert Cognitum-side proposal fixtures for an eventual Lu DLC Core Extension.

This module has NO Lu host adapter, Protobuf generated types, module loading,
model tool registration, IPC, sandbox, or activation path. It deliberately
fails closed on effectful operations while Lu's optional CE/effect contracts
are still under separate review. Model input must never construct bindings.
"""
from dataclasses import dataclass
import re

from .contracts import Manifest, digest

# Mirror only syntax constraints observed in Lu's experimental native branch;
# these are compatibility checks, not a claim to implement Lu's SDK.
_NATIVE_ID = re.compile(r"[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+\Z")
_MODEL_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_TYPE_URL = re.compile(
    r"type\.googleapis\.com/[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z"
)


def _require_native_id(value: str):
    if (type(value) is not str or len(value) > 128
            or not _NATIVE_ID.fullmatch(value)
            or any(len(part) > 64 for part in value.split("."))):
        raise ValueError("invalid proposed Lu-native identifier")


@dataclass(frozen=True)
class ProposedToolBinding:
    """Trusted developer-declared mapping, never a model-produced tool call."""

    cognitum_operation: str
    native_tool_id: str
    model_tool_name: str
    input_type_url: str
    output_type_url: str

    def __post_init__(self):
        if (type(self.cognitum_operation) is not str
                or not self.cognitum_operation
                or len(self.cognitum_operation) > 128):
            raise ValueError("invalid source operation")
        _require_native_id(self.native_tool_id)
        if (type(self.model_tool_name) is not str
                or len(self.model_tool_name) > 64
                or not _MODEL_NAME.fullmatch(self.model_tool_name)):
            raise ValueError("invalid model-visible tool name")
        for value in (self.input_type_url, self.output_type_url):
            if (type(value) is not str or len(value) > 512
                    or not _TYPE_URL.fullmatch(value)):
                raise ValueError("invalid proposed Protobuf type URL")


def compatibility_fixture(
    manifest: Manifest,
    ce_id: str,
    bindings: tuple[ProposedToolBinding, ...],
):
    """Create a deterministic, *non-installable* CE contract design snapshot.

    Effectful source operations are rejected: the current Lu experiment
    declares one ToolEffect per descriptor, while Cognitum can declare sets
    of effects. We must not create a misleading reduced-permission mapping.
    """
    if not isinstance(manifest, Manifest):
        raise TypeError("a trusted Cognitum Manifest is required")
    _require_native_id(ce_id)
    if type(bindings) is not tuple or not bindings:
        raise ValueError("at least one explicit binding is required")

    by_operation = {}
    model_names = set()
    native_ids = set()
    for binding in bindings:
        if not isinstance(binding, ProposedToolBinding):
            raise TypeError("bindings must be trusted ProposedToolBinding values")
        if (binding.cognitum_operation in by_operation
                or binding.model_tool_name in model_names
                or binding.native_tool_id in native_ids):
            raise ValueError("duplicate proposed tool mapping")
        if not binding.native_tool_id.startswith(ce_id + "."):
            raise ValueError("tool ID must be owned by proposed CE")
        by_operation[binding.cognitum_operation] = binding
        model_names.add(binding.model_tool_name)
        native_ids.add(binding.native_tool_id)

    operations = {operation.name: operation for operation in manifest.operations}
    if set(operations) != set(by_operation):
        raise ValueError("every operation needs exactly one explicit binding")
    tools = []
    for name in sorted(operations):
        operation, binding = operations[name], by_operation[name]
        if operation.effects:
            raise ValueError("effectful operation cannot use inert-only proposal")
        tools.append({
            "cognitum_operation": name,
            "cognitum_operation_schema_version": operation.schema_version,
            "native_tool_id": binding.native_tool_id,
            "model_tool_name": binding.model_tool_name,
            "input_type_url_proposed": binding.input_type_url,
            "output_type_url_proposed": binding.output_type_url,
            "input_schema_hash_sha256": digest(operation.input.json_schema()),
            "output_schema_hash_sha256": digest(operation.output.json_schema()),
            "assurance": operation.assurance,
            "outcome_kind": operation.outcome_kind,
            "deterministic": operation.deterministic,
            "declared_effects": [],
        })

    return {
        "fixture_schema": "cognitum.ce_compatibility.v0",
        "host_name": "Lu",
        "host_contract_status": "unbound_proposal_not_host_approved",
        "module_kind_proposed": "optional_core_extension",
        "ce_id": ce_id,
        "default_enabled": False,
        "model_advertised": False,
        "installable": False,
        "source_manifest": {
            "name": manifest.name,
            "version": manifest.version,
            "contract_version": manifest.contract_version,
            "sha256": digest(manifest.describe()),
        },
        "proposed_tools": tools,
    }
