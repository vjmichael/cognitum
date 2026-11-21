# ADR — Cognitum's Orc Graph and CH⊕aT (owner decision, 2026-11-20)

**Decision:** ADOPTED AS NORMATIVE PRODUCT ARCHITECTURE AND COLLABORATION PRINCIPLE. **Engineering:** QUEUED, not implemented or native-accepted by this document. **Authority:** User-owned product decision. **Relationship:** Extends [MEL ADR-001](../research/mel/ADR-001.md), the [R1.6 architecture](../Cognitum_Comprehensive_AI_Architecture_R1_6.md) and the [master task ledger](../MASTER_TASK_LEDGER.md); no replacement of accepted source or research evidence.

## Names and meaning

**Orc Graph** is the product name for Cognitum's typed scientific capability graph and its bounded scientific orchestration, routing, composition, and verification *within* the existing Mathematical Execution Layer (MEL). An Orc Graph is a reviewed computation plan over discoverable first-party capabilities, not an independently authorized model or a second worker/scheduler/registry. The mnemonic **ORC = Orchestration, Routing, Computation** is informal; the product name is **Orc Graph**.

**CH⊕aT**, also informally written **CH+A(t)** or **ch+at**, is promoted from a conversational mnemonic to an **owner-adopted design principle** for task-specific human–AI augmentation. C means capability; H means human/user direction and judgment; ⊕ denotes complementary cooperation rather than mere concatenation; a/A denotes artificial intelligence and its augmenting tools; T is the particular task. The aspiration is to make the measured combined task capability exceed the better standalone participant, for appropriately chosen tasks:

`C_{H⊕A}(T) > max(C_H(T), C_A(T))`

This is a **falsifiable objective, not a universal mathematical identity, guaranteed synergy, or completed empirical result**. Comparison requires a specified task, independent ground truth/assessment, matched budgets, human-only and AI-only controls where valid, and measurement of errors, elapsed time, effort, reliability, and quality. A combined workflow that performs worse must be reported as such. User-facing product terminology should prefer **user** over **human**; H is retained only to preserve the owner's original notation. The separate **KαNT** framework addresses model architecture, scale, and task-dependent capability; do not conflate it with the CH⊕aT collaboration claim.

For Cognitum, CH⊕aT is implemented through *eventual* usable, transparent, controllable collaboration: the user defines goals and permissions, AI/model logic may propose mathematical methods, Orc Graph can construct/review typed candidate plans, and authenticated execution/independent verification produce interpretable evidence. The framework applies at product level; Cognitum does not need to own the user's conversation or Lu's model runtime to satisfy its portion.

## Recovered originating Lu practical-capability framework (November 7, 2026)

**Historically adopted notation: `C_practical = f(K, I, A, F)`, NOT `f(K,I,A,P)`.** The original user observation was that “capability + model-facing interface = performance”: an AI may possess reasoning capability but not the means to execute it. The more explicit Lu formula adopted on November 7 means:

| Letter | Intended factor |
| --- | --- |
| **K** | Knowledge and reasoning capability |
| **I** | Tool/model-facing interfaces that expose applicable capabilities |
| **A** | Host-owned authorized access and scoped execution permission |
| **F** | Verified feedback, correction and recovery |

The four-factor expression is a **conceptual function**, not a numerical performance law or a guarantee of synergy. It should be evaluated with real task completion, correctness, authorization, error recovery, cost and independent observations. KαNT (model architecture/scale/task analysis), the practical Lu `K/I/A/F` factors and CH⊕aT (user–AI task collaboration) describe **related but nonidentical levels**, not a formally established nested derivation. Orc Graph specifically strengthens **I** (typed discoverable mathematical interfaces), **A** (host-governed execution through existing gates) and **F** (source-bound checking/feedback), while its mathematical candidates can augment **K**. No renaming of the original formula, research result or Lu product code is authorized here.

## Existing architecture must be reused

- Extend **existing** MEL typed objects/Protobuf and admission, `Registry`, `Runtime`, policy, existing cooperative DAG/`cooperative.py`, source and checkpoint guards, cancellation, bounded workers, and evidence receipts. ADR-001 explicitly disallows a second orchestrator, scheduler, plugin registry, authorization service, journal, or agent loop. Orc Graph is a **named evolution of that existing cooperative execution path**, not a parallel implementation.
- No new unchecked generic execution, arbitrary scripts, host filesystem/network access, implicit checkpoint trust, self-issued grants, autonomous laboratory or physical-device control. Planner/router proposals are inert until validated by existing trusted host admission. Existing research routes remain **default-off**.
- Cognitum keeps HDC, KAN, SSM, exact symbolic/arithmetical, deterministic numerical/physics, formal, and statistical solvers as independently useful and **equal eligible candidates**. Equal eligibility is not equal assurance: exact certificates, numerical approximations, and empirical learned predictions receive distinct validation and precedence where applicable. A correct exact solver should not be displaced by a heuristic score.
- No forced HDC/KAN/SSM cascade; optional capability composition must be justified by type compatibility, scientific purpose, net observed accuracy, uncertainty, latency, memory and CPU cost. CPU-first remains default.

