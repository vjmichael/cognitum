# Lu DLC Core Extension Integration Addendum Register

**Established:** 2026-10-26  
**Status:** Cognitum-owned proposals for the separate Lu team; **not approvals or implementation work in Lu**  
**Owner of this register:** Cognitum development  
**Lu authority:** Separate Lu development task/repository; **Lu code, GitHub branches, configuration, desktop AppData, installer and architecture documents are read-only from this project**.

## Boundary and terminology

**Cognitum is developed and tested independently as an optional, separately installable and distributable Lu-native DLC Core Extension (CE).** A **CE** provides reusable capabilities/tools to the Lu host and its loaded transformer; it is not an MCP server, a mandatory Lu base-core feature, a replacement model/agent loop, or a DLC Workspace. A **DLC Workspace** is a specialized, full application environment/UI (e.g. IDE or Film Studio) that can consume CEs and Lu services. Vanilla Lu remains available. Cognitum components (C01–C19) may be enabled independently within a CE distribution, subject to Lu authority; they are not nineteen automatically advertised model tools.

**Project rule:** We may inspect Lu to discover compatibility issues. We **never edit, commit, push, build, install, clean, reset, or otherwise modify Lu** from Cognitum work. Every requested Lu change goes here as a scoped addendum with status **proposed** until the independent Lu effort explicitly accepts it. The separate Lu effort owns architecture choice, implementation and release gates. Changes made only in Cognitum are tracked as Cognitum work, not Lu addenda.

**Loaded transformer rule:** Lu controls provider/model selection, agent orchestration, tools, permissions, sessions and user-facing results. Cognitum exposes strictly bounded, evidence-bearing operations through approved Lu-native CE contracts. Improvement is assessed on Lu + selected transformer vs Lu alone and Lu + competent standard tools; no claim of changes to model weights.

## Source-of-truth snapshot

- Host reference checked: `vjmichael/jan_alt` branch `lu/core-contracts-native-registry`, commit `11b2e7e8c5370d512a8f8815d5aaaf9e682e04df` (2026-10-26). This is a **point-in-time inspection**, not a claim about the current unpushed Work task or future Lu design.
- Lu has experimental `lu-core` Rust `NativeToolRegistry`, `ModuleManifest`, Protobuf `ToolCall`/`ToolReply`, `ModelToolCatalog`, `ModelToolCodec`, `ToolAuthorizer`, and a feature-gated, two-tool desktop adapter. Some APIs are **experimental or not yet fully integrated**; do not present the feature branch as a production CE SDK.
- See [pinned Lu-native audit](components/core-runtime/P0-lu-native-audit.md), [host collaboration contract](lu-cognitum-integration.md), [C02 security research](components/security/P0-research.md) and [build order](build-order.md).

## Proposed Lu addenda (not Lu commitments)

