# Cognitum — Ordered Component Build Path

**Adopted:** 2026-10-26  
**Status:** Active priority and dependency plan  
**Governing lifecycle:** [Per-component P0–P3 roadmap](roadmap.md)

## Operating model

**Build in dependency-informed priority order, not one monolithic project-wide phase schedule.** Every item completes its own four stages: **P0 research/standards/libraries/CPU-GPU-FPGA suitability → P1 implementation/adaptation → P2 smoke tests → P3 standardized baseline comparisons**. Independent P0 work can overlap; a production capability cannot bypass a required permission, storage, schema, or evaluation dependency.

The order is a default priority and not a fabricated ETA or a mandate to complete unrelated advanced modules before a task-driven use case. A verified existing implementation may enter the lifecycle as inherited evidence, but must still pass the new component's relevant acceptance gates.

## Mandatory transformer-centered integration requirement

The authoritative architecture is [Lu × Cognitum — Transformer-Centered Collaboration](lu-cognitum-integration.md). **Lu and whichever transformer it has loaded are the system being augmented.** Lu owns model selection/lifecycle, sessions, permission decisions, discovery/dispatch, bounded cross-component orchestration and final synthesis. Cognitum supplies optional, domain-specialized computations and evidence through Lu-native CEs/contracts; it must not duplicate Lu's model loop or overwrite host authority. **Every component P0 specifies its Lu+model task**, and every relevant P3 compares Lu+loaded transformer without Cognitum, with established conventional tools, and with the candidate capability/combination. Model-specific tool reliability and hardware/energy costs must be measured instead of assumed.

**C01 update (2026-10-26):** Source audit located Lu's active `lu/core-contracts-native-registry` branch with a functioning *experimental* native Rust registry and Protobuf/JSON codec contracts, unlike the older `main` baseline. C01 should adapt Cognitum to Lu's native host rather than duplicate a registry. [Pinned active-branch audit and compatibility gaps](components/core-runtime/P0-lu-native-audit.md). C01 P0 is open; optional CE lifecycle and effect/version mapping are blockers.

