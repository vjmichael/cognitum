# C01 — Cognitum → Lu DLC Core Extension Discovery and Model Augmentation Handoff

**Review performed:** 2026-10-26 (read-only Lu audit)  
**Latest Lu reference:** `vjmichael/jan_alt@lu/independent-branding-ce-foundation`, commit `75d558c083dc96660528dd6fb8c745af34469503`. This branch is **two commits ahead** of the older `lu/core-contracts-native-registry` branch.  
**Cognitum implementation:** [`cognitum/lu_ce_handoff.py`](../../../cognitum/lu_ce_handoff.py) and [review JSON exporter](../../../tools/emit_lu_ce_handoff.py)  
**Status:** **Merged via [Cognitum PR #5](https://github.com/vjmichael/cognitum/pull/5)** at commit `82210ecf828b0951917421d061ea4882937b11d1`. The handoff is still **non-installable, inactive, non-advertised** and **not** a Lu host ABI certification. No Lu files were modified. [Four-platform branch CI](https://github.com/vjmichael/cognitum/actions/runs/40449813005) and [PR CI](https://github.com/vjmichael/cognitum/actions/runs/40449936995) passed: **105/105 unit tests, 12/12 synthetic replay and compiler-checked Protobuf** per Windows/Linux Python 3.11/3.13 configuration; formal JSON Schema positive/negative tests included.

## What Lu's newer code already decided and built

The newer Lu branch contains actual early Core Extension machinery that was absent from our earlier integration audit. Treat the old statement “Lu has only Core and Workspace module kinds” as **superseded for this newer branch**.

| Lu source | What exists now | What it does not yet accomplish |
|---|---|---|
| [`contracts.rs`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/contracts.rs) | `ModuleKind::{Core, CoreExtension, Workspace}`; `ModuleManifest` fields `id,display_name,contract_version,kind,tools,panels,workflows`; qualified tool IDs, **one** required `ToolEffect`, exact Protobuf type URLs | Does not define a native `Pure/NoEffect` effect for inert computation or a multi-effect declaration |
| [`core_extension.rs`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/core_extension.rs) | `CoreExtensionHost::register_trusted`, `unregister_trusted`, `extensions`; native CEs are reusable for ordinary chat and Workspaces, independent of vanilla Core | Not a package installer, trust-signature verifier, full dependency manager, OS worker or completed cancellation/drain supervisor |
| [`registry.rs`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/registry.rs) | Atomic registration, qualified ID and type URL checks, protected Core, independent CE unload and per-call authorizer | Unloading blocks *new* dispatch but cannot itself terminate already executing calls |
| [`tests/core_extension_lifecycle.rs`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/tests/core_extension_lifecycle.rs) | Tests optional extension register/unload and denial by host policy | Does not establish third-party Cognitum compatibility or production desktop wiring |
| [`model.rs`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/src/model.rs) | `ModelToolDefinition` with public short name, description, **closed JSON object schema** and a matched `ModelToolCodec`; `ModelToolCatalog` explicitly allowlists a max of **16** model tools per turn; encode JSON → typed Protobuf; decode native result → JSON success/error | It does **not** automatically expose everything in the CE registry. Tool visibility and model/tool compatibility are host decisions |
| [`proto/lu/v1/core.proto`](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/proto/lu/v1/core.proto) | `ToolCall` carries `tool_id,input_type_url,input bytes`, `ToolReply.oneof outcome` carries success bytes or typed failure | It doesn't contain Cognitum's domain messages; the CE must supply generated message types, reviewed bridge and schemas |
| [Lu Core README](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/src-tauri/lu-core/README.md) / [architecture](https://github.com/vjmichael/jan_alt/blob/lu/independent-branding-ce-foundation/docs/lu-architecture-and-roadmap.md) | Lu is local-first host/orchestrator of selected model; CEs reusable, Workspaces specialized environments; ANSF and authenticated task lineage stay host-owned; HDC advisory not authority | Source documentation identifies CE distribution, desktop lifecycle, full model/provider wiring and third-party sandboxing as open |

**Preserved user decisions:** DLC CEs are optional, distributable, Lu-native reusable capabilities, **not MCP servers or mandatory Core features**. DLC Workspaces are distinct full application experiences (Film Studio/IDE), using Lu services/CEs without replacing vanilla Lu. Cognitum augments **whichever model Lu has loaded**; it does **not** choose a hidden second model, grant permission, retrain weights, or substitute its own agent loop. Separate Lu team owns any host changes.

**Additional recovered user decisions from the parallel Lu conversations:** Workspaces should maintain **their own separate registries**, detachable DLCs should not disrupt vanilla Lu or unrelated CEs, and loaded Workspaces should provide tool descriptions/schemas plus workflow, state and event metadata so Lu can inform the active transformer how to use their capabilities. **These are accepted architecture goals, not a claim that their exact IPC/broker and workspace registry protocol is already implemented.** The new handoff emits `workspace_interop_proposal` declaring that intent, with empty workflow/state/event arrays for the calculator and explicit no-change-to-model-weights semantics. No additional workspace features are invented.

**External tool-definition rule:** Lu's existing model-facing `ModelToolDefinition.description` is the text the selected transformer will actually see if the host chooses to advertise a tool; therefore Cognitum's fixed calculator description explicitly includes **when to use**, **when not to use**, and **epistemic limitations**, not merely the capability name. The longer trusted `use_when/avoid_when/output_interpretation` fields are advisory for Lu's possible future context assembly, not a side channel granting permissions. All guidance is fixed developer-authored data; generated prompts and retrieved content cannot change it.

## Two complementary contracts, not competing protocols

1. **Trusted CE/host interface proposal:** a `CoreExtension`-kind `ModuleManifest` reflecting actual Lu Rust field names and `CORE_CONTRACT_VERSION=1`. The current calculator is represented with `effect: null` **ONLY as an explicit incompatibility marker**—this is **not** a valid runnable Lu `ToolDescriptor`. `availability.installable/registered/enabled/model_advertised/host_contract_approved` are all **false**. Never replace the missing pure effect with `ReadWorkspace`: that would declare unnecessary workspace access.
2. **External model-facing tool proposal:** when **Lu** later verifies installation, grants and model compatibility, it can choose a strict `ModelToolDefinition` derived from Cognitum's trusted operation metadata:
   - `name`: `cognitum_calc_rational` (a legal Lu short model-tool name)
   - `description`: bounded, reviewed explanation of the formal expression, exactness and intent limits
   - `parameters`: closed JSON schema requiring bounded `expression` string with no additional properties
   - `native_tool_id`: `cognitum.calc.rational`, `input_type_url`: `type.googleapis.com/cognitum.v1.CalculateRationalRequest`, `output_type_url`: `type.googleapis.com/cognitum.v1.CalculateRationalResult`
   - `use_when`, `avoid_when`, and `output_interpretation` guide the host's model instructions **without becoming permission**, nor being inserted into the model's context unless Lu explicitly chooses.

**Internal invocation stays Protobuf**, per the user's explicit correction: Lu owns `lu.v1.ToolCall/ToolReply` and each `ModelToolCodec`, while Cognitum owns generated `cognitum.v1` request/result domain message types and validates decoded fields. **JSON is an external model-facing schema, not native IPC.** Cognitum's actual [native Protobuf codec](../../../cognitum/protobuf_codec.py) is separately tested. No imaginary `lu.v1.CognitumInstallExtension` protobuf call or alternative host is invented.

## Formal discovery metadata validation

The [v1 declarative handoff JSON Schema](../../../schemas/lu_ce_handoff_v1.schema.json) is a Draft 2020-12 **closed object schema**. It requires the proposed `CoreExtension` module kind, precise `cognitum.v1` Protobuf type URLs, the single reviewed arithmetic JSON argument schema, matched source-schema hash, a required **null** effect incompatibility marker, and all host enablement/registration/advertisement/approval flags set to **false**. The validator rejects extra grant fields, fabricated workspace workflows and attempts to turn the prototype into an installed native CE.

`tests/test_lu_ce_handoff.py` runs schema validation and negative mutations with `jsonschema` on CI; `jsonschema` is deliberately a **CI-only dependency**, not required to run Cognitum's default stdlib-only core. The host still needs an independently reviewed manifest loader and to check native schemas and signatures; validating declarative JSON is not authorization.

**Package format:** the canonical operational payloads remain **binary Protobuf** (`cognitum.v1`) within Lu's own `lu.v1.ToolCall/ToolReply`. The declarative handoff is JSON Schema only because Lu's **model-facing tool catalog** uses closed JSON function parameter schemas. No second runtime RPC or alternative host envelope is added.

## How the loaded AI learns when to augment its work

```text
Cognitum DLC CE package metadata [TRUSTED DEVELOPER PROPOSAL]
    ↓ reviewed by Lu CE loader / signature + ABI + OS worker vetting
Lu CoreExtensionHost → NativeToolRegistry (host-owned)
    ↓ model/session/task authorization + compatible tool-call support
Lu ModelToolCatalog (allowed tools, MAX_ADVERTISED_TOOLS <=16)
    ↓ external model-facing JSON function schema & concise capability usage guidance
Lu's currently selected transformer proposes a tool call
    ↓ strict JSON arguments → Lu-generated Protobuf → Lu authorizes exact operation
    ↓ Cognitum CE verifies cognitum.v1 request and computes bounded result
    ↓ cognitum.v1 success Protobuf, or Lu native failure arm
Lu ModelToolCodec validates/decodes into model-visible structured result
    ↓ model reasons with exactness, provenance, uncertainty and limitations
```

**Important: no automatic "self-augmentation" claim.** This is controlled *inference-time access to specialists*. The model does not independently install a CE, add permissions, update its weights or bypass Lu's authorization. A model without reliable structured tool calling must not be shown capabilities it cannot invoke, and Lu should record unavailable/unsupported status honestly. Do not overload the tool menu by advertising all 19 Cognitum research components.

## Current v1 prototype — exactly one reviewed model-use guide

The C01 [`create_lu_ce_handoff`](../../../cognitum/lu_ce_handoff.py) validates the **exact existing `Calculator().manifest()`**, its single real Protobuf mapping and a **fixed reviewed usage guide**. It rejects unknown component names, schema drift, altered plugin version, effectful operations, changed Protobuf type URLs and modified prompt-like guidance. It emits **a proposal only**; no model can change its enabled/registered/advertised flags.

**To inspect the deterministic, machine-readable JSON review artifact:**

```sh
python tools/emit_lu_ce_handoff.py
```

This command runs no plugin or Lu executable. The JSON includes clear `model_tool_definition_proposal` and `availability.blocking_contracts` sections. Lu's future loader may consume only metadata after independent trust review; the output file is **not** something to drag into Lu as an installed CE yet.

For future HDC/KAN/memory/planner modules, v1 must **not** silently invent model schemas or permissions. Add a reviewed capability description and actual Protobuf request+result, match its real effects, test cross-source privacy and benchmark efficacy **before** marking it eligible for Lu advertisement. Generated text/retrieved docs must not rewrite the trusted use/avoid guides.

## Outstanding Lu-side questions, not Cognitum changes

- **LU-CE-001 (revised):** module kind and trusted registration/unregister exist. Remaining: signed/verified install, dependency mapping, default-off/persistent enable state, secure worker unloading and cancellation/in-flight draining.
- **LU-CE-002 (newly critical):** `ToolDescriptor.effect` must support **zero-effect/pure computation** (or an equivalently non-authorizing design) to represent the calculator honestly, as well as accurate multi-effect resource-scoped operations when needed. Do not fake `ReadWorkspace` on a pure calculation.
- **LU-CE-003:** shared built `cognitum.v1` generated schema/descriptors and version negotiation, Rust codecs and breaking-change checks.
- **LU-CE-004:** trusted host attaches developer-authored descriptions and `ModelToolCodec` to *registered* tools, with per-conversation/model/tool-budget selection and full ephemeral revocation on CE unload.
- **LU-CE-005/006/008:** task-bound user-origin authority, brokered OS workers, canonical memory snapshot/update/delete without crossing profile lines.

All are tracked in [the Cognitum-owned addendum register](../../lu-dlc-ce-addenda.md); the separate Lu team decides how/when to implement them.

**Cognitum-only model discovery update:** `availability.requires_model_function_calling=true` and `lu_model_tool_budget_observed=16` report a read-only Lu branch finding, **not** a grant or confirmed model-tool support on the user's currently loaded transformer. Before any future Lu exposure, Lu should verify the active model/provider's actual function-call reliability and session eligibility. `workspace_interop_proposal` is metadata, not an active plugin API.

**Verification gates:** tests must check stable model JSON parameter schema, exact Protobuf type URLs, no model visibility/installation by default, no extra effect or scope, altered metadata rejection, and that guidance cannot be changed by retrieved content. **C01 P1/P2 tests are not proof of actual Lu installation, security, or improved LLM performance**.