| ID | Lu change or design question to raise | Why Cognitum needs it | Safety / acceptance gate | Status |
|---|---|---|---|---|
| **LU-CE-001** | Explicit optional **Core Extension** module kind and distribution/lifecycle contract, distinct from both permanent Core and full Workspace | Lu current `ModuleKind` has only `Core` and `Workspace`; Cognitum must be installable, disabled/unloaded/upgraded without claiming core ownership | Host-signed/verified install intent, default-off when appropriate, manifest/dependency versioning, enable/disable/unload and restart behavior, fail-closed model visibility, in-flight call admission/cancel rules | **Proposed** |
| **LU-CE-002** | Typed operation effects with **all** real effects and exact resource scopes (or split operations) | Cognitum `Operation.effects` can contain several scoped effects; Lu descriptor currently advertises one `ToolEffect`. Lossy mapping could misrepresent read+write or network behavior | Host remains sole authorizer; negative tests for mismatched declarations, multi-effect operations, scope escalation and arguments; OS enforcement independently verified | **Proposed** |
| **LU-CE-003** | Stable native CE schema/version compatibility profile (Protobuf type URLs, generated message fields, package/manifest version and host ABI) | Lu `CORE_CONTRACT_VERSION=1` differs from Cognitum semantic `1.3.0`; blindly equating them is invalid | Explicit version domains, independent migration plan, reserved Proto fields, optional presence, breaking-change checks and strict JSON→Proto→domain round-trips | **Proposed** |
| **LU-CE-004** | Host-controlled, workspace/session-aware **dynamic CE capability catalog** and model-tool codec registration | Existing desktop Lu native tool adapter exposes two fixed file tools; Cognitive capabilities need on-demand allow-listed discovery without advertising 19 tools to every transformer | No model-supplied registration, explicit grants and health/availability, schema/tool limits and per-model compatibility; disabled/unknown CEs never advertised or dispatched | **Proposed** |
| **LU-CE-005** | Trusted host session/profile ownership binding available to native CEs | Raw webview/thread IDs are not credentials. HDC retrieved matches must not grant cross-project memory access | Trusted Tauri window+session enrollment, exact owner/project/sensitivity authorization, read/export/train separation, revocation, test with multiple profiles and junctions | **Proposed** |
| **LU-CE-006** | OS-confined **optional CE compute worker** service/broker with cancellation/quotas | Python spawn is not a sandbox; advanced HDC/KAN and future libraries must not inherit unrestricted disk, network, secrets, devices or elevated token | Windows AppContainer/LPAC or restricted worker with Job Object controls tested under actual Windows accounts; Linux/macOS analogues; bounded typed IPC, deny network by default, no Python pickle from untrusted workers | **Proposed** |
| **LU-CE-007** | Shared typed execution result/status and provenance envelopes, preserving exact vs approximate vs unsupported | Selected transformer must distinguish solver exactness, KAN estimate, HDC retrieved candidate, failure, timeout, and rejected formalization | Validate output bytes+semantics, include operation version/source revision/evidence/assumptions/limitations and redacted trace ID, no fabricated success | **Proposed** |
| **LU-CE-008** | Canonical memory/state ownership and read-only derived-index invalidation hooks | Lu's ANSF SQLite conversation memory and ownership records should not be duplicated as competing truth; HDC/embedding indexes are derived | Provenance-aware read/write and delete/retract/supersede events, ownership and migration authority, consistent indexing under revocation; no data silently sent to training/cloud | **Proposed** |
| **LU-CE-009** | Bounded host-coordinated multi-CE invocation with typed dependency/cost/cancellation semantics | One transformer task may combine HDC retrieval, exact calculator, optimization, verification and simulation | Lu remains orchestrator; declared call budgets and effects, explicit failure compensation/abstention, no hidden plugin-to-plugin permission escalation | **Proposed** |
| **LU-CE-010** | Independent component and end-to-end **model benchmark handoff contract** | Need to measure whether Cognitum genuinely helps Lu with a selected local/cloud transformer | Pinned model/provider/quantization/parameters, standard-tool controls, latency/memory/VRAM/cost, held-out tasks and honest negative findings; do not infer production gains from K4 self-tests | **Proposed** |

**Dependencies to communicate in order:** 001 + 003 define package/ABI identity; 002 + 005 + 006 constrain authority; 004 + 007 permit truthful model-visible operations; 008 + 009 enable advanced composition. 010 allows performance claims. Some can be designed in parallel.

## Cognitum-only implementation path (no Lu edits)

1. Complete C01 trusted standalone runtime hardening and targeted tests. Preserve existing contracts, calculator, synthetic replay and recorded prior results.
2. Define `CognitumCapabilityManifest`/schema fixtures **inside Cognitum** only, including optional CE identity and operation mapping, without pretending these are Lu's final production SDK.
3. Implement a deterministic inert calculator test adapter behind an **internal, default-off fixture** once a stable native CE ABI is agreed with Lu team. Do not register it in Lu or present it as installed.
4. Continue C02 risk analysis, C03 test harness and C08/C09 recovered source integration based on canonical memory and authority constraints. Do not modify archived originals.
5. When Lu separately adopts any addendum, record Lu link/commit/contract version and write corresponding **Cognitum-side compatibility tests**, then reclassify status as accepted/implemented/verified only with direct evidence.

## Cognitum-side implementation evidence (does NOT change Lu statuses)

