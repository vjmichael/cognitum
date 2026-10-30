# ADR — Cognitum is transformer augmentation first

**Decision date:** 2026-10-29  
**Status:** Adopted product and research direction; component implementation states remain separately verifiable  
**Scope:** Cognitum C01–C19, research benchmarks, production eligibility, eventual Lu Core Extension interface  
**Authority boundary:** This is a Cognitum design decision only. Lu model lifecycle, permissions, native CE discovery, tools, storage and user consent remain owned by Lu; no Lu change is authorized.

## Decision

**Cognitum exists to augment the transformer chosen and operated by Lu, specifically by providing external, verifiable, stateful or specialized capabilities where the transformer alone is unreliable, inefficient, ungrounded or inherently unsuitable. Cognitum is not required to outperform conventional algorithms.** Excellent conventional algorithms may be used *as Cognitum capabilities*; making their results correctly available to the model is itself an augmentation.

Examples of transformer gaps: exact arithmetic and units; bounded symbolic/SMT reasoning; durable authorized memory and temporal belief revision; correct optimization/planning under hard constraints; probability/calibration; causal identification and counterfactual assumptions; spatial/temporal identity and physical modeling; provenance, reproducibility and calibrated abstention. A capability that exposes a trustworthy established solver can be valuable even if it implements no novel solver.

Research into alternative algorithms (HDC, KAN, SSM, learned dynamics, meta-learning, topological methods) remains an explicit project goal: probe where they add complementarity, useful representations, new generalization, efficiency under relevant constraints or stronger end-to-end task outcomes. An unsuccessful comparison does **not** invalidate the component's research, the established computational tool, or the augmentation program.

## Acceptance questions, in order

1. **Transformer deficit:** Identify an actual failure or missing affordance of Lu + its selected transformer. Define the specific capability and task; specify what is gained through correct tool selection, formalization, execution, interpretation, verification, provenance, memory or composition.
2. **Capability validity:** Independently establish numerical, logical, scientific, security and semantic correctness under declared assumptions. Return explicit uncertainty, abstention, limits and unsupported cases. Domain validity is not conferred by model confidence or a successful tool envelope.
3. **Safe usable handoff:** Native Protobuf with verified schemas, scoped user/host authority, bounded resources, permissions and cancellation. Preserve one canonical store and do not duplicate Lu's model or agent loop.
4. **End-to-end augmentation:** Compare the same selected model and task **without Cognitum** and **with Cognitum** under comparable settings. Include established methods as reference implementations and baselines where informative, not as opponents Cognitum must outperform. Evaluate task success, faithful interpretation, reliable tool use, calibration, false claims, resource cost and user friction.
5. **Research claims only when substantiated:** Claims that a novel algorithm is more accurate/faster/cheaper than a strong incumbent require a matched, held-out experiment. Failure to beat an incumbent must be reported; it is **not a veto on deploying a correct conventional tool as transformer augmentation**.
6. **Promotion:** Safe/default-on/production-ready status requires its own reproducible security, compatibility, governance, data and cross-platform evidence. An optional research candidate may remain default-off indefinitely. No unreviewed package or component can grant itself host authorization.

## Separate release definitions

- **Developer alpha:** A reproducible runnable test distribution with a deliberately small set of correctly bounded capabilities, clear disabled/deferred modules and diagnostics. Not required to finish all 19 portfolio components or demonstrate novel-algorithm superiority.
- **Lu-integrated alpha:** A separately approved native CE handoff with real Lu host authorization, tool round-trip, cancellation, revocation and model-task smoke verification. This requires Lu-side readiness but never licenses changes to Lu from this repository.
- **Complete component portfolio:** All **19 C01–C19** have their defined minimum first-party Cognitum capability slice implemented, tested, accurately documented, runnable or explicitly gated as a genuinely optional experimental capability, and registered only after authorization. Full portfolio completion is **not** synonym for production certification, proof of safety of every research hypothesis, or all open-ended future specialist expansions.

## Audit: implementation coverage, not completion (2026-10-29)

