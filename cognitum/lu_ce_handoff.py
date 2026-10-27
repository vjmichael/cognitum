"""Read-only Lu CE discovery handoff *proposal*, not a runnable extension.

Lu's current Rust ModelToolCatalog has an external JSON-schema/model-facing
boundary and typed Protobuf internal dispatch. This module generates ONLY a
trusted-developer proposal for that external catalog; execution still requires
Lu's own native CE loader, permission grant, codec and registered implementation.

Do not use a model-produced manifest, prompt or source document as an argument.
"""
from dataclasses import dataclass
from .ce_manifest import ProposedToolBinding, compatibility_fixture
from .contracts import Manifest, digest
from .plugins.calculator import Calculator

HANDOFF_SCHEMA_VERSION = "1.0.0"
LU_HOST_CONTRACT_VERSION = 1
# Lu branch at the point of this read-only audit; this branch is not a release.
LU_SOURCE_REVISION = "75d558c083dc96660528dd6fb8c745af34469503"

# Fixed, reviewed model-facing copy. A model does not get to rewrite a guide.
_CALCULATOR_DESCRIPTION = (
    "Use only for exact rational arithmetic after you have formalized a "
    "bounded expression (+,-,*,/,integer powers). Avoid live facts, dates, "
    "currency conversion, file reads, code execution, or permissions. "
    "The result is exact for the expression but does not verify user intent; "
    "preserve the intent_not_verified limitation."
)
_CALCULATOR_USE = (
    "Use for exact arithmetic when you can explicitly formalize a numerical "
    "question as a supported expression. Verify the expression represents "
    "the user's intended question and units before trusting the calculation."
)
_CALCULATOR_AVOID = (
    "Do not use for web facts, live currency or dates, unsupported functions, "
    "arbitrary code, document interpretation, permission checks, or claims "
    "that the user's intent was independently verified."
)
_CALCULATOR_RESULT = (
    "The returned rational is exact for its validated formal input only. "
    "Preserve evidence and intent_not_verified; never present computation "
    "provenance as proof of task interpretation or authority."
)


@dataclass(frozen=True)
class ModelUseGuide:
    """Developer-supplied use/avoid semantics for one implemented operation."""
    operation: str
    description: str
    use_when: str
    avoid_when: str
    output_interpretation: str

    def __post_init__(self):
        for value in (self.operation, self.description, self.use_when,
                      self.avoid_when, self.output_interpretation):
            if type(value) is not str or not 1 <= len(value) <= 700:
                raise ValueError("model guidance must be bounded, nonempty text")


CALCULATOR_GUIDE = ModelUseGuide(
    operation="calc.rational",
    description=_CALCULATOR_DESCRIPTION,
    use_when=_CALCULATOR_USE,
    avoid_when=_CALCULATOR_AVOID,
    output_interpretation=_CALCULATOR_RESULT,
)


def _checked_model_schema(operation):
    """Exact external model JSON schema from the source operation."""
    schema = operation.input.json_schema()
    if (schema.get("type") != "object"
            or schema.get("additionalProperties") is not False
            or not schema.get("required")):
        raise ValueError("model arguments must be a closed required object")
    return schema


