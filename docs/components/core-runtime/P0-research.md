# C01 / P0 — Core contracts, capability registry, policy and runtime

**Status:** **IN PROGRESS — initial research and source audit completed; P0 exit not yet approved**  
**Started:** 2026-10-26  
**Component:** C01 (build order #1)  
**Next phase:** P1 targeted adaptation of existing code, **not a rewrite**  
**Links:** [Build order](../../build-order.md) · [Universal lifecycle](../../roadmap.md) · [Architecture](../../architecture.md)

## 1. Purpose, architecture boundary and working hypothesis

C01 is the small trustworthy capability-dispatch layer that permits Cognitum to add and remove optional services without misrepresenting capability, safety, provenance or assurance.

It must (a) validate versioned operation contracts and bounded inputs/outputs, (b) maintain an explicit enabled-provider/champion registry, (c) accept **trusted host context** independently of model-generated requests, (d) enforce policy and safe failure behavior, (e) record correlation and outcome metadata, and (f) integrate with **Lu's native tool infrastructure**, not invent an alternate Lu agent loop, mandatory MCP server or untrusted plugin loader.

**Hypothesis:** preserve the existing standard-library prototype where adequate, add a maintained schema validator and a small typed host adapter where required. Complexity must pay for itself in correctness/compatibility. C02 owns OS isolation, C03 owns full evaluation, and C04 owns Lu integration; C01 provides their contracts.

### User-confirmed host/model integration constraint (2026-10-26)

The C01 core must serve **whatever transformer is selected or loaded in Lu**, and its actual collaboration with Cognitum must follow **Lu's existing native model lifecycle, dispatch, tool registration, state, permission and workspace architecture**. The transformer interprets tasks and synthesizes results; Lu approves and orchestrates; Cognitum validates and executes typed capabilities, reporting status, evidence and limitations. No hidden independent model loop or permission grants from generated text.

See the binding [Lu × Cognitum collaboration design](../../lu-cognitum-integration.md). C01 P0 must incorporate model-agnostic schema advertisement and handoff semantics; its P3 must use selected-model end-to-end comparisons (Lu alone, Lu+conventional tools, Lu+Cognitum, and typed compositions where relevant). A model-specific tool-calling inability must be tested and honestly represented. The existing Python core is a prototype and does **not** yet establish this integration.

## 2. Existing source evidence (read on `main`, 2026-10-26)

| File | Observed implementation | Limitations / questions |
|---|---|---|
| [`cognitum/contracts.py`](../../../cognitum/contracts.py) | Frozen dataclasses for `Request`, `Response`, `Manifest`, `Operation`, `HostContext`, `Effect`; exact contract version `1.3.0`; schema digests; explicit status versus outcome versus assurance | `Shape` validates **only** closed objects of bounded nonempty strings; nested events, numbers, unions, optionals, lists, state records require richer typed schemas |
| [`cognitum/registry.py`](../../../cognitum/registry.py) | Trusted installation with `health`/`self_test`, explicit champion nomination, default-disabled providers, replacement under lock, research opt-in | No general dependency management, verified distribution discovery, hot-reimport, cancellation/draining or production rollback on later execution failure |
| [`cognitum/policy.py`](../../../cognitum/policy.py) | Exact identity/scope grant checks, replay protections, deterministic denial of effectful calls | Not a kernel/OS enforcement boundary. All declared effectful operations are rejected even with grants |
| [`cognitum/runtime.py`](../../../cognitum/runtime.py) | Ordered validate → resolve → validate payload → authorize → invoke → validate result → structured response/trace; no invented exact result on unavailable/error | No full natural-language formalization artifact, versioned host adapter or bounded composition; trace append failure propagates |
| [`cognitum/worker.py`](../../../cognitum/worker.py) | Per-call `multiprocessing` spawn, timeout cleanup and sanitized worker errors | **Not a sandbox**. Python `Pipe` transfers Python objects using serialization unsuitable for adversarial untrusted workers; no CPU/RAM/child containment or OS permission isolation |
| [`cognitum/tracing.py`](../../../cognitum/tracing.py) | Metadata-only in-memory and JSONL trace with request/correlation IDs and latency | No OpenTelemetry span interop, retention/rotation/redaction enforcement outside current metadata, cross-process tracing specification |
| [`cognitum/evaluation.py`](../../../cognitum/evaluation.py) | Deterministic, inert synthetic fixtures with registry/suite digests; no-promotion label | Engineering smoke only, not cross-architecture or end-user scientific P3 evidence |
| [`tests/test_core.py`](../../../tests/test_core.py) | Tests cover empty core, nomination, toggle/replacement, schema versions, grants/replay, timeout, traces, compatibility and replay | Existing repository handoff reports **31 passing tests + 12/12 synthetic cases**; those are **historical reports**, not tests rerun by this P0 audit |

**Verification provenance:** [`docs/status.md`](../../status.md), [`docs/verification.json`](../../verification.json), [`tests/manifest_v1.json`](../../../tests/manifest_v1.json). No runtime tests executed or existing implementation edited during this audit.

## 3. Lu-native host reuse audit (read on `vjmichael/jan_alt` `main`)

- [`web-app/src/lib/agentTools.ts`](https://github.com/vjmichael/jan_alt/blob/main/web-app/src/lib/agentTools.ts) already exposes built-in tool discovery and execution. The ordinary chat tool subset differs from the Cowork set; `shell` is withheld without an enforcing sandbox.
- [`web-app/src/lib/coworkDispatch.ts`](https://github.com/vjmichael/jan_alt/blob/main/web-app/src/lib/coworkDispatch.ts) dispatches Cowork tool calls, checks plan-mode/web restrictions and feeds operation outcomes back to the runner.
- [`src-tauri/plugins/tauri-plugin-agent-tools/src/tools/schema.rs`](https://github.com/vjmichael/jan_alt/blob/main/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/schema.rs) maintains the Rust-facing model tool JSON schemas and related tests.
- [`src-tauri/plugins/tauri-plugin-agent-tools/src/tools/mod.rs`](https://github.com/vjmichael/jan_alt/blob/main/src-tauri/plugins/tauri-plugin-agent-tools/src/tools/mod.rs) defines native built-ins and contextual sandbox/workspace controls; Lu already has tools and policy to integrate with.
- [Tauri permission definitions](https://github.com/vjmichael/jan_alt/blob/main/src-tauri/plugins/tauri-plugin-agent-tools/permissions/default.toml) exist. **Existence of policies ≠ demonstrated Cognitum security integration**.

**Integration direction:** expose Cognitum through **Lu-native CEs/capabilities** and the existing host-authorized tool registry/dispatcher. Treat internal Protobuf as the selected direction for Lu's internal messages, with JSON at model/API boundaries as needed. **No Cognitum Protobuf or Lu converter exists yet**; C01 does not claim one. A documented native IPC/serialization contract and exhaustive compatibility fixtures are a P0/C04 dependency. Do not duplicate Lu's installed tool mechanics or assume MCP is the internal plugin architecture.

## 4. External standards and library survey (initial, 2026-10-26)

The following sources are maintained specifications/reference docs; adoption is a **proposed engineering decision**, not a claimed installed dependency. Package versions, licenses and live maintenance advisories must be pinned/verified at implementation time.

| Standard or library | Official/reference resource | Suitability and present decision |
|---|---|---|
| JSON Schema Draft 2020-12 | https://json-schema.org/draft/2020-12 | **Choose as canonical schema dialect for JSON operation boundaries**; explicitly define `additionalProperties`, required/nullable/present fields and safe limits. Not the runtime authority for grants. |
| `python-jsonschema` (`Draft202012Validator`) | https://python-jsonschema.readthedocs.io/en/stable/validate/ | **Preferred P1 evaluation candidate** for validating generated JSON Schema; straightforward and mature. Trial rich nested types and hostile cases, benchmark overhead. |
| Pydantic v2 | https://docs.pydantic.dev/latest/concepts/json_schema/ | Alternative typed Python model + JSON Schema generation; evaluate against Python dataclasses and `python-jsonschema`. Avoid simultaneously owning two divergent schema definitions. **Not automatically selected**. |
| Protocol Buffers (proto3 presence/reserved tags) | https://protobuf.dev/programming-guides/field_presence/ and https://protobuf.dev/programming-guides/proto3/ | For chosen Lu internal typed message direction: preserve unset vs zero/false via presence; never reuse field numbers, reserve removed tags. **Conversion contract pending actual Lu boundary design**. |
| Buf breaking checks | https://buf.build/docs/breaking/ | **Recommended once .proto files exist**; detect breaking changes against pinned prior descriptors/refs. Not relevant to current Python-only starter. |
| Python packaging entry points | https://packaging.python.org/en/latest/specifications/entry-points/ | Standard discovery mechanism for **trusted, explicitly approved** Python distributions; metadata discovery is not code isolation or automatic execution approval. |
| `pluggy` | https://pluggy.readthedocs.io/en/latest/ | Established hook-based plugin manager. **Do not adopt yet**: Cognitum has a purpose-built explicit registry, so replacing it could increase complexity without evidence. |
| OpenTelemetry Python API and context propagation | https://opentelemetry.io/docs/languages/python/instrumentation/ and https://opentelemetry.io/docs/languages/python/propagation/ | Optional interoperable tracing **adapter** for host runtime: preserve privacy-minimal metadata by default, avoid mandatory collector or payload export. |
| Standard-library dataclasses/typing/JSON/hashing | https://docs.python.org/3/library/dataclasses.html | Preserve core's existing small immutable objects and trusted internal representation until richer schemas show a concrete need for an additional validation library. |

**Evaluation of these choices:** compare JSON-schema validation fidelity, cross-language semantic consistency, maintenance/licenses, startup cost, package footprint and existing source compatibility. No software dependencies added in P0. An entry-point loader or hook manager must not be mistaken for an untrusted plugin host.

## 5. CPU / GPU / FPGA / other-accelerator suitability matrix

C01 does **not** execute AI matrix kernels; it resolves capability metadata, validates small structured messages, checks grants and emits traces. It does not inherit a GPU requirement merely because HDC and KAN may use one.

| Backend | Expected benefit for **C01 core control plane** | Initial P0 decision |
|---|---|---|
| **CPU** | Low setup cost, scalar/string parsing, hash and permission checks, desktop portability; no host↔device transfer | **Preferred target**; use standard host CPU; test single-threaded and concurrency effects as appropriate |
| GPU (including Radeon AI PRO R9700) | Good for massively parallel numeric payloads, not tiny serial registry lookups; IPC/transfers likely dominate | **Not justified for C01**; GPU remains relevant for separate C08/C09/C16+ evaluations |
| FPGA | Potential custom wire/parser offload at much higher throughput, but compilation/transfer/deployment cost outweighs small-call control plane | **No implementation for C01** without measured sustained high-volume workload |
| NPU/ASIC/other accelerator | Designed for numerical/model work, not authorization, schema traversal or manifest lookup | **Not justified** for C01; reevaluate if tasks fundamentally change |
| Hybrid CPU+GPU | CPU control plane + GPU-backed plugins, without GPU-coupled core | **Architectural preference** for future integration; measure data movement per plugin separately |

This is an **engineering hypothesis** about backend suitability, not a comparative benchmark result. P3 should verify actual CPU control-plane overhead and test affected GPU-backed plugin dispatch; a full GPU/FPGA head-to-head is not warranted for C01 unless P0 identifies a plausible implementation.

## 6. Contracts, security, and compatibility design decisions proposed for review

1. Keep `Runtime.call(Request, HostContext) -> Response` behavior, strict outcome/assurance split and default-disabled modules. No unauthenticated remote API.
2. Keep a **single canonical definition** of each operation contract and deterministic generated schema/compatibility fixtures. P1 to design typed nested/list/optional/number/object schema support with bounded depth/count and strict unknown-field behavior. Do not interpret a JSON Schema as valid if unsupported features are silently ignored.
3. Compare `python-jsonschema` and Pydantic v2 with the existing trusted dataclasses; select one validated schema source and document round-trip conversions and limits. JSON Schema is for the **external/model-visible** shape; Protobuf is a proposed **internal typed** Lu boundary once its host adapter is defined.
4. Continue explicit champion nomination and versioned provider lifecycles. No automatic plugin activation or research promotion; support disable/replace semantics with admitted-call snapshot behavior.
5. Keep grant construction in a **trusted host boundary** and authorization independent of model requests. C02 must demonstrate OS-scoped confinement before invoking effectful/untrusted providers. Never expose `multiprocessing.Pipe` pickle to an untrusted provider.
6. Keep metadata-only default traces with correlation IDs, explicit trace failure handling, and strict non-retention of prompts/payloads/results. Optional OTel export only after consent and data governance design.
7. Treat **native Lu registration, Protobuf conversions and IPC transport** as C04 implementation scope. C01 must specify enough compatibility tests and handoff records to enable C04 without rewriting shared infrastructure.
8. No permission to infer a natural-language formulation is correct solely because a solver gives an exact response. Carry formalization/assumptions into the status model.

## 7. P0 baseline and acceptance plan (freeze before comparative measurement)

**Baseline systems to implement/test in P3:** 
- B0: direct, trusted function dispatch using the same C01 operation payload without registry/authorization policy (performance-only baseline; never user-facing replacement);
- B1: existing checked-in Cognitum core, with frozen source revision and identical workers;
- B2: C01 candidate using reviewed JSON Schema validation and typed boundary;
- B3: Lu-native tool interface (integration behavior/correctness baseline after C04 exists; not claimable as tested today).

**Fixed fixture families to define before P1:** empty registry; absent/disabled champion; install replacement success/failure; version/field/presence drift; malformed nested objects, unknown keys, `null` versus missing values; invalid/surplus payloads; explicit workspace/user scope mismatch; grants forged inside model args; effectful deny even with grant (until C02); research opt-in; replay side-effect denial; worker crash/timeout/no-orphan; trace payload leak attempt; repeated deterministic outcomes; correlation continuity across native boundary; concurrent disable/replace; size and recursion bounds.

**Safety/correctness gates:** 100% pass on frozen critical negative cases for authorization, identity, model-as-authority rejection, schema/version rejection, no invented exact answers, and no effects in replay; **zero unauthorized effects** and **zero private payload fields** in metadata traces. All previously passing unit/smoke cases must continue to pass on each supported platform. For C01 P3, report p50/p95/p99 call overhead, throughput under concurrency, peak RAM, worker startup/teardown overhead, dependency/startup footprint, schema serialization and conversions; distinguish **cold start**, **warm dispatch** and **provider execution**. Retain raw per-run distributions and CI/platform details; benchmarks must not be labeled performance wins from synthetic smoke fixtures.

**Performance/production gate still to freeze:** set workload-specific ceilings relative to B0/B1 and expected interactive Lu latency after gathering an actual non-optimized baseline and choosing batch sizes, concurrency, device/OS and dataset. Do not invent a target latency or claim an accelerator win before measurement. With an untrusted provider, C02's enforced sandbox and its overhead are obligatory regardless of faster unsafe baselines.

## 8. Phase status, risk register and work started

**P0 activities completed so far:** 
- Mapped actual Cognitum C01 source components and reported historical tests.
- Inspected `main` of Lu/Jan for native schema/dispatch/sandbox points.
- Reviewed selected official standards and maintained candidate libraries; documented CPU/accelerator rationale.
- Identified core-specific benchmark controls, critical negative fixtures and first contract decisions.

**Open P0 exit blockers:**
- [ ] Confirm the latest working Lu integration branch and exact CE registration/host authority boundary; main source was inspected, not an in-flight experimental branch.
- [ ] Choose canonical rich schema approach based on a runnable compatibility prototype and license/security/dependency review; compare `jsonschema`/Pydantic only if evidence warrants it.
- [ ] Specify and verify Lu's Protobuf/native message adapter, absent versus zero semantics, bounded serialization and schema hash/compatibility fixture strategy with C04.
- [ ] Define trusted lifecycle hooks and C02 threat model with Windows worker isolation, CPU/memory quotas and orphan cleanup.
- [ ] Freeze concrete P3 workloads and performance thresholds before measurement, with representative Lu tool-call sizes and concurrency.
- [ ] Approve the C01 contract/scope and baseline plan as the P0 exit design record.

**Risk register:** model-promoted grants; permissive schema interpretations; Python worker deserialization or resource exhaustion; state/plugin lifecycle races; schema drift across Rust/TypeScript/Python; default-off research unexpectedly made visible; logging sensitive content; benchmark confounding by Windows process spawn.

**Current phase decision:** **P0 in progress.** Existing prototype and historical verification are preserved as inherited P1/P2 evidence; no replacement was generated, no new test was run, and no production default was approved. Next actionable task is the **rich-schema/serialization compatibility spike**, in tandem with C02's worker security P0.

## 9. Sources and verification links

Internal repo: [Cognitum source and test tree](https://github.com/vjmichael/cognitum/tree/main/cognitum), [test suite](https://github.com/vjmichael/cognitum/tree/main/tests), [architecture limitations](../../architecture.md), [prior handoff](../../status.md), and Lu native files linked above. Public normative/reference materials are linked directly in §4. Access checked on 2026-10-26. Source inspection and authoritative reference reading are **not** execution or empirical validation.
