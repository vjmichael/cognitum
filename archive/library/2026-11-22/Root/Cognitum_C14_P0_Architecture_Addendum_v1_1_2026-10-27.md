# Cognitum C14 — P0 Architecture Addendum v1.1

**Title:** Causal Inference, Structural Causal Models, Interventions, Counterfactuals, Discovery, and Uncertainty  
**Date:** 2026-10-27  
**Status:** Proposed P0 architecture refinement; design deliverable, not an implementation or benchmark claim  
**Baseline reviewed:** `Cognitum_C14_P1_Structural_Causal_Counterfactual_2026-10-27.zip`; `docs/components/causal/P0-P1-causal-models-and-identification.md`; `proto/cognitum/causal/v1/scm.proto`; `START_HERE.md`; `Cognitum_Engineering_Standard_2026-10-27.md`  
**Preservation policy:** Existing Library checkpoints immutable. Do not alter Lu, GitHub, the existing C14 P1 source, or its wire contract as a consequence of this document alone.

## 1. Purpose and decision

C14 SHALL be a **causal-capability framework**, not a monolithic causal algorithm or an LLM claim-generation facility. Its stable typed boundary SHALL support established causal methods first and explicitly optional research adapters for differentiable/neural causal mechanisms, causal discovery, time-dependent causality, and Bayesian structural causal modeling. C14 SHALL distinguish observational association, identification, estimation, intervention, counterfactual inference, and discovery. Results SHALL preserve mathematical assumptions, epistemic limitations, provenance, and independently checkable evidence. C14 cannot confer real-world authority or action permissions on Lu.

**Implementation distinction:** The source checkpoint already contains a **bounded, functional C14 P1 reference** (exact finite-state SCM, observational/interventional/counterfactual queries, a sufficient backdoor-set check, source-level Protobuf receipts and tests). This addendum is a *retrospective P0 enhancement* and prospective compatibility gate; it does not roll back or re-label that P1 as unimplemented. P2 remains the next recorded development milestone in the source checkpoint.

## 2. Non-negotiable invariants

1. **One typed native boundary.** Internal requests, outcomes, and capability advertisement are Protobuf-native. JSON/CSV are optional **external import/export** formats only; their conversion is validated, bounded, and provenance-labelled. Reuse C01/C03/Lu contracts where they actually exist, without inventing already-generated message types.
2. **Offline-first and modular.** Windows x86-64 is the initial target. Avoid required Docker/WSL and avoid surprise network access. Keep mature and experimental backends separately installable, pinned, permission-scoped, cancellable, and independently disabled. No hidden dependency on a Python runtime on the user's machine; packaging remains a gate, not an assumption.
3. **Host-owned authority.** Lu authenticates, authorizes, supervises and kills work; Cognitum does not self-authorize, alter canonical ANSF memory, or perform physical/external actions merely because a counterfactual estimates a benefit.
4. **No causal overclaim.** A supplied DAG/SCM is an assumption until justified. A statistically discovered edge is not causal ground truth; a failed backdoor test is not a universal proof of nonidentifiability. Valid numerical output under a model is not verification that the model describes reality.
5. **Audit and independent checking.** Reuse request/result digests, versioned backend and model provenance, independent verification receipts, local bounded/redacted metadata-only audit, fixed seeds where relevant, explicit rejection/unknown/timeout/cancel status, and C03 benchmark hooks.
6. **Standards-first dual track.** Mature reference/backend support and experimental research backends share a common semantic contract but not a false promise of identical mathematical scope. Never silently replace a production backend with an experimental one or represent an unsupported query as zero effect.

## 3. Capability taxonomy and semantic boundaries

| Capability | Question answered | Evidence/result requirement |
|---|---|---|
| Observation / prediction | What is associated with or predicted from X? | Conditional distribution; never label a conditional as `do(X)` |
| Graph validation | Is the declared graph admissible for a chosen model class? | Graph type, cycles/lag constraints, variable roles, rejection reason |
| Identification | Does the **stated model and assumptions** identify an estimand? | Estimand, assumptions, method, witness/derivation where available; distinction between failed method and proven nonidentification |
| Estimation | What is the numerical value/range of an identified effect? | Estimator, sample assumptions, diagnostics, uncertainty and data provenance |
| Intervention | What follows from replacing specified structural mechanisms? | `do` versus conditioning, intervention target, mechanism invariance, outcome distribution |
| Counterfactual | What would have happened in the same factual world? | Abduction–action–prediction, shared exogenous world/posterior, factual evidence likelihood |
| Discovery | Which structures are compatible with the data/assumptions? | Candidate graph/CPDAG/PAG, orientation uncertainty, method, stability, dataset/sampling limits |
| Refutation/sensitivity | How sensitive is the result to assumptions or perturbations? | Diagnostic/refuter type, tests executed, thresholds, failure/fragility status |
| Partial identification | What bounds are supported when point identification fails? | Derived bound, assumptions, bounds method; no fabricated point estimate |