def create_lu_ce_handoff(
    source: Manifest,
    ce_id: str,
    bindings: tuple[ProposedToolBinding, ...],
    guides: tuple[ModelUseGuide, ...],
):
    """Produce deterministic host-review metadata, WITHOUT enabling any tools.

    Current Lu ToolEffect has no no-effect/compute-only variant, therefore
    a pure calculator cannot be registered faithfully yet. We never invent
    ReadWorkspace, read user data, or claim installation or model approval.
    """
    fixture = compatibility_fixture(source, ce_id, bindings)
    if type(guides) is not tuple or not guides:
        raise ValueError("explicit trusted usage guides required")
    guide_map = {}
    for guide in guides:
        if not isinstance(guide, ModelUseGuide) or guide.operation in guide_map:
            raise ValueError("duplicate or invalid model usage guide")
        guide_map[guide.operation] = guide
    ops = {o.name: o for o in source.operations}
    if set(guide_map) != set(ops):
        raise ValueError("exactly one model guide per source operation")

    # The only approved capability study is existing inert exact calculator.
    # Additional capability classes require independent P0 evidence and a
    # separately reviewed candidate decoder/host permissions.
    if (set(ops) != {"calc.rational"} or guide_map["calc.rational"] != CALCULATOR_GUIDE
            or source.describe() != Calculator().manifest().describe()):
        raise ValueError("unreviewed capability cannot be advertised through v1 proposal")
    tools = []
    for proposed in fixture["proposed_tools"]:
        name = proposed["cognitum_operation"]
        operation = ops[name]
        guide = guide_map[name]
        binding = next(b for b in bindings if b.cognitum_operation == name)
        if operation.effects:
            raise ValueError("effectful operation cannot be represented by inert CE proposal")
        if (binding.input_type_url !=
                "type.googleapis.com/cognitum.v1.CalculateRationalRequest"
                or binding.output_type_url !=
                "type.googleapis.com/cognitum.v1.CalculateRationalResult"):
            raise ValueError("unexpected generated Protobuf domain message types")
        schema = _checked_model_schema(operation)
        tools.append({
            "operation": name,
            "operation_schema_version": operation.schema_version,
            "native_tool_id": binding.native_tool_id,
            "native_input_type_url": binding.input_type_url,
            "native_output_type_url": binding.output_type_url,
            "required_effects": [],
            # Lu's ToolDescriptor has exactly one required ToolEffect and no
            # Pure/None variant, so NULL here is an explicit INCOMPATIBILITY.
            "lu_tool_effect": None,
            "effect_mapping_status": "blocked_no_effect_free_variant",
            "result_assurance": operation.assurance,
            "epistemic_limitations": ["intent_not_verified"],
            "use_when": guide.use_when,
            "avoid_when": guide.avoid_when,
            "output_interpretation": guide.output_interpretation,
            "model_tool_definition_proposal": {
                "type": "function",
                "function": {
                    "name": binding.model_tool_name,
                    "description": guide.description,
                    "parameters": schema,
                },
            },
            "input_json_schema_sha256": digest(schema),
        })

    return {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "kind": "cognitum.lu_core_extension_handoff_proposal",
        "source_ref": {
            "repository": "vjmichael/jan_alt",
            "branch": "lu/independent-branding-ce-foundation",
            "commit": LU_SOURCE_REVISION,
            "host_core_contract_version": LU_HOST_CONTRACT_VERSION,
        },
        "host_manifest_proposal": {
            "id": ce_id,
            "display_name": "Cognitum exact arithmetic (proposal)",
            "kind": "CoreExtension",
            "contract_version": LU_HOST_CONTRACT_VERSION,
            "tools": [
                {
                    "id": t["native_tool_id"],
                    "display_name": "Exact rational arithmetic",
                    "effect": None,  # Lu has no effect-free variant yet.
                    "input_type_url": t["native_input_type_url"],
                    "output_type_url": t["native_output_type_url"],
                } for t in tools
            ],
            "panels": [],
            "workflows": [],
        },
        "producer_source_manifest_sha256": digest(source.describe()),
        "capabilities": tools,
        "workspace_interop_proposal": {
            # Confirmed user design direction; no Lu runtime API is implied.
            "ce_reusable_in": ["vanilla_chat", "host_approved_workspace"],
            "workspace_registries_remain_separate": True,
            "workspace_tool_schemas": [],  # host chooses which to expose
            "workspace_workflows": [],
            "workspace_state_contracts": [],
            "workspace_event_contracts": [],
            "loaded_transformer_weights_unchanged": True,
            "ce_removal_must_preserve_core_and_unrelated_dlc": True,
        },
        "availability": {
            "installable": False,
            "registered": False,
            "enabled": False,
            "model_advertised": False,
            "host_contract_approved": False,
            "requires_model_function_calling": True,
            "lu_model_tool_budget_observed": 16,
            "blocking_contracts": [
                "Lu effect-free ToolEffect mapping for pure compute",
                "trusted CE installer and worker lifecycle",
                "host-provided ModelToolCodec with registered native tool",
                "authenticated task-scoped host authorizer",
            ],
        },
        "trust_statement": (
            "Capability descriptions and schemas are proposals only. "
            "Lu may advertise a tool only after trusted registration, "
            "host authorization, validated generated Protobuf codecs, "
            "model compatibility and per-session allowlisting."
        ),
    }
