"""Canonical, inert Cognitum -> Lu CE discovery handoff: binary Protobuf.

This does NOT create a Lu ToolCall/ToolReply, install an extension, authorize
a tool or communicate with an LLM. Existing Python dictionaries are a local
legacy diagnostic projection; JSON is emitted only by explicit provider-edge
adapter calls. Lu owns native CE enrollment and external model interfaces.
"""
from google.protobuf.message import DecodeError

from .ce_manifest import ProposedToolBinding
from .contracts import digest
from .lu_ce_handoff import CALCULATOR_GUIDE, create_lu_ce_handoff
from .plugins.calculator import Calculator
from .proto import ce_handoff_pb2 as pb

HANDOFF_TYPE_URL = "type.googleapis.com/cognitum.v1.CoreExtensionHandoff"
MAX_HANDOFF_BYTES = 16 * 1024
HANDOFF_WIRE_SCHEMA_VERSION = 1


def _binding():
    return ProposedToolBinding(
        cognitum_operation="calc.rational",
        native_tool_id="cognitum.calc.rational",
        model_tool_name="cognitum_calc_rational",
        input_type_url="type.googleapis.com/cognitum.v1.CalculateRationalRequest",
        output_type_url="type.googleapis.com/cognitum.v1.CalculateRationalResult",
    )


def create_lu_ce_handoff_proto():
    """Build the reviewed, unregistered v1 prototype as a typed message.

    Uses existing C01 trusted source-contract checks, then maps into explicit
    Proto fields. There are NO generic JSON blobs, Any payloads or permissions.
    """
    source = Calculator().manifest()
    reviewed = create_lu_ce_handoff(source, "cognitum.calc",
                                    (_binding(),), (CALCULATOR_GUIDE,))
    capability, = reviewed["capabilities"]
    arg_schema = capability["model_tool_definition_proposal"]["function"]["parameters"]
    if arg_schema != {
        "type": "object", "additionalProperties": False,
        "required": ["expression"],
        "properties": {"expression": {
            "type": "string", "minLength": 1, "maxLength": 256}},
    }:
        raise ValueError("unreviewed provider-bound argument schema")
    message = pb.CoreExtensionHandoff(schema_version=HANDOFF_WIRE_SCHEMA_VERSION)
    meta = reviewed["source_ref"]
    message.source.repository = meta["repository"]
    message.source.branch = meta["branch"]
    message.source.commit = meta["commit"]
    message.source.host_contract_version = meta["host_core_contract_version"]

    manifest = reviewed["host_manifest_proposal"]
    message.module.id = manifest["id"]
    message.module.display_name = manifest["display_name"]
    message.module.kind = manifest["kind"]
    message.module.host_contract_version = manifest["contract_version"]
    message.module.panels.extend(manifest["panels"])
    message.module.workflows.extend(manifest["workflows"])

    cap = message.capabilities.add()
    cap.operation = capability["operation"]
    cap.operation_schema_version = capability["operation_schema_version"]
    cap.native_tool_id = capability["native_tool_id"]
    cap.input_type_url = capability["native_input_type_url"]
    cap.output_type_url = capability["native_output_type_url"]
    cap.host_effect_status = capability["effect_mapping_status"]
    cap.result_assurance = capability["result_assurance"]
    cap.epistemic_limitations.extend(capability["epistemic_limitations"])
    cap.declared_effects.extend(capability["required_effects"])
    cap.input_schema_sha256 = capability["input_json_schema_sha256"]
    cap.model_use.name = capability["model_tool_definition_proposal"]["function"]["name"]
    cap.model_use.description = CALCULATOR_GUIDE.description
    cap.model_use.use_when = CALCULATOR_GUIDE.use_when
    cap.model_use.avoid_when = CALCULATOR_GUIDE.avoid_when
    cap.model_use.output_interpretation = CALCULATOR_GUIDE.output_interpretation
    cap.model_use.arguments.add(
        name="expression", kind="string", required=True,
        min_length=1, max_length=256,
    )

    workspace = reviewed["workspace_interop_proposal"]
    message.workspace.contexts.extend(workspace["ce_reusable_in"])
    message.workspace.registries_separate = workspace["workspace_registries_remain_separate"]
    message.workspace.unload_preserves_core_and_other_dlc = workspace[
        "ce_removal_must_preserve_core_and_unrelated_dlc"]
    message.workspace.model_weights_unchanged = workspace["loaded_transformer_weights_unchanged"]

    availability = reviewed["availability"]
    for field in ("installable", "registered", "enabled",
                  "model_advertised", "host_contract_approved",
                  "requires_model_function_calling"):
        setattr(message.availability, field, availability[field])
    message.availability.observed_max_model_tools = availability[
        "lu_model_tool_budget_observed"]
    message.availability.blocking_contracts.extend(availability["blocking_contracts"])
    message.producer_manifest_sha256 = reviewed["producer_source_manifest_sha256"]
    message.trust_statement = reviewed["trust_statement"]
    if len(message.SerializeToString(deterministic=True)) > MAX_HANDOFF_BYTES:
        raise ValueError("native CE discovery handoff exceeds wire limit")
    return message