**2026-10-26 — C01 prototype (merged to Cognitum `main`):** [PR #2: standalone disabled DLC CE manifest compatibility fixture](https://github.com/vjmichael/cognitum/pull/2) adds `cognitum/ce_manifest.py`, a frozen JSON fixture and strict tests. [CI run 40444530509](https://github.com/vjmichael/cognitum/actions/runs/40444530509) passed **42/42 unit tests plus 12/12 synthetic replay cases** for each of Linux/Windows and Python 3.11/3.13. The fixture is *not installable*, *not advertised* and *not bound* to Lu. It currently **rejects effectful operations**, because LU-CE-001 (lifecycle), LU-CE-002 (effects), LU-CE-003 (typed ABI) and LU-CE-004 (catalog) have **not been adopted by Lu**. The proposed type URLs are placeholders for future generated contracts, not compiled Protobuf.

**Independent C01 hardening (also merged to Cognitum `main`):** [PR #1: fail-closed trace field/status metadata](https://github.com/vjmichael/cognitum/pull/1) passed [four-platform CI](https://github.com/vjmichael/cognitum/actions/runs/40444297105) with **40/40 unit tests plus 12/12 synthetic replay cases** per job. This is Cognitum-only source improvement; no Lu integration code was written.

**Combined main verification:** [GitHub Actions run 40444933715](https://github.com/vjmichael/cognitum/actions/runs/40444933715) on the merged code passed **51/51 tests and 12/12 synthetic replay cases per job** across Windows/Linux, Python 3.11 and 3.13. The two prior PR-specific CI results remain as separately attributable evidence. **All LU-CE addenda remain Proposed**, regardless of this Cognitum-side progress.

## LU-CE-007: typed result translation proposal (Cognitum implementation underway)

[Cognitum typed capability result v1 — source and contract proposal](https://github.com/vjmichael/cognitum/blob/cognitum/c01-typed-results-v1/docs/components/core-runtime/P1-P2-typed-results.md) and [PR #3](https://github.com/vjmichael/cognitum/pull/3) define an **opt-in Cognitum Python result contract** covering canonical exact rational, explicitly uncertain decimal estimate, snapshot-matched retrieval references, dry-run-only, and sanitized failure categories. Fixed epistemic limitations distinguish **exact formal computation** from **verified user intent**, and candidate references from authority or source truth. This is **not** the adopted Lu Protobuf ABI.

**Read-only host finding:** Lu currently uses `lu.v1.ToolReply.oneof outcome` (either `output` typed bytes or `failure` `ToolError`), and validates model-visible JSON through its `ModelToolCodec`. Proposed translation for Lu team:
1. `completed` with a validated domain value → **dedicated generated Protobuf output**; preserve value kind, evidence reference, limitations and assurance derived by Lu-reviewed codec.
2. `denied` / `invalid_input` / `unavailable` / `timed_out` / `error` → Lu's **native failure arm**, with sanitized `code` and reviewed `retryable` flag; never wrap a failed execution as successful `output`.
3. `validated` (dry run) → host-approved representation explicitly conveying that no execution occurred; not an ordinary exact/approximate success.
4. **Unknown status, outcome schema, evidence/limitation code or newer major version → reject**, never silently coerce to “ok” or parse from a generic JSON blob.
5. Lu must continue to derive authenticated subject/workspace scopes from its trusted host, not Cognitum's candidate IDs or model-generated metadata.

The Lu team determines the final `.proto` package, `optional` presence semantics, ABI version policy, status-to-transport mapping and model-visible codec. This proposal **does not request replacing Lu's host core or editing `lu.v1.ToolReply` when its existing typed-oneof design suffices**. Status remains **Proposed** pending separate Lu authority and compatibility tests.

## Ownership and update protocol

Each entry may gain: **source branch + verified commit**, proposed host interface, rationale, acceptance criteria, Lu decision reference, implementation link, Cognitum compatibility test, superseding entry and date. Do not silently change **Proposed** to **Accepted**. If Lu's independent implementation differs, reconcile Cognitum adapter requirements here first.

**No Lu modification permission is granted or exercised by maintaining this register.**
