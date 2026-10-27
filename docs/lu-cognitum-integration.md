# Cognitum × Lu — Transformer-Centered Collaboration Contract

**Decision date:** 2026-10-26  
**Status:** User-confirmed architectural requirement; **design contract**, not an implemented integration  
**Applies to:** All Cognitum C01–C19 components, C04 Lu integration, Lu-native Core Extensions (CEs) and DLC Workspaces  
**Related:** [Ordered build path](build-order.md) · [Per-component P0–P3 process](roadmap.md) · [C01/P0 source audit](components/core-runtime/P0-research.md)

## 1. Architectural objective and authority

> **Cognitum's purpose is to measurably augment whichever compatible LLM transformer is selected/loaded in Lu. Lu's implemented model lifecycle, agent orchestration, tool discovery/dispatch, permission controls, session/workspace behavior and native extension architecture determine how Cognitum capabilities collaborate with that transformer and with each other.**

**Lu is the host and integration authority.** The currently selected model handles natural language, user dialogue, problem interpretation and synthesis. Cognitum is a collection of optional, bounded computational and cognitive capabilities—some exact, some statistical or experimental—that the host may invoke when relevant. The capabilities are not a rival chat host or a hardcoded substitute model.

This is **inference-time capability augmentation**, not a claim to change the transformer's weights, automatically retrain it, increase its intrinsic intelligence or guarantee superior answers. If a separate learning/fine-tuning feature is proposed, it requires its own explicit design, consent and research track.

### Boundaries and responsibilities

| Concern | Owner of authority / work |
|---|---|
| Model/provider selection, loading/unloading, local/cloud connections, model-context management | **Lu**; no Cognitum-imposed transformer, provider or model family |
| User dialogue, intent interpretation, tool proposals, natural-language output/synthesis | **Selected transformer via Lu**, with Lu-compatible adapters and verification/confirmation for consequential formalization |
| Capability discovery, presentation to models, tool dispatch and multi-step execution control | **Lu's current native interfaces** and its approved CE/service/Workspace integration; Cognitum advertises versioned available operations and can execute bounded component-local plans only when invoked by the host |
| Authentication, workspace grants, approval, prompt-injection defense, isolation, cancellation, resource/energy budgets | **Lu host** enforces authority, with Cognitum performing defense-in-depth input validation and capability policy; no authority from model payloads or retrieved text |
| Component implementation, domain computation, provider validation and specialized results | **Cognitum native component/adapters**, including HDC, KAN, state, memory, solver, spatial and simulation implementations |
| Canonical user/project memory and mutable state ownership | **One explicitly agreed storage owner and permission/migration contract** between Lu and Cognitum; no parallel conflicting truths; derived HDC/embedding indexes are never canonical stores |
| Component benchmarking, limitations, promotion decisions | **Cognitum P0–P3 process** with actual Lu+selected-model end-to-end baseline tests and host security gates |
| User-facing limitations, evidence, final contextualized response | **Lu and loaded transformer**, faithfully reflecting Cognitum execution/status/evidence; exact computation alone never validates an incorrectly formalized user problem |

Lu's GUI remains customizable and available even when DLC Workspaces are installed. Specialized Workspaces use shared native capabilities rather than spawning an unrelated Cognitum AI platform. Whether a capability is exposed to vanilla Lu, an IDE Workspace or the Film Studio Workspace is a host policy/UI decision.

## 2. Normative request/result lifecycle

```text
User → Lu session / selected transformer (local or provider-backed)
     → Lu decides/proposes eligible operations with current context
     → Lu validates workspace, authority, grants, model capability, budget
     → Lu-native CE/tool bridge calls Cognitum's typed operation contract
     → Cognitum chooses nominated enabled provider for requested operation
     → Cognitum validates typed input and policy; executes in appropriate boundary
     → Cognitum validates result, distinguishes status/outcome/assurance/evidence
     → Lu receives structured result, timestamps, provenance and limitations
     → Selected transformer interprets and synthesizes answer, Lu enforces display policy
     → User receives answer with honest computed/estimated/unknown distinctions
```