## Typed capability graph contract

Each candidate node declares operation identity/version, schema/units/clock/coordinates, numerical representation and precision, deterministic/stochastic/learned semantics, assumptions and evidence maturity, source/checkpoint provenance, effects, cost limits and failure/abstention behavior. Every edge is an explicit reviewed conversion or type-compatible binding: no unannounced unit conversion, future observation leakage, lossy representation substitution or silent correction of missing values. Plan compilation checks graph acyclicity, dependencies, source freshness, host scope and authorized effect class before execution.

The scientific data pathway should preserve original observations and metadata; validate timestamps, units, gaps, duplicate/conflicting measurements, and source custody; derive train-only features and explicitly available covariates; conduct chronological or site-holdout training/calibration/test without cross-split leakage. Transformations are immutable, hash/revision-linked, reversible where possible, and documented when lossy. The planner must be able to select a direct simple baseline (persistence, ridge, classical Kalman/ARIMA, known mechanistic differential solver) over a hybrid, and must be able to decline an unqualified comparison.

Candidate evaluation distinguishes numerical residual/certification from holdout forecasting skill, probabilistic calibration from nominal coverage, test-independent selection from post hoc test-set cherry-picking, and site-independent evidence from one-publisher/site reuse. Where comparisons are invalid, publish limitation/refusal instead of fabricated confidence.

## Planned staged work and evidence gates

| Task | Planned engineering scope | Required acceptance, not assumed done |
| --- | --- | --- |
| **COG-ORCH-01A** | Inventory and reconcile COG-06 reviewed DAG, MEL routes, typed objects, HDC/KAN/SSM specialist prototype, deterministic and statistical tools; define capability descriptors and compatible edge profiles | Exact source/contract crosswalk; no second scheduler; rejected unknown/cyclic/stale/incompatible/unauthorized graph fixtures |
| **COG-ORCH-01B** (includes **COG-PIPE-01**) | Shared science data qualification, immutable provenance, features/units/clock/gaps and train-only preprocessing | Original-byte lineage; missingness/leakage/adversarial unit cases; genuine independent source data and consent/license requirements |
| **COG-ORCH-01C** (includes **COG-EXEC-01**) | Compile inert candidate graph to existing authorized MEL/Runtime/worker/cooperative execution; deterministic-first eligible routing and strict operator caps | Same-source cancellation, revocation, time/resource limits, restart, host-scope, no accidental research authorization; Windows/Linux native execution |
| **COG-ORCH-01D** | Matched alternative candidates and optional residual/multi-engine cooperation, independent verification and uncertainty reports | Compare ridge/persistence/mechanistic/SSM/KAN/HDC/selected composites on identical heldout origins; preserve null/negative results, drift and dependent uncertainty failures |
| **COG-ORCH-01E** | Evidence-informed but bounded planner and operator explanation with task-specific learned selection only where validated | Simple deterministic router as default; frozen out-of-domain tasks; calibrated abstention, budget/cost accounting and actual user/model interaction/override evidence; measured CH⊕aT synergy only if verified |

**Ordering:** Maintain independent COG-05-SSM-POST-NATIVE-05-R4-R1 physical data, cross-platform KAN checkpoint and transfer validation as its own source-locked research task. Orc Graph A/B architectural and data-contract work may proceed independently; C/D/E must reuse and reconcile established MEL/COG-06 infrastructure rather than prematurely claiming release integration. Batch fixes and CI; do not stack acceptance runs.

## Design acceptance versus scientific or release acceptance

This ADR **accepts the name and architectural direction only**. It neither promotes the 72 partial DS capability groups nor reclassifies any HDC/KAN/SSM scientific result or release route. Accepted R4 native SHA `cf78900c4fcec3981b93c842144c53b15cc0d411`, four-platform 25/25 per target remains untouched; its negative ridge comparisons, KAN checkpoint bitwise nonidentity, dependence-calibration failures and upstream sensor provenance gaps remain open. Prove cross-platform graph execution and independent end-to-end user–AI benefit before product promotion. No Lu source is modified, and installed Lu interoperability remains deferred to its separate authorized gate.
