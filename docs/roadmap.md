# Cognitum — Living Component Development Roadmap

**Adopted:** 2026-10-26  
**Status:** Active process and component tracker  
**Scope:** Cognitum core services, production adapters, research modules, and future Lu integration components

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
| Evaluation and replay harness | **P1 implementation and limited P2 checks exist:** deterministic synthetic replay and trace fixtures. P0 benchmark definition and P3 real-task validation remain open; smoke fixtures are not promotion evidence. |
| Calculator / exact arithmetic | **P1 implementation and limited P2 checks exist:** bounded Fraction/AST calculator. Full P0/standards review and P3 established baseline comparison remain to be recorded. |
| Canonical memory and retrieval (SQLite/FTS5, provenance, deletion) | **P0 pending:** inventory mature libraries and store semantics; benchmark conventional retrieval and revision/deletion correctness. |
| Typed state and belief revision (event store, snapshots, conflicts) | **P0 pending:** define event schema, consistency and update semantics, trusted source/consent, and conventional state baselines. |
| HDC / compositional relational memory | **Prior research frozen outside this repo** (user-identified K4 integrated baseline). **P0 reuse/integration audit pending:** locate and verify source files, test reports, licenses, interfaces, and provenance in the ChatGPT Library/research archive. Adapt, do not automatically redo the original research; Cognitum P1/P2/P3 integration evidence is still required. |
| KAN / numerical or symbolic learning | **Prior research frozen outside this repo**, including default-off optional KAN depth add-on. **P0 reuse/integration audit pending:** recover exact implementation/report references; do not assume prior experiments prove symbolic-regression or production benefits. Cognitum-specific P1/P2/P3 follow as needed. |
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

For these two components, start P0 with **archive discovery, provenance and compatibility review**; reuse any verified existing tests and benchmark reports whose conditions still match. Only run new experiments to fill an actual integration/validation gap or test a genuinely new hypothesis. Do not label legacy research as new Cognitum P3 evidence without verifying methodology and comparability.

## Workflow and project hygiene

- Keep one tracker/record **per component**, with: owner, scope, dependencies, current phase, evidence links, blocker, target hardware candidates, pass/fail gates, benchmark baselines, and promotion status.
- Store or link the four phase artifacts as `P0-design`, `P1-implementation`, `P2-smoke`, and `P3-benchmark` under a component-specific location when work begins. Do not create empty folders or placeholder success reports.
- Track dependencies explicitly; work may overlap across independent components, but a component cannot bypass required interfaces, canonical state ownership, data protections, or sandboxing.
- Distinguish **not started / in progress / evaluated / blocked** from **recommended / production default**. Revisit P0 when standards, requirements, hardware, or evidence materially change; do not silently rewrite completed benchmarks.
- Maintain a claims ledger with source, method, result, limitations, replication, and promotion decision. Keep experimental challenges optional and ordinarily disabled until approved.
- No implementation, tests, or archived research assets were modified as part of adopting this roadmap.

## Immediate planning focus (not global phases)

1. Audit the already-implemented core, calculator, and harness against the new P0/P2 exit requirements; preserve verified work instead of rebuilding it.
2. Undertake P0 for canonical memory and typed state, coordinating shared SQLite ownership and belief revision with Lu.
3. Perform an archive/reuse audit for HDC and KAN; create Cognitum-specific adaptation cards only after finding the real implementations and reports.
4. Prioritize secure worker isolation, typed conversion, and dependency/cost budgets before enabling effectful or untrusted providers.
5. Select additional components based on concrete user tasks and dependency readiness, not the order in an obsolete global-stage chart.
