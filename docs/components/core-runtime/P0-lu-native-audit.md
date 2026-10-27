# C01 / P0 — Lu Native Integration Audit and Compatibility Design

**Captured:** 2026-10-26  
**Source revision:** `vjmichael/jan_alt`, branch `lu/core-contracts-native-registry`, commit `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df` (read-only source inspection).  
**Cognitum component:** C01 — Core Contract / Runtime; dependencies C02 Security, C03 Evaluation, C04 Lu Host Integration.  
**Stage:** P0 design/audit **in progress**. No claim of executable Cognitum↔Lu integration.  
**Authoritative user requirement:** whichever LLM transformer Lu loads must be the host model that Cognitum improves. Lu—not an independent Cognitum orchestrator—determines model, tool, user authority and collaboration. See [Lu × Cognitum contract](../../lu-cognitum-integration.md).

**Superseding discovery (2026-10-26):** A newer Lu branch, `lu/independent-branding-ce-foundation` at commit `75d558c083dc96660528dd6fb8c745af34469503`, **now has `ModuleKind::CoreExtension`, `CoreExtensionHost`, and separate CE unregister with tests**. For current CE compatibility decisions, follow [C01 newer branch review and model-facing handoff](P1-P2-lu-ce-discovery-handoff.md). The missing CoreExtension kind described below is **historical and no longer accurate for that newer branch**; packaging/worker lifecycle, model discovery, and permission mapping remain open. Notably, Lu's required singular ToolEffect lacks a **pure/no-effect** value, which now blocks accurate registration of even the inert calculator.

## 1. Correction to the initial main-branch survey

The initial [C01/P0 survey](P0-research.md) inspected Jan/Lu's `main` code. **The active Lu feature branch is substantially more advanced.** It already has an actual native registry, typed Protobuf contracts and a model-facing JSON adapter. Therefore an independent second registry, Tauri bridge, protocol envelope or agent loop would be duplicative.