### 3.1 Explicit evidence lattice

Represent **calculation outcome** separately from **causal claim status**:

- **Execution:** `SUCCESS | UNSUPPORTED | UNKNOWN/INCONCLUSIVE | TIMEOUT | CANCELLED | DENIED | ERROR`.
- **Inference:** `MODEL_CONDITIONAL | GRAPH_CRITERION_SUFFICIENT | IDENTIFIED_UNDER_ASSUMPTIONS | PARTIALLY_IDENTIFIED | ESTIMATED_UNDER_ASSUMPTIONS | REFUTED_OR_SENSITIVE | NOT_ESTABLISHED`.
- **Source support:** `USER_SUPPLIED_MODEL | SIMULATED_GROUND_TRUTH | OBSERVATIONAL_DATA | RANDOMIZED_OR_INTERVENTIONAL_DATA | DISCOVERED_CANDIDATE`.
- **Assurance:** numerical exactness, statistical validity under given assumptions, independent verifier success, and externally verified real-world causality are **different dimensions**. A source-supplied label is never host-authentication or independent proof.

The existing `EXACT_MODEL_RESULT`, `BACKDOOR_CERTIFIED`, `ASSUMED_SCM_EXACT`, and `BACKDOOR_GRAPH_CRITERION` retain their *current bounded meaning*. Any expansion shall add correctly scoped fields/messages or a versioned package; existing statuses MUST NOT be reinterpreted.

## 4. Forward-compatible causal representation

### 4.1 Variables

Support typed descriptors for **endogenous / exogenous / latent / observed / proxy / selection / intervention / outcome** roles; scalar discrete, count, continuous, categorical and vector-valued domains; units, dimensions, legal bounds, missingness and measurement/error models. A role may depend on the query (e.g., treatment vs outcome) and shall not be conflated with whether a variable is observed. Time-indexed variables need clock definition, sample period, timestamp/lag semantics, irregular sampling and window bounds.

### 4.2 Graph families

- `DAG`: fully directed acyclic graph appropriate for static SCMs.
- `CPDAG`: equivalence class of Markov-equivalent DAGs; do not arbitrarily orient unresolved edges.
- `PAG`: partial ancestral graph expressing possible latent confounding/selection and unresolved edge endpoints; preserve endpoint marks and ambiguity.
- `TEMPORAL_GRAPH`: lagged, time-indexed links, possible self-dependence across time, regime/missingness metadata. Require explicit policy for contemporaneous edges; lagged feedback is not the same as an instantaneous directed cycle.
- `LATENT_CONFOUNDED_SCM`: exogenous shared causes and/or appropriately typed latent confounder representation. Do not silently drop latent nodes during identification.
- `CYCLIC_EQUILIBRIUM` or continuous-time systems: **future explicit research model kinds only** with their own well-posedness/solver semantics; never accept them through static DAG validation.

Graph structure must carry a provenance source (`user_asserted`, `physics_specified`, `expert_reviewed`, `interventional_data`, `algorithm_discovered`, etc.), confidence or equivalence-class uncertainty if validly defined, and explicit assumptions. An LLM-generated graph is a *hypothesis* pending examination.

### 4.3 Structural mechanisms

Define an extensible **mechanism descriptor**, not a universal `function_outputs` table: finite lookup tables (existing exact P1), linear/generalized-linear functions, additive-noise and nonlinear mathematical expressions, piecewise/physical mechanisms, stochastic conditional kernels, differentiable/neural mechanisms, and time-dependent/stateful transition mechanisms. Future backends may use tensors, model weights/checkpoints, parameter priors/posteriors and internal precision descriptors. Execution of arbitrary expressions or model code is **disabled** unless Lu hosts an explicit isolated, pinned and authorized backend. Data and model digests/handles are preferred to embedding large private blobs in audit.

### 4.4 Model-family and support negotiation