Cognitum should **not** invent a second model loop, arbitrary universal task router, duplicate tool API, hidden model switch, or universal vector coordinate system. Lu decides when/how to expose operations and how to compose calls. Cognitum's local registry still chooses the explicitly nominated enabled provider **within** an approved capability slot; this is subordinate to Lu's overall orchestration. If a model cannot reliably produce tool arguments or lacks native function calling, Lu's model adapter must either provide a tested constrained/structured mediation path, rely on explicit user-triggered operations, or declare capability unavailable. **Never rely on unvalidated JSON repair or hallucinated tool results as a guarantee.**

A multi-component task is a **Lu-controlled typed plan**: each step declares inputs, outputs, dependencies, authority, runtime/memory budget and failure paths. A plugin must not secretly call other plugins, acquire broader permissions or overwrite canonical data. Component-local composition may be used only when its declared contract and authority make it auditable.

## 3. Cross-component collaboration examples (design targets, not implemented claims)

| Lu + transformer task | Cognitum capability handoff | Expected truthful result |
|---|---|---|
| “What did we decide, and what changed?” | Lu retrieves canonical memory + typed state; optionally invokes HDC derived relational index | Provenance, temporal revision/supersession and uncertainty; deleted claims excluded |
| “Compute this exactly” | Lu sends a formalized, bounded expression to exact calculator/solver; KAN only for fit/surrogate tasks where appropriate | Exact or qualified numeric value; no KAN-as-exact-math claim |
| “Plan this constrained sequence” | Lu composes plan/search and optimization/verification calls with dependency and budget limits | Feasible plan, proof/gap if supported, unresolved constraints and limitations |
| “Explain cause versus correlation” | Lu calls probability/causal adapters only when identification assumptions and relevant data exist | Assumptions, model outputs and disclosure; no fabricated causal inference |
| “Maintain object continuity in a film scene” | Lu Studio Workspace uses typed scene/object state, spatial tracking, optional physics simulation and derived indexes | Stable object identifiers, tested state updates and bounded simulation outputs |
| “Summarize a running simulation” | Lu selects relevant numerical simulator or KAN surrogate only under workload-specific validated envelope | Units, fidelity/uncertainty, OOD detection, fallback to solver if necessary |

**Research reuse:** HDC K4 integrated research and default-off KAN depth extension are now **located, hash-verified and independently CPU-unit-tested** ([archive audit](components/hdc-kan/P0-archive-reuse-audit.md)); Cognitum/Lu typed contract, permission and end-to-end improvement tests are still required. They are **not** blockers for defining the Lu-host integration contract, and are not to be rebuilt without a demonstrated gap.

## 4. Model independence and capability negotiation

- **No hardcoding to one transformer family, parameter count, quantization or accelerator.** Lu may select different compatible local/cloud models. The actual host model determines tool calling, context limits, structured-output fidelity and operational constraints.
- Lu advertises **only enabled, healthy, permitted operations**, with compact model-appropriate schemas. Do not infer that a model supports all tools based on the presence of an API field.
- Capability negotiation must distinguish unavailable, disabled, denied, timeout, failed, approximate, and verified operation results. The final LLM answer must not mask any failure as success.
- When the selected model/provider changes between sessions or turns, Lu keeps application-owned canonical data and checks capability compatibility. Cognitum does not need to migrate the user's permanent memory into the transformer's weights.
- Plugin selection is bounded by hardware/runtime availability (CPU, AMD GPU, FPGA, others), resource budgets, authorization and current model/tool support. **Hardware optimization is chosen per component**, not imposed by the selected transformer.
- Any learned routing scorer is an optional, separately benchmarked helper; deterministic Lu policy and explicit disables always win.

## 5. Serialization and trust contract

**Design direction already selected for Lu:** Protobuf for reliable internal typed messages, with JSON still accepted at model/API boundaries. This does **not** imply protobuf support is already merged in Cognitum or the active Lu main branch.

P0/C04 must identify the actual host bridge and bind schemas to immutable version identifiers; explicitly document `optional`/presence for unset vs zero/false, reserved retired field numbers, schema evolution/breaking checks and typed JSON↔Protobuf conversion failures. Typed arguments must not silently become unvalidated `Struct` payloads. A rejected/malformed model argument must yield a clean structured error without continuing a partially parsed request.

Security invariants: model text/retrieval is untrusted; `HostContext` is built only by Lu's trusted host. Do not supply resource grants through model output. Untrusted/effectful code requires an OS-enforced C02 worker boundary. Never treat Python multiprocessing isolation alone as sufficient. Restrict trace payload retention and propagate cancellation/scope rules from Lu.