**Latest Lu read-only CE review (2026-10-26, merged Cognitum [PR #5](https://github.com/vjmichael/cognitum/pull/5)):** [C01 Cognitum→Lu handoff](components/core-runtime/P1-P2-lu-ce-discovery-handoff.md) inspected `lu/independent-branding-ce-foundation` two commits ahead of the older core-contracts branch. **Lu now has a distinct `CoreExtension` kind with trusted registration/unregister; the older statement that no CE variant exists is superseded.** A complete signed installer/lifecycle and per-model exposure remain unimplemented. A newly identified blocker is Lu's lack of a **no-effect/pure-compute** ToolEffect for Cognitum's exact calculator. Cognitum's handoff deliberately remains disabled, uninstalled and unadvertised. Separate user decisions about workspace-specific registries and tool/workflow/state/event discovery remain architectural goals, not declared shipping APIs.

## Ordered development queue

| ID | Order / component | Essential dependencies and acceptance intent | Evidence and next activity |
|---|---|---|---|
| **C01** | **1. Core contracts, registry, policy, and runtime** | Own strict versioned I/O, capability selection, disabled-plugin behavior, accurate status/outcome/fallback, and reliable dispatch | **P0 Lu CE ABI/security audit remains open; P1 typed results and Protobuf-native domain messages merged, P2 CI passed (91/91 tests + 12/12 replay + compiled schema verification per configuration).** [P0](components/core-runtime/P0-research.md) · [typed result contract](components/core-runtime/P1-P2-typed-results.md) |
| **C02** | **2. Security, scoped permissions, worker isolation** | Stable C01 authority model; OS-enforced confinement before *any* untrusted or effectful plugins | **P0 OS isolation research ongoing; P1 typed worker Protobuf and fail-closed admission implemented, P2 136/136 units + 12/12 replay + three compiled Proto schemas per OS/Python CI configuration passed.** New worker launch remains intentionally blocked; Python spawn is **not** a sandbox. [C02 research](components/security/P0-research.md) · [P1/P2 worker boundary](components/security/P1-P2-protobuf-worker-boundary.md) · [Protobuf supervisor negative acceptance plan](components/security/P1-P2-supervisor-acceptance.md) · [signed host conformance receipt gate](components/security/P2-host-conformance-gate.md) |
| **C03** | **3. Evaluation harness, observability, replay** | C01 contracts; test definitions, trace correlation, privacy, baseline controls and reproducibility | **P0 Lu+transformer task design ongoing; P1 deterministic Protobuf synthetic evaluator implemented, P2 CI passed 173/173 unit tests, 12/12 legacy replay and five compiler-matched Protobuf schemas per Linux/Windows Python configuration.** Only 10 fixed calculator cases were run; A/B/C/D Lu-model arms remain **unexecuted**. [P0](components/evaluation/P0-research.md) · [P1/P2 synthetic evaluator](components/evaluation/P1-P2-protobuf-component-smoke.md) · [P1/P2 Lu+model benchmark plan/capture contracts](components/evaluation/P1-P2-host-benchmark-capture.md). **Latest C03 P2 six-schema CI 40458944707: 195/195 unit tests, 12/12 replay per Linux/Windows Python job. A/B/C/D remain unexecuted; P3 real-task evaluation pending** |
| **C04** | **4. Lu-native integration and typed composition** | C01–C03 integration requirements; reuse Lu's tool schema/dispatch/security surface and agreed internal Protobuf boundary; preserve external JSON | P0 needed; inspect actual Lu host, no independent model loop or duplicate MCP server |
| **C05** | **5. Exact calculator** | C01 and C03; simple known-correct capability for end-to-end integration | Existing bounded AST/Fraction implementation and reported P2 checks; preserve and baseline it |
| **C06** | **6. Canonical memory and retrieval** | C01–C03, persistent store and grants under C02; SQLite/FTS5, provenance, correction and deletion semantics | P0 needed; avoid duplicated Lu stores without ownership decision |
| **C07** | **7. Typed state and belief revision** | C06 canonical claims/store decisions; event stream, contradiction, retraction, supersession, idempotency | P0 needed; jointly design store/events and migration ownership |
| **C08** | **8. HDC reuse/integration** | C06/C07 canonical memory/state and C03 baselines; indexes remain derived | **Archived research recovered and independently retested**; verify typed canonical index/host contracts before C08 integration |
| **C09** | **9. KAN reuse/integration** | C01/C03/C05 contracts and numeric baseline; no assumption that KAN is an exact calculator | **Archived research recovered and independently retested**; K4 + default-off depth overlay preserved, Cognitum integration remains unverified |
| **C10** | **10. Formal verification** | Typed formalization and failure/status contract; confirm witness/certificate and unsupported/unknown semantics | P0 needed; research Z3/cvc5 and comparable solvers |
| **C11** | **11. Combinatorial optimization** | C10 formalization lessons where relevant; explicit resource/certificate semantics | P0 needed; benchmark CP-SAT/HiGHS and domain incumbents |
| **C12** | **12. Planning, MCTS, DP and search** | C11 as useful incumbent, but not a hard technical dependency for every search problem | P0 needed; define domain, comparable planners, and resource ceilings |
| **C13** | **13. Probabilistic / Bayesian inference** | Typed assumptions, calibrated evidence/uncertainty and reliable numeric computations | P0 needed; begin with analytical Bayes and established stats libraries |
| **C14** | **14. Causal inference / intervention** | C13 uncertainty contracts where appropriate; identification assumptions are independently required | P0 needed; compare standard causal libraries and falsifiable tasks |
| **C15** | **15. Spatial objects / scene graphs** | Canonical identity/state and typed objects; prioritize earlier if AI Film Studio has a specific task | P0 needed; maintain stable object IDs outside approximate features |
| **C16** | **16. Physics / simulation** | C15 representation when spatial, but independent numerical simulation may begin earlier for real tasks | P0 needed; validate units, conservation/boundaries, and reference simulators |
| **C17** | **17. SSM / learned temporal modeling** | C07 typed baseline; learned model must beat competent chronological state controls | P0 needed; explicitly distinct from ordinary state management |
| **C18** | **18. Meta-learning / adaptation** | Stable benchmarks and explicit privacy/retention; compare conventional adaptation methods | P0 needed, task-driven |
| **C19** | **19. Topological data analysis** | Demonstrable task, appropriate data/manifold assumptions, and standard library control | P0 needed, task-driven |

### Dependency graph (minimum)

```text
C01 contracts/registry/runtime
  |-- C02 permissions / secure worker -------------------+
  |-- C03 evaluation / trace / replay -------------------+-- C04 Lu integration
  |-- C05 calculator                                     |
  +-- C06 canonical memory (+ C02 effects) -- C07 state -+-- C08 HDC integration
                                                      
C01 + C03 + C05 ----------------------------------------- C09 KAN integration
C01 + C03 + verified formalization ---------------------- C10 verify
C10 / task constraints + C03 ----------------------------- C11 optimize -> C12 plan
C01 + C03 ------------------------------------------------ C13 probability -> C14 causal
C06 + C07 + C03 ----------------------------------------- C15 spatial -> C16 physics
C07 + C03 ------------------------------------------------ C17 learned SSM
C03 + user task ----------------------------------------- C18 adaptation / C19 TDA
```

Arrows show useful prerequisites and typical data dependencies, not absolute scientific prerequisites. For example, a self-contained simulator can be evaluated without a scene graph, and HDC/KAN source audits can start before C06/C07 are deployed.

## Work packaging and gate rules

Each Cxx item has **its own** four deliverables:

1. `P0-research.md`: problem definition, research/standards and library review, license/dependency review, hardware matrix, interface/reuse plan, baseline candidates, fixed test gates and open decisions.
2. `P1-implementation.md`: code references, dependencies, contracts, unit tests and security boundaries.
3. `P2-smoke.md`: smoke suite, test commands, platform/backend logs, pass/fail/blocked status.
4. `P3-benchmark.md`: preregistered baselines/datasets, held-out results, resource/cost results, reproducibility and explicit promotion decision.

Documents for P1–P3 are created **when work exists**, not as empty placeholders. Completing P3 does not automatically switch a module on for production. No benchmark, compatibility, or security result may be inferred from the existence of a document.

## First execution slice — starting now

- **C01/P0 — active:** source audit of Cognitum's current core and Lu's native tool boundary, standards and mature library research, hardware suitability, and test plan. See [C01/P0](components/core-runtime/P0-research.md).
- **C01/P1 and partial P2 — inherited, not restarted:** `cognitum/contracts.py`, `registry.py`, `runtime.py`, `policy.py`, `tracing.py`, `worker.py`; 31 tests and 12 synthetic replays are *reported by the checked-in handoff*, not rerun during this documentation change.
- **C02/P0+P1/P2 — active safety prerequisite:** [bounded Protobuf worker wire](components/security/P1-P2-protobuf-worker-boundary.md) is implemented and tested, but OS confinement, exact host authorization, quotas, cancellation and native supervisor remain **unverified and fail-closed**. Do not enable effectful/untrusted code.
- **C03/P0 — next cross-cutting prerequisite:** define real-task baselines and telemetry standards; do not relabel synthetic smoke fixtures as P3.
- **C06/C07/P0 — next user-facing cognitive capabilities:** canonical SQLite schema, provenance and state change semantics.
- **C08/C09 — recovered:** exact K4 source/overlay and closure archives located in the ChatGPT Library, hashes confirmed, fresh Linux CPU 41/41 unit tests and 20/20 HDC self-tests passed. [Archive audit](components/hdc-kan/P0-archive-reuse-audit.md). Next: C08/C09 native interface and application-state dependency designs, **not** repeating prior research.

## Priority can change without rewriting phase history

Advance C15/C16 for an urgent, testable film-studio need, or another adapter for a concrete user task. Record justification and dependencies. Freeze an experiment's metrics **before** looking at results. Preserve failed experiments, older source designs, HDC/KAN historical assets, and current production behavior.

**Change scope:** documentation and planning only; no runtime, Lu, archived research, or tests modified by adding this build order.
