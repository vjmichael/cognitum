# Cognitum — Living Component Development Roadmap

**Design portfolio consolidated (2026-10-27):** [Complete AI architecture R1.5](Cognitum_Comprehensive_AI_Architecture_R1_5.md) · [technology portfolio C01–C19](design/technology-portfolio-C01-C19.md) · [eight compositional research protocols and P0–P3 test/release gates](design/research-validation-and-delivery.md). **Design completion is separate from implementing C06–C19 or closing C02/C04/real P3 benchmarks.** Use this living roadmap for *actual implementation status*, not as a design-gap substitute.

**Adopted:** 2026-10-26  
**Status:** Active process and component tracker  
**Scope:** Cognitum core services, production adapters, research modules, and future Lu integration components

## Repository ownership and Lu boundary

This conversation and repository develop **Cognitum only**. Lu is a read-only integration reference, never an implementation target here. Record any host-side DLC Core Extension requirements in the [Lu DLC CE Integration Addendum Register](lu-dlc-ce-addenda.md), with **Proposed** status until independently accepted by the Lu team. Cognitum may implement standalone tests, adapters and research against provisional documented contracts, but must not modify Lu. The original C01 tracing security hardening has since been [merged to Cognitum main in PR #1](https://github.com/vjmichael/cognitum/pull/1); historical per-PR CI counts below remain provenance records, not the current total test count. No change to Lu is implied.

**C01 P1/P2 delivery (separate Cognitum PRs, 2026-10-26):** [#1 tracing hardening](https://github.com/vjmichael/cognitum/pull/1) passed 40-unit/12-replay cases per Linux/Windows Python job; [#2 offline Lu CE manifest fixture](https://github.com/vjmichael/cognitum/pull/2) passed 42-unit/12-replay cases per job. PR #2 is **default-off, noninstallable, no Lu adapter**. Both changes are **merged to Cognitum `main`** (PR #1 merge `07e3f87d0b688d9d050f79d2a74721769f47992a`; PR #2 merge `29ad17aff147d177ac1394d7bc6c96ec2ecfb5af`). The [combined final CI](https://github.com/vjmichael/cognitum/actions/runs/40444933715) passed **51/51 unit tests and 12/12 synthetic replay cases per Windows/Linux Python 3.11/3.13 job**. These checks are **not P3 evidence**. Lu-side requests stay in [the addenda register](lu-dlc-ce-addenda.md).

**C01 typed results:** [versioned capability-result contract](components/core-runtime/P1-P2-typed-results.md) delivered via [merged PR #3](https://github.com/vjmichael/cognitum/pull/3). **76/76 unit tests and 12/12 replay cases passed** on all four Linux/Windows Python CI jobs ([PR evidence](https://github.com/vjmichael/cognitum/actions/runs/40445966151)). This is a Cognitum Python contract, not a Lu-native or P3 benchmark result. LU-CE-007 transport translation remains **Proposed**.

**C01 native Protobuf correction (2026-10-26):** [Protobuf request/result messages, Python bindings and binary codec](components/core-runtime/P1-P2-protobuf-native.md) merged via [PR #4](https://github.com/vjmichael/cognitum/pull/4). [Four-platform Protobuf CI 40447933037](https://github.com/vjmichael/cognitum/actions/runs/40447933037) passed **91/91 unit tests and 12/12 replay cases** per job with compiler-generated schema comparison. Lu `lu.v1.ToolCall/ToolReply` is reused conceptually but **actual Lu-native CE registration/invocation is still unimplemented**; C01/C02/C04 host gates remain open.

**C03 Protobuf evaluation milestone (2026-10-26):** [Versioned synthetic component suite/report](components/evaluation/P1-P2-protobuf-component-smoke.md) was added in an isolated Cognitum branch. [Four-platform CI 40457467419](https://github.com/vjmichael/cognitum/actions/runs/40457467419) passed **173/173 unit tests, 12/12 old replay cases, 10/10 pinned arithmetic cases and five Protobuf source/binding checks** per Python/OS combination. All Lu+transformer comparison arms A/B/C/D are **planned but not run**. No deployment/promotion evidence or C02 worker permission is claimed.

**C03 host-model benchmark handoff (2026-10-26):** [Versioned Protobuf benchmark configuration and capture](components/evaluation/P1-P2-host-benchmark-capture.md) fixes Lu/model/dataset/grader identities, sampling/tool budgets, a rotating matched A/B/C/D schedule, conventional comparator manifests, tool-call judgment, abstention/failure semantics, and presence-aware latency, memory, energy and token/cost fields. [CI 40458944707](https://github.com/vjmichael/cognitum/actions/runs/40458944707) passed **195/195 unit tests and 12/12 replay with six Protobuf schema comparisons** on Windows/Linux × Python 3.11/3.13. It verifies *only declared format and synthetic fixtures*, not actual Lu telemetry, model gains, or C02 sandbox security.

**C04 host collector boundary (2026-10-27):** [Seventh Protobuf schema](../proto/cognitum/benchmark/v1/collector.proto) and [C04 P0/P1/P2 report](components/integration/P0-P2-host-collector-receipt.md) provide offline validation of future signed Lu collector *claims*, binding exact C03 plan/capture bytes, pinned caller-provided Ed25519 public key, challenge, model/host IDs and source digests. **No real Lu model or collector data was obtained**; all P3 efficacy and C02 OS security gates remain blocked.

**C05 exact computation hardening (2026-10-27):** [C05 P0 research](components/calculator/P0-research.md) and [P1/P2 implementation](components/calculator/P1-P2-exact-verification.md) add bounded ASCII arithmetic input screening, an AST-independent rational reference parser, deterministic differential corpus, and strict known-tag/nested-field Protobuf canonicalization. [CI 40462149387](https://github.com/vjmichael/cognitum/actions/runs/40462149387) passed **216/216 unit tests, 12/12 legacy replay, 10/10 synthetic calculator evaluation and seven compiled Protobuf schema checks** per Windows/Linux Python 3.11/3.13 configuration. These are component tests, **not** a production Lu-integrated model P3 benchmark. 

**C05 six scientific specialist expansion (2026-10-27):** [P1/P2 scientific math contract and validation](components/calculator/P1-P2-scientific-specialists.md) introduces six **typed native Protobuf** request/result pairs (symbolic algebra, scientific functions, high-precision Decimal, rational matrices, bounded roots, and discrete oscillator simulation). An inert `cognitum.math.v1.SpecialistCatalog` supplies fixed guidance **without host approval or model advertising**. All kernels are bounded, optional mpmath is a scoped dependency, and C02 worker launch remains closed. [CI 40465416831](https://github.com/vjmichael/cognitum/actions/runs/40465416831) passed **232/232 unit tests, 12/12 replay and 8/8 compiler-matched Protobuf schemas** on all four Windows/Linux × Python 3.11/3.13 combinations. This is a CPU reference **not** general CAS/ODE capability or a Lu model performance claim.

**C06 ANSF ownership audit started (2026-10-27):** [Lu ANSF-backed canonical memory P0 research and read-only Protobuf retrieval plan](components/memory/P0-ansf-ownership-retrieval.md) inspected current Lu session books, immutable revisions, global FTS5 catalog and explicit desktop memory-sync boundary. Proposed Cognitum role: **authorized read-only evidence selection and rebuildable derived indexes over Lu-host-owned source records**, not a second canonical store. Lu host identity/scope, retention/deletion and real-model C03 P3 remain unresolved. Documentation only; no C06 executable or real memory access.

## Active execution sequence

The canonical priority/dependency order is [**Ordered Component Build Path**](build-order.md). It lists C01–C19, differentiates independent P0 research from implementation dependencies, and identifies the first active work item: **[C01 / P0 core runtime research and design](components/core-runtime/P0-research.md)**. The older component table below is the status inventory, not the prioritized build sequence.

## Transformer-centered architectural objective

**Cognitum exists to augment the transformer selected/loaded by Lu, under Lu's existing host authority and orchestration.** See [Lu × Cognitum — Transformer-Centered Collaboration](lu-cognitum-integration.md). Each component P0 must define the intended improvement to a concrete Lu+model task and compatible native interface. Each relevant P3 must include end-to-end **Lu+transformer** comparisons against host-only and competent conventional-tool baselines—not only isolated component throughput or retrieval metrics. Experimental HDC/KAN benefits are not presumed from archival existence.

## Governing decision

Cognitum no longer advances through one project-wide Phase 0–5 sequence. **Every component follows its own P0 → P1 → P2 → P3 lifecycle**, with explicit evidence and acceptance criteria. Components can occupy different phases simultaneously. Dependency and safety gates still apply; independent phases do not permit bypassing shared infrastructure or security controls.

This document is the **current execution roadmap**. The global stages in [Revision 1.4 §13](sources/Cognitum_Source_Informed_Revision_1_4.md), the earlier [Revision 1.2](sources/Cognitum_Strengthened_Revision_1_2.md), and the initial eight-week plan in [design 1.0](sources/hybrid_ai_design.md) remain historical design inputs, **not active project-wide phase identifiers**. Do not rewrite those source documents. [Architecture](architecture.md), [research agenda](research.md), and [handoff/status](status.md) retain their existing evidence and limitations.

**Core rule:** a phase is an engineering activity, not a certification of scientific improvement or production safety. Completion requires artifacts; a negative benchmark result is still a valid completed experiment, but does not authorize promotion.

## Universal component lifecycle

### P0 — Research, standards, library selection, and design (mandatory)

- Define the component's precise task, boundaries, input/output contracts, expected failure modes, success metrics, and dependencies. Distinguish reliable production capability from open research hypotheses.
- Survey relevant scholarly research, applicable technical standards, mature/de facto interfaces, reproducible reference implementations, datasets, and competing approaches. Record sources and dates.
- Search for maintained standard libraries and compatible existing implementations **before** planning new code. Compare capability, portability, security posture, compatibility, maintainer health, license, and cost. Prefer reuse where it meets requirements; do not equate library popularity with correctness.
- Evaluate **CPU, GPU, FPGA, and other relevant architectures** (e.g., NPU/ASIC/accelerators or hybrid CPU+GPU), including the actual target hardware and software stack, precision, memory/VRAM, data movement, startup overhead, power/energy, and deployment portability. P0 proposes plausible candidates; **P3 empirically determines the preferred target** for defined workloads.
- Specify standard APIs/schema versions, typed conversions, provenance, privacy/access policy, isolation needs, graceful degradation, and how the component is enabled or disabled.
- **Before implementation**, define representative workloads, strong conventional baselines, test datasets and licensing/consent, metrics, fixed acceptance thresholds, ablations where warranted, and held-out evaluation rules.
- Inventory prior Cognitum/Lu/ChatGPT Library work. Preserve immutable sources, hashes, reports, validation limits, and reusable code; do not restart concluded work merely because a new component lifecycle exists.

**P0 exit artifacts:** a reviewed component design specification; literature/standards/library comparison; hardware decision matrix with rationale; dependency/contract/security plan; test and baseline plan with unambiguous gates; source/reuse inventory.

### P1 — Implementation

- Build **or adapt existing code** according to P0. Favor proven libraries over duplicate implementations when appropriate.
- Implement strict versioned contracts and typed boundaries, optional enable/disable lifecycle, resource budgets, deterministic authorization, error/outcome reporting, and instrumentation.
- Add focused unit tests and fixtures. Separate trusted host authority from model-supplied requests; preserve correct operation when the component is absent.
- Record implementation versions, library licenses, selected execution backends, reproducible environment/configuration, and deviations from P0. Update the design if a material assumption changes.

**P1 exit artifacts:** code or reviewed integration adapter, tests, configuration, contracts, build/run instructions, and documented known limitations. A working prototype is not yet a validated component.

### P2 — Smoke testing and safety checks

- Confirm install/load/start/stop, basic known-correct outputs, schema handling, version rejection, timeouts, missing dependency paths, disable/re-enable, and honest failure disclosure.
- Run small deterministic positive, negative, malformed-input, edge-case, restart/recovery, and isolation tests appropriate to the component.
- Verify actual permission enforcement for effectful/untrusted code; a worker process alone is **not** a sandbox. Reject unsafe scenarios rather than claiming isolation without evidence.
- Record platform/backend coverage and test outputs. Component smoke tests must not be described as general scientific benchmarks.

**P2 exit artifacts:** passing reproducible smoke-suite report (or explicit failures and blockers), logs, test environment/versions, and issue list. Unsafe unresolved blockers prevent integration/promotion.

### P3 — Standard baseline evaluation and architectural validation

- Run the P0-defined benchmark with matched, competent controls and held-out tasks. Where research components are composed, compare individual components, conventional compositions, experimental combinations, and host-only behavior where applicable.
- Measure task correctness/quality and uncertainty, failure/abstention rates, latency, throughput, memory/VRAM, startup/conversion costs, power/energy where measurable, and resource/financial costs.
- Measure CPU/GPU/FPGA/other feasible backends under comparable conditions. Report the practical hardware recommendation **for each workload**, not a blanket winner. State unavailable equipment/toolchains rather than fabricating results.
- Preserve seeds, dataset splits, configurations, environment, baseline versions, confidence intervals or uncertainty analysis where applicable, and reproducible reports.
- Report **wins, ties, regressions, and negative findings**. Decide whether to keep research-only, revise, retire the hypothesis, or recommend production adoption. Production enablement additionally requires appropriate security, interoperability, reliability, and privacy review.

**P3 exit artifacts:** frozen benchmark specification, raw summarized results/metrics, comparative report, hardware recommendation, limitations, reproducibility instructions, and explicit promotion decision. **P3 completed ≠ default-on approved.**

## Component-level tracking

Each component uses the same lifecycle. An entry's status describes **evidence in this Cognitum repository**, not external projects, unreviewed assertions, or tests not yet inspected. P0 can incorporate pre-existing design material but its exit gate is not automatically passed. “P0 pending” is not a claim that no one has researched the topic.

| Component / capability | Current evidence and next lifecycle work |
| --- | --- |
| Core contracts, registry, policy, runtime, and tracing | **P1 implementation and limited P2 checks exist** in the separate Phase 0 starter. Complete P0 evidence review, broader security/host-interoperability checks, and P3 validation. Not an untrusted plugin host. |
| Evaluation and replay harness | **P0 evaluation standardization started:** [C03/P0 baseline/control and Lu+transformer test plan](components/evaluation/P0-research.md). Existing **P1 implementation and limited P2 checks**: synthetic replay and trace fixtures. P3 real-task validation remains open; smoke fixtures are not promotion evidence. |
| Calculator / exact arithmetic | **P1 implementation and limited P2 checks exist:** bounded Fraction/AST calculator. Full P0/standards review and P3 established baseline comparison remain to be recorded. |
| Canonical memory and retrieval (SQLite/FTS5, provenance, deletion) | **P0 started:** [Lu ANSF ownership/retrieval audit](components/memory/P0-ansf-ownership-retrieval.md) identifies existing SQLite books, FTS5, immutable revisions and global catalog as preferred canonical host sources. Cognitum-only read-only Protobuf evidence validation proposed; authoritative Lu approval, secure source access, deletion and benchmarks still pending. No P1/P2 implementation or P3 results. |
| Typed state and belief revision (event store, snapshots, conflicts) | **P0 pending:** define event schema, consistency and update semantics, trusted source/consent, and conventional state baselines. |
| HDC / compositional relational memory | **K4 archive recovered and source integrity verified**; fresh Linux CPU baseline passed 20/20 HDC self-tests (within the combined 41-unit-test + 20-self-test run). **P0 integration requirements remain open:** canonical state/index/versioning, native CE bridge and matched Lu+model baselines. [Archive/reuse audit](components/hdc-kan/P0-archive-reuse-audit.md). |
| KAN / numerical or symbolic learning | **K4 integrated archive and optional default-off depth overlay recovered and integrity checked**; fresh combined Linux CPU 41-unit-test run passed. **P0 integration, symbolic/MLP baselines and Lu+transformer comparisons remain open.** [Archive/reuse audit](components/hdc-kan/P0-archive-reuse-audit.md). |
| Formal verification / proof and constraints | **P0 pending:** inspect Z3/cvc5/related tools, formalization validation, and proof/witness checks. |
| Combinatorial optimization | **P0 pending:** assess CP-SAT, HiGHS, and domain-specific solver baselines. |
| Planning and search (MCTS/DP/classical) | **P0 pending:** pick domain, compare classical planners/search, bound search/resource use. |
| Probability / Bayesian reasoning | **P0 pending:** compare analytical Bayes and maintained statistics/probabilistic libraries. |
| Causal modeling | **P0 pending:** define identification assumptions and suitable established toolkits. |
| Spatial reasoning / object persistence / scene graphs | **P0 pending:** examine standard scene representations, geometry engines, and object-tracking baselines. |
| Physics and dynamical simulation | **P0 pending:** use dimensional/unit checks, mature numerical simulation baselines; research surrogates separately. |
| Sequential/SSM modeling | **P0 pending:** distinguish dependable typed state from learned state-space models and require concrete held-out use cases. |
| Meta-learning / adaptation | **P0 pending:** clarify task and compare conventional adaptation/fine-tuning baselines. |
| Topological data analysis | **P0 pending:** identify a real workload and review established TDA libraries before implementation. |
| Lu host integration, secure worker boundary, and capability composition | **P0–P3 per subcomponent:** inspect Lu's native interfaces; reuse existing tools and messaging. Isolation, permissions, versioned conversion, recovery, and composition are dependencies, not assumptions. |

## Preserving completed HDC/KAN work

The HDC/KAN research stream was intentionally closed before Lu implementation work, with an archived K4 integrated prototype and optional, **default-off** KAN depth extension. That is a **research baseline and candidate reusable asset**, not evidence that Cognitum has already imported it or validated the new host boundary. The repository does not presently contain the archived implementation.

Archive discovery and integrity checks are **now complete** for these two components, with a new independent CPU unit/self-test run. Continue P0 with interface, provenance, benchmark and host-compatibility design; reuse verified existing tests and reports whose conditions still match. Only run new experiments to fill an actual integration/validation gap or test a genuinely new hypothesis. Do not label legacy research as new Cognitum P3 evidence without verifying methodology and comparability.

**New evidence (2026-10-26):** [Recovered HDC/KAN K4 archive and fresh test audit](components/hdc-kan/P0-archive-reuse-audit.md). The closure bundle, integrated code and default-off KAN overlay were located in the user's Library and checksums verified; the combined 41 unit tests and 20 HDC self-tests passed in a new Linux CPU run. This is **not** Cognitum/Lu integration or a general benchmark win.

## Workflow and project hygiene

- Keep one tracker/record **per component**, with: owner, scope, dependencies, current phase, evidence links, blocker, target hardware candidates, pass/fail gates, benchmark baselines, and promotion status.
- Store or link the four phase artifacts as `P0-design`, `P1-implementation`, `P2-smoke`, and `P3-benchmark` under a component-specific location when work begins. Do not create empty folders or placeholder success reports.
- Track dependencies explicitly; work may overlap across independent components, but a component cannot bypass required interfaces, canonical state ownership, data protections, or sandboxing.
- Distinguish **not started / in progress / evaluated / blocked** from **recommended / production default**. Revisit P0 when standards, requirements, hardware, or evidence materially change; do not silently rewrite completed benchmarks.
- Maintain a claims ledger with source, method, result, limitations, replication, and promotion decision. Keep experimental challenges optional and ordinarily disabled until approved.
- No implementation, tests, or archived research assets were modified as part of adopting this roadmap.

**Cross-cutting C02 security P0 has begun:** [Windows AppContainer/Job Object and Lu-native worker threat model](components/security/P0-research.md). No effectful/untrusted worker can be enabled until independent OS confinement and authorization are verified.

## Immediate planning focus (not global phases)

1. Audit the already-implemented core, calculator, and harness against the new P0/P2 exit requirements; preserve verified work instead of rebuilding it.
2. Undertake P0 for canonical memory and typed state, coordinating shared SQLite ownership and belief revision with Lu.
3. Perform an archive/reuse audit for HDC and KAN; create Cognitum-specific adaptation cards only after finding the real implementations and reports.
4. Prioritize secure worker isolation, typed conversion, and dependency/cost budgets before enabling effectful or untrusted providers.
5. Select additional components based on concrete user tasks and dependency readiness, not the order in an obsolete global-stage chart.