| Capability already in Lu feature branch | Verified source | Scope / limitation |
|---|---|---|
| Native interface | [`lu-core/src/contracts.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/contracts.rs) | `NativeTool`, `ToolDescriptor`, `ToolInvocation`, `ToolAuthorizer`, typed `ProtoPayload`; Lu internal `CORE_CONTRACT_VERSION = 1`. Manifest currently has only `ModuleKind::Core` and `ModuleKind::Workspace` |
| Registry and dispatch | [`lu-core/src/registry.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/registry.rs) | Qualified IDs, atomic registration, per-call authorizer, type-URL checks, protection against device/privilege control; permits unloading **Workspace only**, not optional CEs. In-flight calls may finish |
| Generated transport | [`proto/lu/v1/core.proto`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/proto/lu/v1/core.proto), [`wire.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/wire.rs) | `ToolCall` / `ToolReply`; nominal 4 MiB invocation / 8 MiB reply limits; `optional workspace_id`; legacy JSON is explicitly transitional; tool implementations must validate generated message contents |
| Model JSON bridge | [`lu-core/src/model.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/model.rs) | `ModelToolCatalog`/`ModelToolCodec`, explicit name allow-list, strict external JSON→typed Protobuf conversions; current constants `MAX_MODEL_TOOL_ARGS_BYTES = 64 * 1024`, `MAX_ADVERTISED_TOOLS = 16` |
| First end-to-end native tools | [`lu-core/src/native_files.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/native_files.rs), [`src-tauri/src/core/lu.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/src/core/lu.rs) | Bundled read-only file tools; feature-gated desktop Tauri commands; only two explicit public tool names approved, with host-bound ephemeral thread root and read-only scope; not a general CE loader |
| Webview adapter | [`web-app/src/lib/luNativeTools.ts`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/web-app/src/lib/luNativeTools.ts) | Fixed two-tool allow-list and `lu_native_tool_catalog` / `lu_native_tool_execute` invocation. Cannot yet advertise a Cognitum tool |
| Jan legacy compatibility | [`tauri-plugin-agent-tools/src/lu_bridge.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/plugins/tauri-plugin-agent-tools/src/lu_bridge.rs) | Feature-gated native bridge, keeps Jan legacy policy in addition to Lu authorization; code explicitly says not connected to Cowork/Desktop. Do not mislabel it as current integration |
| Host security / records | [`policy.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/policy.rs), [`host_resource_authority.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/host_resource_authority.rs), [`host_session.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/src/host_session.rs) | Exact grants and experimental trusted resource/session models. The in-memory native policy is **not** a proof that webview-supplied thread IDs authenticate a user or that a restricted OS worker exists |
| Existing tests | [`lu-core/tests/protobuf_wire.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/tests/protobuf_wire.rs), [`registry_contracts.rs`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/tests/registry_contracts.rs), [`web-app/src/lib/__tests__/luNativeTools.test.ts`](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/web-app/src/lib/__tests__/luNativeTools.test.ts) | Tests exist. Not rerun for this Cognitum audit; do not infer CI status or production Windows support from code inspection |

The [Lu Core README](https://github.com/vjmichael/jan_alt/blob/lu/core-contracts-native-registry/src-tauri/lu-core/README.md) itself distinguishes experimental contracts from full desktop/Cowork integration. The app's active model continues to be selected/loaded by Lu, not Cognitum. GitHub branch and source links are **not** a signed release or guaranteed future API.

## 2. Binding integration strategy — one authority, not two competing cores

**Recommendation for C01:**

1. **Lu's native `NativeToolRegistry` and `ModelToolCatalog` are authoritative** for model-advertised Cognitum operations, per-session grants and dispatch. Use Lu's existing `ToolAuthorizer` and policy engine; never reconstruct a second trusted host from a model-supplied Cognitum `HostContext`.
2. **Keep Cognitum's Python `Registry` / `Runtime` as a separate, standalone/offline evaluation and implementation environment** for components that are written in Python, with its current strict disabled/champion behavior. In Lu production, it may select a nominated **implementation provider within an already-authorized operation**, but it may **not** advertise hidden tools, enable itself or broaden scope. Reconcile the dual registry/version surfaces through one explicit host→provider mapping, not implicit routing.
3. **Integrate as a separately enableable Lu-native Core Extension (CE).** This is a user decision. It must not be hardcoded as a permanent `ModuleKind::Core` and must not be falsely represented as a full DLC Workspace. Current Lu contracts have no `Extension` variant. A reviewed native CE lifecycle/manifest contract must be added first, including id/version, dependencies, enable/disable, quarantine/uninstall and in-flight admission semantics. Until that exists, build/test a *non-advertised internal adapter fixture* rather than exposing a fake extension.
4. **First representative operation:** an existing deterministic, inert `cognitum.calc.rational` capability, not new HDC/KAN research. Define a dedicated generated request/result message and exact failure model, add a matched `ModelToolCodec` translating strict JSON to protobuf, and register the operation only after trusted host opt-in. A nominal public model name might be `cognitum_calc_rational`; final name depends on Lu catalog naming and collision checks.
5. **Do not reuse `LegacyJsonArguments` for new Cognitum capabilities.** Dedicated typed messages allow explicit missing/null/false/zero handling, range/length checks, and version tests. No magical conversion from arbitrary JSON to arbitrary proto bytes.
6. **Rust is the narrow host-side adapter; Python is a candidate calculation/research worker** if needed. The existing Python `multiprocessing.Pipe` uses object serialization and is not a secure worker protocol or OS sandbox. C02 must choose a bounded, length-delimited, typed wire with verified Windows confinement before untrusted/effectful providers.
7. **Lu owns model-facing availability.** If the selected transformer cannot use structured tools reliably, Lu must choose an independently tested mediation/user-triggered fallback, not treat unreliable model arguments as authoritative. A plugin that fails, is unhealthy, denied, disabled or incompatible must be withheld or report unavailability without fabricated results.
8. **No model weights are changed by normal Cognitum calls.** Component improvements must be demonstrated in P3 on the actual selected model(s) and task suite.

### Working data flow

```text
Lu model/provider + session
  → Lu ModelToolCatalog visible tool schema (enabled & explicitly allowed)
  → strict model JSON → CEx-specific generated Protobuf via ModelToolCodec
  → Lu NativeToolRegistry::dispatch with host ToolAuthorizer
  → Cognitum CE NativeTool wrapper; optional bounded worker
  → Cognitum domain implementation (exact/approx/research, as declared)
  → typed domain result + evidence/assurance/failure
  → Lu catalog output codec → structured model-visible result
  → selected transformer synthesizes; Lu preserves limitation disclosures
```

**Authority crossing:** Protobuf type-URL equality checks are **not** schema content validation; each generated adapter must decode and validate fields. Lu policy checks an effect descriptor, but arguments and multi-effect actual behavior need **separate verified scrutiny**. No model-created workspace IDs or local file paths are trusted.

## 3. Concrete compatibility gaps blocking a production bridge

| ID | Observed incompatibility or gap | Proposed resolution / ownership |
|---|---|---|
| **G01** | Lu `ModuleKind` currently has Core / Workspace only, while Cognitum must be optional Lu-native CE | **C01/C04:** define a distinct removable CE module kind and host-owned lifecycle; no fake Workspace mapping and no forcing optional cognitive modules into permanent Core |
| **G02** | Lu `ToolDescriptor.effect` describes **one** `ToolEffect`; Cognitum `Operation.effects` contains a **set** of scoped effects | **C02/C04:** design canonical effect-set representation with granular read/write/state/network scopes and argument-level validation, or split separate atomic operations with accurately declared effects. Never downgrade effects into read-only labels |
| **G03** | Lu `CORE_CONTRACT_VERSION` is `u16 = 1` and wire `ToolCall.contract_version` is `u32`; Cognitum Python `CONTRACT_VERSION = "1.3.0"` | **C01/C04:** explicitly separate **Lu host protocol version** from **Cognitum component schema/version**, choose compatible generated message evolution, hash source-specific schemas, fail closed on mismatches |
| **G04** | Lu `ModelToolCodec` already strictly handles model JSON ↔ typed protobuf; Cognitum `Shape` supports only closed objects of bounded strings | **C01:** use Lu native codec contract as outer boundary; keep current exact calculator shape initially and design richer typed schemas only for components requiring it. Avoid duplicate dynamic JSON validators in the host hot path |
| **G05** | Lu native catalog currently advertises only two built-in read-only tools, using a fixed webview name set | **C04:** extend host-controlled registry/catalog and webview exposure after CE lifecycle/permissions tested; limit per-turn tools, do not blanket advertise C01–C19 |
| **G06** | Lu production native invoke and in-memory policy are not proof of host-authenticated scope; experimental session/ownership modules remain partly unwired | **C02/C04:** tie calls to trusted window/profile/conversation enrollment and separate scoped capabilities before Cognitum memory/state reads or any effects |
| **G07** | Cognitum Python worker process, IPC, cancellation and quota semantics are not compatible with an adversarial producer | **C02:** OS-confined worker with typed bounded messages, CPU/RAM/process-tree limits and cleanup; allow trusted calculator as explicitly inert diagnostic fixture only |
| **G08** | Existing model/UI transport and Lu new native CE paths are evolving separately; old Jan/Cowork dispatch still exists | **C04:** introduce reversible, opt-in integration and feature tests in the **actual Lu feature branch**; don't replace shipping loop or main app based on a standalone core test |
| **G09** | Lu's envelope model-visible `ok/error` doesn't itself encode Cognitum interpretation/assurance, provenance and confidence semantics | **C01/C04:** define domain result fields and verified status mappings, including unavailable, denied, unsupported, timeout, inexact, unvalidated-formalization; never erase unknown/error into plausible prose |
| **G10** | Current P3 smoke fixtures cover only individual deterministic operations | **C03:** add controlled Lu+actual-model baselines (host alone; conventional reference tool; Cognitum; bounded composition) with provider/tool schema compatibility and fidelity measurements |

## 4. Contract-specific safety and version policy

**Version labels must remain distinct**: (a) Lu core/native host compatibility version, (b) generated Protobuf message type and field numbers, (c) Cognitum semantic operation schema version, and (d) Python implementation/research version. A numerical `1` on Lu wire cannot be treated as meaning the same thing as Cognitum `1.3.0`.

Protobuf `proto3` `optional` is required for scalars where missing differs from zero/false/empty; `oneof` for mutually exclusive success/error when needed. Never reuse removed field numbers; reserve them. Add Buf/protoc breaking checks against a pinned schema baseline before migrating a deployed format. Presence is also lost if a JSON codec strips null/omitted fields without a declared mapping.

Lu currently defines a **64 KiB** bound on model tool arguments, **4 MiB** invocation and **8 MiB** reply frames in `model.rs`/`wire.rs`; those are current branch constants, not proof every transport path imposes all relevant memory quotas. C01/C04 must enforce tight per-operation limits below the wire ceilings as appropriate.

Design security property: a model or retrieval result may **request** an operation but cannot mint `HostContext`, create/extend `CapabilityGrant`, select a privileged workspace identity or drive a resource outside its bound scope. All indirect effects and data exports must remain under C02's host and OS policy, with actual argument checks independent of any model tool schema.

## 5. First candidate C01→C04 adapter (design, not code)

**Manifest direction:** `cognitum.calc` as an optional Core Extension; stable operation ID `cognitum.calc.rational`, versioned input/output messages and an explicit default-off enablement. Do not register all Cognitum modules at startup as always-on core.

**Model-facing arguments:** `{ "expression": "<bounded arithmetic expression>" }`. Require exact string and bounded grammar. Unknown keys, malformed JSON, length violations, unsupported expressions and non-finite intermediates fail before execution with typed, sanitized errors. The existing Cognitum `Fraction` implementation is the initial computational reference; validate that expression formalization matches the user's intended question before treating its exact arithmetic as a final answer.

**Native request/results (to design in actual Lu source when C01 P0 exits):** dedicated `CalculateRationalRequest` and `CalculateRationalResult` types (candidate `cognitum.v1` package) plus a preserved host result/error envelope. Candidate result includes canonical rational string and assumption/limitation field; no fake calibrated confidence. Use Lu `ToolInvocation`/`ToolOutput` rather than a second arbitrary JSON RPC.

**Bounded worker decision:** for an inert, trusted arithmetic adapter, prefer an in-process verified Rust wrapper or carefully scoped trusted Python worker **only in a local development harness**. A new OS worker is mandatory before enabling untrusted third-party Python code, file access, networking or arbitrary code.

**Rollback:** feature flag not advertised; disabling the CE must block new admissions, retain canonical user data, and report unavailable to Lu; any already admitted call follows reviewed termination/cancellation rules. Never silently activate research challengers.

## 6. Acceptance fixture checklist for P1/P2/P3

- **Registry and model boundary:** installed-but-disabled absent from schemas; explicit enablement & tested removal; unknown tool/name/version/type fail; tool count ceiling; duplicate native/public IDs; no workspace-as-CE shortcut; in-flight remove under load.
- **JSON→Proto strictness:** malformed JSON, invalid UTF-8, unknown keys, deeply nested values, JSON null vs absent, empty vs unset, boolean false and integer zero presence, oversized input; protobuf wrong type URL, malformed bytes, output mismatch, future/reserved fields, forward-version refusal.
- **Host authority:** malicious prompt or retrieved “grant permission” does not grant; cross-thread/profile spoof fails; forged resource ID unavailable; denial occurs before worker spawn; no writable/network effect under read-only descriptor; no privilege escalation.
- **Runtime:** known rational controls, division by zero, excessive exponent, bounds, worker crash/timeout/cancel/orphan; evidence/assurance status maps correctly; empty/disabled plugin gives no invented result.
- **Model independence:** at least one actually loaded local transformer and a second compatible model or simulated tool-unavailable adapter; same authorized reference tasks, fallback behavior, argument failure rate, tool-selection quality and end-task fidelity.
- **Comparison:** current Lu native no-Cognitum path, standard conventional arithmetic tool, Cognitum exact calculator, integration overhead; hold model/version/settings/hardware fixed where comparable. Measure per-turn invocation/worker overhead and peak RAM; core control plane runs on CPU unless measurements justify otherwise.

**P0 exit condition:** approve G01–G04 contracts (and C02 authority boundary for any effects), settle host branch/CE API, freeze representative acceptance suite and explicit model end-to-end metrics. Only then undertake an executable bridge. The existing Python C01 prototype and test artifacts are preserved, not rewritten.

## 7. Public reference standards checked for this audit

- [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12): compatible schema vocabulary for strict model JSON arguments; schema generation is not host authorization.
- [Protobuf field presence](https://protobuf.dev/programming-guides/field_presence/): `optional` semantics and oneofs must survive JSON conversion.
- [Protobuf proto3 guide](https://protobuf.dev/programming-guides/proto3/): field reservations, evolution and wire compatibility.
- [Python `jsonschema` validation](https://python-jsonschema.readthedocs.io/en/stable/validate/): candidate for richer standalone Python shapes, **not** evidence it belongs in Lu's native hot path.

**Audit provenance:** Lu branch `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df`, source files and tests read through authenticated GitHub connection. No live Lu/Cognitum benchmark or executable integration was performed in this audit.