## 6. P0–P3 evidence must measure the *loaded LLM's* improvement

**Each component's P0 design must now define two result levels**: (1) component-alone correctness/performance, and (2) **end-to-end Lu+selected-transformer task improvement**. A fast or accurate HDC/KAN/solver benchmark does not automatically prove improved user answers.

Minimum evaluations where applicable:
- **A — Lu + selected transformer alone** with the same task/context and no new Cognitum capability.
- **B — Lu + selected transformer + competent standard/conventional tool** for the same function.
- **C — Lu + selected transformer + candidate Cognitum component** (including recovered HDC/KAN where relevant).
- **D — Lu + selected transformer + bounded relevant component combination**, with controlled ablations (host-only, each single component, conventional composition, proposed composite).

Match model/provider/version/quantization, model settings, sampling/seeds where possible, prompts/context, dataset/held-out split, permissions, hardware budgets and timing windows. Run task types representative of Lu's real workflows, and record tool selection success/denial, formalization errors, answer accuracy, inconsistency/hallucination rates, latency, CPU/GPU/VRAM/RAM/energy, conversion cost and failure recovery. State any test not practical for a given component explicitly.

**Promotion criterion:** measurable benefit and no critical security/privacy/reliability regression relative to competent controls, plus approval under the main roadmap. Negative results remain valid scientific evidence but do **not** justify default-on deployment.

## Active Lu feature-branch finding (2026-10-26)

**Updated authoritative host reference:** [C01 pinned Lu native feature-branch audit](components/core-runtime/P0-lu-native-audit.md), anchored at `lu/core-contracts-native-registry` commit `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df`. This branch already has native `NativeToolRegistry`, typed Protobuf tools, a strict `ModelToolCatalog`/codec bridge, a feature-gated Tauri integration and an experimental Jan-native legacy bridge. Current gaps: optional Core Extension module kind (Core/Workspace alone), effect-set/scoped permission translation, `1.3.0` component versus `1` host contract versioning, and host authorization/worker isolation. **Earlier `main` findings below are historical, not the target API.**

## 7. Existing source anchor points, inspected 2026-10-26

**Lu repository `vjmichael/jan_alt` `main`:**
- [`web-app/src/lib/coworkTransport.ts`](https://github.com/vjmichael/jan_alt/blob/main/web-app/src/lib/coworkTransport.ts) — records chosen model/provider per run, inherits host model lifecycle.
- [`web-app/src/lib/coworkRunner.ts`](https://github.com/vjmichael/jan_alt/blob/main/web-app/src/lib/coworkRunner.ts) — agent loop and tool result flow.
- [`web-app/src/lib/coworkDispatch.ts`](https://github.com/vjmichael/jan_alt/blob/main/web-app/src/lib/coworkDispatch.ts) — native dispatcher, plan/web policy and tool execution.
- [`web-app/src/lib/agentTools.ts`](https://github.com/vjmichael/jan_alt/blob/main/web-app/src/lib/agentTools.ts) — advertised native tool sets and sandbox-dependent `shell` advertisement.
- [`src-tauri/plugins/tauri-plugin-agent-tools/src/tools/schema.rs`](https://github.com/vjmichael/jan_alt/blob/main/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/schema.rs) — model-visible tool schema definitions.

**Cognitum repository:** [`cognitum/runtime.py`](../cognitum/runtime.py), [`cognitum/contracts.py`](../cognitum/contracts.py), [`docs/architecture.md`](architecture.md).

These anchors demonstrate **existing host entry points**, not an already working Cognitum↔Lu integration. Current branch-specific Lu CE contracts remain to be confirmed, especially if recent work has not landed on `main`.

## 8. Impact on component build order

**The C01–C19 priority order is retained**, but this contract governs them all. C01's P0 must define host-controlled invocation and typed contracts. C02 verifies the authority boundary; C03 must capture Lu+loaded-model baselines; C04 implements the native bridge. **For C05 onward, P0 must explicitly ask “How does this capability change the selected transformer's ability to complete a concrete Lu task?”** and P3 must test that answer. Independent library/backend microbenchmarks remain necessary but insufficient.

**Current status:** architectural decision recorded; documentation only. No model weights, runtime, Lu source, Cognitum source, tool registry, benchmark or archived HDC/KAN implementation changed by this decision.