def encode_lu_ce_handoff():
    """Emit actual binary Protobuf, never JSON in the native handoff."""
    return create_lu_ce_handoff_proto().SerializeToString(deterministic=True)


def decode_lu_ce_handoff(payload):
    """Fail-closed v1 decoder for the *currently reviewed inert fixture*.

    The v1 proposal has exactly one fixed calculator and no grants. Unknown
    fields, different versions, modified guidance, any enablement claim or
    additional capabilities cannot be promoted by a caller. The separate
    trusted Lu host MUST still check signatures and authorization.
    """
    if type(payload) is not bytes or not 0 < len(payload) <= MAX_HANDOFF_BYTES:
        raise ValueError("invalid CE discovery Protobuf frame")
    message = pb.CoreExtensionHandoff()
    try:
        message.ParseFromString(payload)
    except DecodeError as exc:
        raise ValueError("malformed CE discovery Protobuf") from exc
    known = pb.CoreExtensionHandoff()
    known.CopyFrom(message)
    known.DiscardUnknownFields()
    if known != message:
        raise ValueError("unrecognized CE discovery Protobuf fields")
    if message != create_lu_ce_handoff_proto():
        raise ValueError("unreviewed CE capabilities, metadata or authority claims")
    return message


def model_boundary_function_definition(message):
    """Generate a provider-facing JSON function schema *at the external edge*.

    This is never serialized into the internal Protobuf handoff. Lu may choose
    not to expose this tool at all, depending on model compatibility, grants,
    installed CE state and tool budget.
    """
    if not isinstance(message, pb.CoreExtensionHandoff):
        raise TypeError("native typed handoff required")
    # A typed in-process message can also be mutated after construction.
    decode_lu_ce_handoff(message.SerializeToString(deterministic=True))
    cap, = message.capabilities
    required = [arg.name for arg in cap.model_use.arguments if arg.required]
    properties = {}
    for arg in cap.model_use.arguments:
        if arg.kind != "string" or not 1 <= arg.min_length <= arg.max_length <= 256:
            raise ValueError("unsupported provider-bound argument")
        properties[arg.name] = {
            "type": "string", "minLength": arg.min_length,
            "maxLength": arg.max_length,
        }
    parameters = {
        "type": "object", "additionalProperties": False,
        "required": required, "properties": properties,
    }
    if digest(parameters) != cap.input_schema_sha256:
        raise ValueError("model-boundary schema fingerprint mismatch")
    return {
        "type": "function",
        "function": {
            "name": cap.model_use.name,
            "description": cap.model_use.description,
            "parameters": parameters,
        },
    }