A capability descriptor SHALL advertise model kinds, domain types, graph families, estimands, operations, numeric precision, algorithm/version, determinism, training need, data access mode, maximum size/resources, assurance modes and known limitations. A request is rejected as `UNSUPPORTED` if its semantics exceed that descriptor. Experiment-only methods default off and require host approval. No implicit downgrade from nonlinear/temporal/Bayesian to finite-state static lookup semantics.

## 5. Required research-extension hooks

### 5.1 Differentiable causal models

Provide optional differentiable-mechanism interfaces for parameter tensors, constrained structural functions, gradient availability, optimization metadata, loss/objective, optimization convergence and acyclicity diagnostics. Gradients may enable learning but do not certify a causal interpretation. Preserve the contrast between an assumed SCM mechanism and learned structure. Candidate references: NOTEARS (continuous DAG optimization) and neural SCM research; neural implementation is an optional backend, not an assumed dependency.

### 5.2 Neural causal discovery

Discovery shall return a **candidate graph or equivalence class** plus orientation uncertainty, dataset assumptions, latent confounding policy, intervention knowledge, scoring/conditional-independence tests, stability across seeds/subsamples and confidence calibration when justified. Support PC, FCI, GES baselines before experimental neural discovery. Include a controlled **propose → validate → challenge/refute → optionally adopt under explicit authority** workflow. Discovery alone cannot rewrite the canonical SCM, grant action authority, or certify identification.

### 5.3 Temporal causal inference

Provide lag-indexed graphs and temporal dataset contracts, support for time units and sampling, nonstationarity/regime changes, autocorrelation, time-varying confounders, delayed effects, and feedback through time-unrolling. Distinguish forecasting, time-series Granger-type predictive dependence, structural temporal causality, and dynamic intervention effects. Reference PCMCI/PCMCI+ (Tigramite) as a discovery baseline with explicit assumptions. A physics/simulation engine remains independently responsible for actual dynamics and conservation constraints.

### 5.4 Bayesian structural causal models (C13 interoperability)

Define an optional adapter between C14 causal models and C13 probability/Bayesian inference **after verifying actual schemas and execution semantics**. Represent priors/posteriors over mechanism parameters, exogenous disturbances, and optionally graph structures; track inference engine, likelihood, sample diagnostics, posterior sample ids/weights and convergence metrics. Distinguish uncertainty due to stochasticity, parameters, graph ambiguity, sampling, measurement and missingness. A frequentist confidence interval and a Bayesian credible interval are not interchangeable. `P(Y | X=x)`, `P(Y | do(X=x))` and `P(Y_do | X=x)` must remain separately named query/result types; no shared type should blur conditioning, intervention and abduction.

### 5.5 Research reserve beyond the first four

Reserve capability descriptors (not obligatory P1 implementations) for partial identification and causal bounds, frontdoor/IV/general identification, mediation and path-specific effects, soft/stochastic/policy interventions, transportability/domain shift, multi-environment causal robustness, causal representation learning, measurement/selection bias, optimal experimental design, and sensitivity to hidden confounding. Experimental work is research-labelled and independently disableable.

## 6. Baselines, adapters, and interoperability

| Reference candidate | Intended scope | P0 decision / caution |
|---|---|---|
| Exact C14 P1 finite-state engine | Golden observable/intervention/counterfactual examples; independent arithmetic checks | **Retain unchanged**, expose as `reference/exact_discrete`; it does not estimate effects from raw datasets |
| NetworkX | Graph checks and independent d-separation verification | Already used in P1 checkpoint; not a general causal identification engine |
| DoWhy / PyWhy | Identification, effect estimation, refutation, GCM | Assess version, license, Python dependency packaging, Windows x86-64, safety and isolation; optional adapter, not declared running |
| EconML | DML, CATE and heterogeneous treatment effects | Estimation requires identification assumptions; separate P3 adapter |
| causal-learn | PC, FCI, GES and other discovery | Preserve CPDAG/PAG ambiguity and assumptions; separate P3 adapter |
| Tigramite | Time-lagged/contemporaneous causal discovery | Optional temporal capability; validate stationary/conditional-independence assumptions and computational budgets |
| NOTEARS-family / neural SCM | Differentiable constrained structure learning | Experimental, pinned, reproducible, separately benchmarked and disabled by default |
| C13 probabilistic inference | Prior/posterior computations and uncertainty | Reuse **only after real schema and semantic compatibility tests**, no parallel independent Bayes core |