This inventory combines merged Cognitum `main` with the **unmerged** C15 source checkpoint pull request [#19](https://github.com/vjmichael/cognitum/pull/19). It is not a claim that the source PR has green CI or that code in it ships on `main`. A Protobuf schema, a research-only reference, a generated binding or a test alone does not prove production integration.

| Component | Technology | Evidence tier | Key remaining work |
|---|---|---|---|
| C01 | Contracts, native registry, typed results | Cognitum implementation foundation | Real host registration, lifecycle, authority |
| C02 | Security, permissions, worker isolation | Contract and test foundation | Real approved host OS worker isolation / recovery |
| C03 | Evaluation, tracing, benchmark science | Offline implementation foundation | Real paired Lu + transformer trials |
| C04 | Native Lu CE and compositions | Offline collector/contract foundation | Approved native CE end-to-end invocation |
| C05 | Exact and scientific computing | Executable bounded kernels | Broader specialist coverage, safe integration |
| C06 | Canonical memory/retrieval | Offline host-fenced reference in PR #19 | Host-owned canonical ANSF integration; no competing store |
| C07 | Typed state/belief revision | Offline reference / tests in PR #19 | Authorized persistent state owner and actual revision lifecycle |
| C08 | HDC / vector-symbolic indexing | External archived K4 research | Cognitum typed bridge; scope, invalidation and optional runtime |
| C09 | KAN learned function capability | External archived K4 research | Cognitum typed bridge, OOD fallback, optional runtime |
| C10 | SMT and formal verification | Offline solver adapters in PR #19 | Final host permission/verification, broader fragments |
| C11 | Optimization and scheduling | Offline bounded engines in PR #19 | Worker acceptance and real scheduling workflows |
| C12 | Planning and search | Offline bounded planning engines in PR #19 | Supported host adapters, real problem replay |
| C13 | Probability and uncertainty | Offline reference/optional backends in PR #19 | Reproducible mature backend validation and integration |
| C14 | Causal inference | Offline reference/optional backends in PR #19 | Causal assumption reviews, real-data validation, integration |
| C15 | Spatial objects/scene graphs | Substantial offline research prototypes in PR #19 | Real source provenance, native Windows P13/worker, deployment gates |
| C16 | Physical modeling/learned dynamics | Initial bounded exact-motion reference merged ([PR #26](https://github.com/vjmichael/cognitum/pull/26)) | General physics, ODE solvers and host integration still open |
| C17 | State-space / learned temporal representation | Initial bounded classical Kalman reference merged ([PR #23](https://github.com/vjmichael/cognitum/pull/23)) | Learned SSM, multivariate methods and host integration still open |
| C18 | Meta-learning/adaptation | Design only, purposely deferred | Consented trace governance; build safe optional adaptation |
| C19 | Topological data analysis | Design only | Define task-specific data bridge and build baseline computation |

**Coverage update (2026-10-30):** 15/19 now have identifiable first-party implementations or offline references (C01–C07, C10–C17); 2/19 are historical external research prototypes needing Cognitum bridges (C08–C09); 2/19 remain design-only (C18–C19). Thus **4/19 need a first Cognitum-native implementation or bridge**, and **all 19 still have unfinished breadth, integration or acceptance work**. C16 and C17 count only as *first bounded slices*, not completed physical simulation or learned SSM systems. The earlier October 29 snapshot (13/2/4) is superseded. No component is production-complete based on these counts.

Some C01–C07 evidence is already in `main`; much of C06–C07 and C10–C15 only exists in the unmerged PR #19 source branch. Keep CI, provenance and status tier explicit. Do not misrepresent optional external research as a currently installed Lu CE.

## Supersession

This ADR supersedes older blanket language requiring a proposed method to *beat* a strong conventional solver to qualify as Cognitum augmentation, including the old R01 tool-promotion stop/go. Comparative research remains mandatory **when making comparative claims**; end-to-end transformer-task evaluation remains relevant when promoting a new capability. Conventional tools may be directly wrapped, composed, or served as trusted reference methods.

The P0/P1/P2/P3 lifecycle, hostile-input tests, user-control requirements, consent, signed provenance, source deletion handling, reproducibility and OS security blockers are **not** relaxed by this change.
