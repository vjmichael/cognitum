# Lu Windows Alpha vs. Cognitum C14 G25 — Compatibility Review

**Date:** November 1, 2026  
**Decision:** **INTEGRATION HOLD — NOT VERIFIED**  
**Scope:** Static source and published local-build evidence review only. This does **not** claim execution of the current Lu Windows alpha on an installed Windows machine. No changes to Lu or Cognitum production code.

## Provenance: these are not interchangeable builds

- **Current upstream Windows source candidate:** `vjmichael/jan_alt`, draft [PR #106](https://github.com/vjmichael/jan_alt/pull/106), head `48d78669333131e343ab05eba6cb1e8d088a5f34`, branch `work/lu-mmproj-native-pairing-20261101`, with PR #105 Vulkan/UI and PR #104 native GGUF import changes underneath. Source-only draft, not an installed/accepted alpha.
- **Latest verified local Windows build evidence:** `R5_WINDOWS_BUILD_REPORT.md`, sourced from older commit `68eab79e2799c02cec8949993cebd64215f00559` plus R3/R4 overlay—not an R5 build of PR #106. It cross-compiled Lu Core for Windows, linked a PE smoke executable, and created an NSIS **toolchain-smoke** installer. It did **not** build the full latest Tauri desktop, include a verified pinned Vulkan llama-server, or verify real GPU/MMProj inference.
- **Linux-derived generic DLC work:** draft [PR #97](https://github.com/vjmichael/jan_alt/pull/97), head `f16ffe3584dc332ed927c46acdeca33462539ee0`. Commit comparison confirms it is an ancestor of PR #106 (which is 89 commits ahead). Some *source design* converged, but source ancestry is not an installed operational contract.
- **Cognitum acceptance evidence:** isolated Cognitum `research/c14_g25_nonprod` JSONL host and Cognitum's Python `Registry`/`Runtime`/`Worker` route, 980 independent black-box exchanges and eight Cognitum-native scenarios. This never exercised Lu's installed Windows native dispatcher, Windows signed external CE runtime, or Lu's typed IPC.

## Concrete contract mismatches

| Boundary | Cognitum C14 G25 research integration | Actual PR #106 Lu Windows alpha source | Compatibility finding |
|---|---|---|---|
| Registration | Python `cognitum.contracts.Manifest`, research plugin, `allow_research` and a `COGNITUM_G25_RESEARCH_OPT_IN=1` environment switch | Rust `ModuleManifest` + `NativeToolRegistry` + trusted CE enrollment, per-turn host policy | **Not equivalent.** An environment flag is not a Lu grant or registration. |
| Protocol | Local subprocess JSON Lines, `request_json` up to 131,072 characters; nested `host_status` and refusal metadata | Lu native Protobuf envelopes, `CeToolSchema` accepts only generated `CeReadRequest/Result`, `CeWriteRequest/Result`, or `CeExecuteRequest/Result`. Execute args: max 16, each <=1,024 characters. Reviewed host route: one <=4,096-char argument. | **Hard schema mismatch.** A dedicated, host-reviewed typed G25 message contract and size policy are necessary. |
| Default route | Research-only capability, deliberately not in production Cognitum CLI | `capability_router.rs` declares `BUILTIN_DLC_ROUTES = &[]`. Desktop `lu_inference_native_turn` passes `None` for route candidate and `new_read_only`, with only first-party read tools authorized. | **Not reachable in default Lu.** Do not auto-announce or advertise Cognitum. |
| Worker identity | Trusted local Python spawned process; Linux timeout cleanup tested; no external signed CE envelope | Content-addressed signed worker, durable per-profile/scope grants, OS sandbox and broker. `SignedCeRuntime::start` explicitly returns `NoSandbox` on non-Linux targets. | **Windows external CE blocked by design.** Do not use an unsandboxed Python fallback. |
| Transport | JSONL through stdin/stdout process; older separate Linux dev explored AF_UNIX | Lu signed Linux CE runtime uses framed Protobuf over worker stdin/stdout with a host resource broker. AF_UNIX support in other branches is not proof of current Lu Windows CE support. | **Transport mismatch.** Define one canonical Lu CE protocol, with OS-specific supervised launch. |
| Authority | Cognitum `HostContext` / plugin `allow_research`, empty declared effects | Lu binds authenticated persisted current USER turn, conversation/task/scope, exact ToolEffect, schema, approval and durable effect journal. Launching an external Python calculation is not made harmless by declaring empty effects. | **Authorization mismatch.** Require Lu host-constructed grant; no model/worker self-authorization. |
| Cancellation | Python `multiprocessing` timeout cleanup on Linux; no Windows process-tree containment accepted | Lu native inference has its own cancellation; optional CE runtime on Linux supports revocation/cancel; Windows arbitrary signed CE launch is disabled. | **Not accepted** for Windows CE cancellation/kill descendants/revoke/restart. |
| Result semantics | `execution_status=completed` may enclose `host_status=refused`, with no intervals | Lu tool result and audit pipeline must preserve conditional/unverified/refused science status; never count a process success as causal admission. | **Requires explicit mapping**, particularly after model continuation and journal replay. |
| Package | Local Python research package, no default registration | Vanilla Lu must ship without Cognitum, and install DLC only after identity, signature and per-scope permission validation | **Keep separate**; no Lu Core bundling of Cognitum. |

## Direct upstream source findings

1. [SignedCeRuntime](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/ce_signed_runtime.rs) documents Linux-only signed native ELF execution; `start()` rejects non-Linux with `NoSandbox` around lines 193–205.
2. [Lu's CE schema validation](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/src-tauri/lu-core/src/ce_schema.rs) only accepts generated read/write/execute Protobuf types; it cannot decode the Cognitum Python `Manifest` or arbitrary 131 KiB `request_json` payload.
3. [Lu desktop native inference](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/src-tauri/src/core/lu_inference.rs) authorizes only `lu.files.read_text`, `lu.files.list_directory`, `lu.inspect.stat`, and `lu.inspect.search_text` for the current turn (around lines 1097–1128), then supplies no DLC candidate/rules around lines 1149–1156.
4. [Generic capability router](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/src-tauri/lu-core/src/capability_router.rs) deliberately has no built-in DLC routes and requires matching trusted current USER digest, host-selected rule, native tool, effect, typed codec and model-advertised schema.
5. [CE package manager](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/src-tauri/lu-core/src/ce_packages.rs) quarantines external archives; verified signed external workers cannot be enabled through `enable_bundled_trusted` (`SignedWorkerRequired`).
6. [Lu alpha replacement decision](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/docs/lu/ALPHA_NATIVE_REPLACEMENT_DECISION_20261101.md) explicitly says native MMProj binding is a source draft, not image-chat acceptance; it requires independent Windows GGUF/MMProj/Vulkan installed verification before release.
7. [Generic CE containment review](https://github.com/vjmichael/jan_alt/blob/work/lu-mmproj-native-pairing-20261101/docs/lu/dlc-generic-interface-containment-gate-2026-10-31.md) accepts signed generic Linux Bubblewrap fixture evidence but says arbitrary signed external DLC Windows execution is **not supported**.

## Safe path to compatibility and acceptance

**Gate 0 — pin actual installed Lu target.** Obtain a complete runnable Windows alpha build/NSIS whose manifest SHA matches exact reviewed source. Reconcile local R5 modifications with PR #106 before tests. Inventory actual Tauri commands, core/proto versions, engine, worker launcher and signer. Build toolchain smoke NSIS is not qualifying.

**Gate 1 — typed CE contract, reviewed independently.** Define `G25SensitivityRequest` and `G25SensitivityReport` Protobuf (or a separately reviewed canonical typed operation), including counts, Gamma, bounded assumptions, explicit statuses, unverified/no-admission flags and no interval on refusal. Negotiate protocol version/feature; reject unknown fields, oversized data, duplicate effects, ambiguous operations. Design for aggregate counts instead of shipping private raw observations.

**Gate 2 — external CE runtime and OS containment.** Build separately signed, content-addressed Linux ELF and Windows PE workers from one reviewed Cognitum release contract. Windows must have actual restricted worker identity, Job Object/process-tree termination, broker-only resources, default-deny network and no home/credential access. Lu Windows does not implement this for arbitrary signed DLC yet; until then do not claim integration. No Python-global/unsafe fallback, no Docker, no MCP prerequisite.

**Gate 3 — explicit Lu-owned enrollment and authorization.** User-controlled install/enable, publisher-signature acceptance, durable grant, verified current user turn, per-call effect/scope/args validation, and no-tool preference. The model cannot mint permissions. Do not embed Cognitum-specific routing into Lu core.

**Gate 4 — scientific-result integrity.** Map `completed` process vs nested `refused`/`conditional`, preserve interval omission on refusal, bounds and assumptions, trace/audit source hashes, and no causal certification. Tests must confirm that prompts or malicious worker output cannot reframe the result as verified causation.

**Gate 5 — independent same-build OS E2E.** On *the same exact Lu source/CE contract*, run real installed Linux and Windows tests: discover disabled by default, approve once, valid report, missing-arm/sparse/missing-assumptions refusal, schema mismatch, revocation, timeout, cancellation before/after effect, child-process cleanup, crash/restart, upgrade/rollback, and trace inspection. Windows must use installed Lu alpha, not a Cognitum-only Python subprocess. Separately qualify Lu's native GGUF/model/Vulkan alpha gates; no Cognitum requirement for vanilla Lu startup.

## Decision

- **Cognitum isolated nonproduction integration:** PASS for its own research interface and independent tests.
- **Lu generic extension design:** SOURCE PRESENT, different runtime semantics and OS limitations.
- **Lu Windows alpha <-> Cognitum CE installed compatibility:** **UNVERIFIED / BLOCKED**.
- **Lu Windows signed arbitrary DLC launch:** **UNSUPPORTED in reviewed source**.
- **Lu alpha installed GGUF/MMProj/Vulkan qualification:** **OPEN**.
- **Cognitum production estimator promotion:** **NOT AUTHORIZED**.

This is a compatibility hold, not a request to modify the existing Lu alpha feature scope. Keep Cognitum separate and schedule actual Lu integration only after the host extension gates can enforce the same contract on each OS.