A backend library's adoption is contingent on current release/maintenance, license/redistribution rights, pinned transitive dependency review, deterministic behavior disclosure, data-handling checks, offline Windows packaging, C02 security, cancellation and independent tests. A library paper or website is not evidence of a successful runtime integration.

## 7. Protobuf compatibility and lifecycle

The shipped `cognitum.causal.v1` includes `StructuralCausalModel`, `ExogenousVariable`, `EndogenousVariable`, `CausalRequest`, `CausalResult`, `CausalReceipt`, `CausalAudit` and bounded query enums. **Do not recycle tags, reinterpret existing statuses, or change the exact finite-state reference semantics.** Introduce additive optional fields/messages only when safe; use a versioned `cognitum.causal.v2` package for incompatible graph/float/tensor/temporal semantics. Include unknown-enum handling and explicit feature-negotiation across hosts and workers. Model-specific request payloads should be typed oneofs or separate typed operations rather than unbounded polymorphic bytes.

**Logical future contracts (not yet generated symbols):** `CausalCapabilityDescriptor`, `CausalModelDescriptor/Handle`, `GraphSpecification`, `StructuralMechanism`, `ObservationDatasetRef`, `InterventionSpecification`, `CounterfactualSpecification`, `EstimandSpecification`, `IdentificationOutcome`, `EstimationOutcome`, `DiscoveryOutcome`, `CausalAssumptionSet`, `CausalUncertainty`, `CausalVerificationReceipt`, `CausalRunManifest`, and `CausalBackendSelector`. Reuse existing generic capability/request/outcome/receipt envelopes rather than duplicate their trust semantics.

Authenticated Lu scopes, request ids, budgets, cancellation and audit correlation are supplied by the trusted host, never authorization claims in model/dataset inputs. A model/dataset handle must be bound to host identity, permissions, digest, schema, exact backend, and limited lifetime when applicable.

## 8. Evidence, privacy, reliability and security gates

- **Data governance:** explicit dataset provenance and permissions; role declarations (treatment, outcome, confounders, mediators, colliders, instrument, selection, proxy); sample populations, sampling scheme, missingness mechanism, data leakage/measurement caveats and intervention availability.
- **Statistical diagnostics:** positivity/overlap, identification assumptions, sample size/effective sample size, covariate balance where applicable, held-out diagnostics, convergence and numerical conditioning, uncertainty estimator identity, sensitivity/refutation; return `UNKNOWN/UNSUPPORTED` if tests are unavailable rather than fabricate validity.
- **No unsafe automation:** causal evaluation cannot itself trigger real-world or user-state changes. Physical/medical/legal/financial recommendations require appropriate user oversight; any action requires separate Lu permissions and policy checks.
- **Security:** C02 OS confinement remains unresolved. Optional Python/native/ML backends are untrusted workloads: resource quotas, memory bounds, cancellation, filesystem/network permissions, restricted loading of weights and code, backend binary digest and process isolation; disabled if enforcement unavailable.
- **Audit:** metadata-only by default; request/result hashes are not privacy boundaries. Keep raw measurements, prompts, proprietary documents and personal data out of audit unless independently authorized. Independent verification receipts may certify arithmetic or graph algorithm execution but never automatically certify the truth of a causal graph.

## 9. Benchmark and verification specification

**Start with focused offline mathematical tests; defer major comparative/hardware/real-model campaigns** under the Cognitum engineering standard. Reuse C03 hooks and C13 only after actual schema checks; log exact method, library/version, fixture digest, random seed, resource budget, hardware/platform, failure states and distinct time/memory measurements.

**Mandatory fixture families for subsequent work:**

1. Static DAG cycle and invalid variable/parent/noise checks; canonical topological order.
2. Observational vs `do` on a confounded SCM, with non-equality where appropriate.
3. Shared-exogenous abduction–action–prediction and impossible evidence failure.
4. Sufficient backdoor-set passes and fails, with *method insufficiency* distinguished from global nonidentification.
5. Confounding, collider bias, selection, hidden causes, measurement error and positivity failure cases.
6. Frontdoor/IV/multiple adjustment paths and valid/invalid assumption counterexamples (when adapters implemented).
7. CPDAG/PAG uncertainty: no arbitrary direction/promotion to a DAG or estimated effect.
8. Temporal lag, delayed intervention, irregular sampling, feedback via time, nonstationarity and time leakage (when temporal adapters implemented).
9. Bayesian posterior recovery, credible interval semantics, parameter/graph uncertainty and C13 cross-module consistency (when implemented).
10. Differentiable gradient/acyclicity/optimizer constraints, multi-seed stability and failure cases (when research adapters implemented).
11. Deterministic reproducibility; stochastic run seed/provenance; numerical tolerance declaration and independent reference checks.
12. Malformed Protobuf, unauthorized host identity, excessive budget, disabled experiment, timeout/cancellation, and verification corruption fail-closed.
13. Backward `cognitum.causal.v1` replay and unchanged 26 focused C14 P1 tests, six smoke checks and schema regression; only claim new passing evidence after running it.
14. Windows x86-64 packaging, authenticated Lu native call, C02 OS security, benchmark-runner interoperability and optionally signed native backend verification as distinct **pending** gates.

Benchmark reports SHALL distinguish synthetic ground truth from real-world observational results, exact-model numerical correctness from causal identification, and confidence/credible intervals from theoretical causal guarantees. A comparison must use equivalent questions, available data, estimator conditions and budgets; raw speed scores without validity are not evidence of causal quality.

## 10. Phase mapping and change-control gate

- **C14 P0 (this amendment):** Record and review foundational types, method taxonomy, evidence lattice, research tracks, interoperability plan, baselines, security/benchmark requirements and open decisions. The P0 revision itself requires *no source overwrite*.
- **C14 P1 (already present in reviewed checkpoint):** Exact discrete SCM, observational / intervention / counterfactual, sufficient backdoor test, Protobuf and focused tests. Retain validated bounded semantics. Perform a **retrospective compatibility gap assessment** against this amendment before modifying the schema.
- **C14 P2 (next per checkpoint):** Mature identification, observational treatment-effect estimation and refutation through optional pinned DoWhy and independently testable reference cases; include positivity, bias/uncertainty and admission policy.
- **C14 P3 (per checkpoint):** Optional EconML heterogeneity estimators and causal-learn PC/FCI/GES discovery with candidate/evidence segregation.
- **C14 P4 / subsequent research phases (proposed scope):** Partial identification/bounds, transportability, soft/policy interventions, temporal causal models (Tigramite), differentiable/neural models, Bayesian SCM-C13 bridge. Prioritize with research dossiers and practical testability; do not declare these done just because extension points exist.

**P0 amendment acceptance checklist:**

- [x] Named standard and experimental capability families, without falsely claiming installed backends.
- [x] Separate semantics for observation, intervention, counterfactual, discovery, identification, estimation and bounds.
- [x] Conceptual future-ready graph, mechanism, temporal, Bayesian and latent-variable representations.
- [x] Protobuf v1 preservation and versioning policy.
- [x] Lu security / no unauthorized causal action; privacy and audit policy.
- [x] C03/C13/C02 compatibility and verification *requirements* defined.
- [x] Mature-library and research-reference shortlist.
- [ ] Formal migration matrix against current source `.proto` (design review required).
- [ ] Backend license, maintenance, Windows packaging and ABI checks with exact versions/commits.
- [ ] C13 and C03 actual wire interop tests and C02 authenticated host OS gates.
- [ ] P2+ implementations, focused tests for new methods, and real-world validity evaluations.

**Open questions, nonblocking at P0:** Default causal graph adoption policy (proposed: manual/explicit host authorization); first supported continuous-mechanism family (proposed: linear additive-noise); whether time is regular-grid or irregular first (proposed: explicit clock/lag model, regular-grid baseline); Bayesian graph posterior representation (proposed: weighted candidate graphs with typed model identifiers). These are research/implementation decisions to document at the phase where they become executable.

## 11. Reference sources consulted

- DoWhy causal tasks and GCM: https://www.pywhy.org/dowhy/v0.14/user_guide/causal_tasks/index.html
- EconML user guide: https://econml.azurewebsites.net/
- causal-learn documentation: https://causal-learn.readthedocs.io/en/latest/
- Tigramite (PCMCI / PCMCIplus): https://jakobrunge.github.io/tigramite/
- NOTEARS (NeurIPS 2018): https://papers.nips.cc/paper/2018/hash/e347c51419ffb23ca3fd5050202f9c3d-Abstract.html

**Verification note:** This file was authored from the reviewed Library project checkpoint and public documentation; it does not mutate Cognitum source, produce new generated Protobuf, re-run existing tests, install adapters, or claim an authenticated Windows/Lu integration. The existing C14 P1 numerical test counts are reported from prior checkpoint evidence, not tests freshly executed here.
