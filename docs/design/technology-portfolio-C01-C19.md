# Cognitum Revision 1.5 — AI Technology Portfolio C01–C19

**Status:** complete component-level **design**, not a claim that every technology is implemented. **Governing 2026-10-29 decision:** [Cognitum augments the Lu-selected transformer; beating conventional tools is not a universal release prerequisite](ADR-augmentation-first-transformer-capabilities-2026-10-29.md). These cards retain historical \"Current\" snapshots; see the ADR's explicit implementation coverage audit (including the unmerged C15 source branch). This is the functional companion to the [architecture](../Cognitum_Comprehensive_AI_Architecture_R1_5.md) and [research and delivery program](research-validation-and-delivery.md).

**Global rules for every card:** typed canonical Protobuf inputs/outputs; Lu-host authorization and permission scope; no new independent transformer/agent loop; bounds and graceful missing-component errors; separate execution/domain/assurance/intent labels; exact canonical sources under one agreed owner; disabled-by-default research challengers; P0→P1→P2→P3 with strong baselines and whole-task metrics. Labels **Implemented/P2** and **Designed/P0** must not be interchanged.

## C01 — Contracts, native registry and cognitive result semantics

**Current:** Implemented and CI-tested Cognitum typed outputs, Protobuf capability messages, registry/diagnostics and inert Lu handoff; host-integrated registration **pending**.

**Question:** Can Lu expose specialist computation without ambiguous meaning, privilege escalation, inconsistent versioning or a competing tool loop?

**P0 design:** CapabilityDescriptor includes stable family/name/version, exact input/output descriptor SHA/type URLs, reviewed user-facing use/avoid rules, status/outcome/assurance/evidence conventions, mandatory limitations, resource effects and scopes, privacy policy, dependency graph, timeout and advertised/active state. Reject absent/unknown type URL, unsupported version, hidden capability dependencies, semantic drift and forged host-owned approval bits. The true host envelope remains lu.v1.ToolCall/ToolReply.

**P1:** Keep thin Protobuf validation, strict canonical wire where contract requires it, subtype-specific semantic checking and deterministic error mapping. A failed result should never be coerced into a valid zero or success. Include separate optional namespace for future schemas; preserve deprecated field numbers.

**P2:** Invalid fields, duplicate known-field shadowing, out-of-range numeric values, mutated descriptors, disabled-plugin startup, partial module failures, rollback, cancellation and deterministic model-visible catalog. Run on supported desktop OS targets. No model-invoked execution implied by unit tests.

**P3:** Compare direct Lu tools and small family catalog versus grouped Cognitum specialists under the **same selected model and tool budget**; measure end-task success, wrong tool, invalid args, token overhead and p95 latency. Do not promote a router only because dispatch microseconds are lower.

**Hardware:** CPU/reference-first; performance bottleneck is model/host routing and validation, not a GPU kernel. FPGA acceleration is not a justified P1 prerequisite.

## C02 — Security, scoped permissions, OS worker and trust

**Current:** Cognitum Protobuf worker, security acceptance and signed-claim formats are tested; **production worker gate closed**. Newer Lu draft branch demonstrates real diagnostic Windows and Linux worker isolation tests and Linux signed CE tests. No completed Cognitum-specific production integration has been established.

**Question:** Can hostile or faulty optional code execute without seeing forbidden filesystem, network, handles, credentials, adjacent Workspaces or unrelated Lu processes?

**P0:** Threat actors include model prompt injection, forged package publisher, compromised worker/plugin, malicious file/import, stale grant and tampered IPC. Assets include Lu session identity, user files and private context, system tools and source models. Require publisher identity, durable revocation/rotation/recovery, prompt/desktop user-consent binding, mandatory typed effects and permissions, bounded process tree, no unsigned fallback.

**P1:** Lu, not Cognitum, must implement actual boot, authenticated channel, native resource broker, cancellation and OS sandbox. Cognitum only supplies typed restricted operations, deny-by-default ability declarations and test harnesses; it must not issue its own grants. On Windows evaluate AppContainer/LPAC and kill-on-close Job Objects; on Linux namespaces/seccomp/cgroups/broker; on macOS Seatbelt or proven equivalents. Avoid assuming a platform capability exists where it has not passed hostile-worker tests.

**P2:** Independently attempt private-file reads, writes/reparse/symlink escape, DNS/loopback egress, inherited-handle access, child breakaway, CPU/RAM saturation, worker crash, grant revocation mid-call, late results, restart and publisher-key removal. Check trace secrecy and unrelated Workspaces survival. Test signed packages separately from trusted diagnostic workers.

**P3:** Acceptance is a **security gate**, not a marketing performance benchmark. Residual risk and platform matrix must be signed off before untrusted/effectful CE installation. Monitor latency and energy of confinement only after isolation works.

**Hardware:** OS feature support matters more than accelerators; GPU handle sharing itself is a high-risk brokered resource.

## C03 — Evaluation, tracing and benchmark science

**Current:** Native Protobuf synthetic evaluation and paired A/B/C/D plan/capture shape contracts, including presence-aware resource fields, pass CI. **No real Lu+model paired trials yet**.

**Question:** Does an augmentation change validated user-task outcomes enough to offset security, time, memory, maintenance and model-context costs?

**P0:** Freeze dataset/gold truth/rubric, Lu build, selected model artifact hash, quantization, prompting/model context, hardware, permissions, catalogs and repeats before experiments. Distinguish development, held-out and adversarial sets. Explicitly score correct abstention and unnecessary tool use.

**P1:** Typed BenchmarkPlan and BenchmarkCapture, evaluator identity, independent trusted collector, case/outcome/error schemas and run-level trace correlation. A/B/C/D comprise host-only, strong conventional tool, a candidate specialist, and a genuine declared composition. Unavailable arms report NOT_RUN, never fabricate data.

**P2:** Tampered plan/capture/receipt, noncanonical Protobuf, missing seed/repeat, truncated report, absent sensors and forged success; CI is required but does not certify actual host metrics.

**P3:** Paired end-task comparisons with confidence intervals, per-class failures, p50/p95 latency, peak RAM/VRAM, tokens, energy (sampled integrals with idle matched) and explicit decision based on preregistered thresholds. Primary outcome must reflect a **real user need** rather than a kernel microbenchmark.

**Hardware:** Reproducibly identify accelerator, driver, thermals, warmup and CPU fallback.

## C04 — Native Lu/Core Extension integration and composition

**Current:** Cognitum signed-collector receipt verifier is tested offline; no actual model/run collector or approved Cognitum CE installed.

**Question:** Can Lu's chosen model call a vetted specialist and use the result correctly without a duplicate runtime, UI or memory store?

**P0:** Read Lu current contracts before every integration change. Freeze approved CE package manifest, exact effect-free vs effectful mapping, typed operation IDs, negotiation, model-visible descriptions, response codecs, health, installing, disabling and revocation semantics. Lu's desktop user-confirmation controls remain host-only; separate full Workspaces keep independent tool registries.

**P1:** Propose a minimal **host-owned** native adapter for one bounded calculator operation, with metadata-only trace and strict ToolCall/ToolReply domain payload validation. Do not hardwire to one model/provider or require MCP. Composer builds a Lu-controlled typed DAG with explicitly scoped edges and no hidden sub-tool invocation.

**P2:** Genuine host user-turn approval vs forged assistant-generated consent; supported/unsupported model tool calling; version mismatch; canceled tool, worker unavailable, unloaded CE, key rotation; workspace install/uninstall and recovery without disrupting unrelated components.

**P3:** Same selected transformer with and without an approved Cognitum tool, measured by independent final-answer grader and actual host telemetry. Report model-visible context pressure and wrong tool selection.

**Hardware:** Cognitum capability may be CPU/GPU/FPGA-backed independently of model execution; device handle allocation must be host-brokered.

## C05 — Exact and scientific computing

**Current:** Exact bounded Fraction calculator and six disabled scientific kernels are implemented and P2-tested; see previous C05 reports. Broad CAS, general optimization and scientific simulation **not yet implemented**.

**Question:** Can Lu reliably formalize problems into safe, accurate numerical/symbolic computations and interpret the answer appropriately?

**Supported first slice:** exact rational arithmetic; degree≤6 univariate polynomial expand/derivative; real sin/cos/exp/log/sqrt to bounded significant digits via optional mpmath; Decimal add/divide/sqrt to 256 digits; exact ≤4×4 rational determinant/product/solve; bracketed real polynomial bisection; ≤256-step discrete harmonic oscillator. Six C05 math specialists have typed Protobuf requests/results and an **inert** developer-authored catalog, not live model tools.

**Next P0 design:** Separate domains and assurance classes: exact integer/rational, symbolic identity, finite-precision approximate, interval or error-certified, physical dimensioned, measured stochastic and uncertified simulation. Establish safe AST-to-symbolic object construction if adding SymPy; never feed raw model text to eval-oriented parse APIs. Consider mature mpmath, SymPy, NumPy/SciPy as optional engines *only where better than a safe incumbent*.

**P1 future:** Polynomials in multiple variables and symbolic factorization/integration within bounded grammars; complex/special functions; interval arithmetic; sparse/dense matrix operations; eigenvalue problems; constrained root finding; trustworthy dimensions; multiple numerical integrators and event detection. Each needs a separately versioned Protobuf operation and explicit computational budget.

**P2:** Identity/golden tests, independent/reference libraries or property-based checks, conditioning and singularity failures, inverse/pseudoinverse distinctions, overflow/underflow, unit/domain mismatches, cancellation/resumption where meaningful, convergence-vs-failure labels and adversarial parser inputs.

**P3:** Compare the same model's use of C05 with a competent built-in Python/standard-calculator/SymPy/SciPy alternative on held-out word problems, not just already-formalized equations. Score task formalization and units separately from computational kernel accuracy.

**Hardware:** CPU exact arithmetic and small matrices by default; only test BLAS/GPU at sizes where transfer/runtime overhead is amortized. Arbitrary precision may not benefit from consumer GPUs.

## C06 — Canonical memory, search and retrieval

**Current:** Design only; no new Cognitum canonical memory store approved.

**Question:** Can Lu recover correct, current, authorized evidence across long histories and many files while honoring corrections and deletions?

**P0 ownership decision:** Audit Lu's ANSF and any connected project/workspace stores; choose a **single canonical owner** before coding. Cognitum's proposed interfaces are MemoryQuery(scope, time_filter, structured_subjects, evidence_limit), MemoryEvidence(source_id, revision, access_scope, valid_interval, citation_handle, freshness), IndexStatus(snapshot_id, origin_revision, staleness), and MemoryMutationProposal (host approval required). All native Protobuf; never allow Cognitum to mint user identity.

**P1 incumbent:** SQLite transactional canonical records and FTS5/BM25 baseline (or Lu's existing equivalent) plus optional semantic embedding/binarized index, exact source ID lookup, provenance and source-revision reconciliation. Model memory is not the source of truth. Derived indexes are rebuildable, versioned, scope-filtered and deleted on canonical tombstone; use explicit LRU/caching with invalidation.

**P2:** Recall across homonyms, stale index, cross-workspace/access denial, deletion/restore, restart, partial transaction/reindex, corrupted metadata, huge corpus and task recency. Imported malicious instructions must be treated as quoted data, not tool policy.

**P3:** Competent FTS/BM25, dense/binarized+rescore, exact key lookup and graph query baselines; evaluate citation correctness, updated-claim accuracy, temporal and multihop retrieval, p95 latency, incremental index cost and deletion leakage. Negative HDC retrieval pilot is not erased.

**Hardware:** CPU SQLite/BM25 first; GPU embeddings only if batching/corpus scale and cost justify; investigate binary SIMD/FPGA for HDC indexing as an experiment, not canonical storage.

## C07 — Typed state, claim revision and temporal belief reconciliation

**Current:** Design only; C06 ownership is the blocking dependency.

**Question:** Can Lu distinguish its present commitments from prior superseded choices, unverified assertions and conflicting evidence without silently overwriting history?

**P0 schema:** StateEvent(event_id, entity, predicate, typed_value, origin, actor_authority, expected_revision, effective_time, recorded_time, action), with action ASSERT/CONFIRM/CHALLENGE/SUPERSEDE/RETRACT/EXPIRE/MERGE; BeliefRecord(id, status, source_refs, scope, conflict_edges, valid_from/to, revision). Keep **user decision**, imported claim and model hypothesis distinct. Facts are not true merely because they were saved.

**P1:** Atomic versioned event writer, materialized current-view derivation, cross-chat consistency resolver, negative evidence/conflict notices, explicit human-in-the-loop policy for consequential changes. Integrate with Lu's ANSF revision chains rather than creating competing memory. Exactly-once effect at store boundary via idempotency keys and expected revision.

**P2:** Reversal after long conversation, topic switch falsely labeled contradiction, concurrent writers, out-of-order events, rollback/restart, stale confidence, expired claims, deletion/tombstone propagation and hostile sources.

**P3:** Compare Lu's existing revisioned knowledge system and simple event-sourced state baseline; grade up-to-date response accuracy, correct uncertainty, contradictory updates and user-friction/time. An SSM challenger is **not** baseline state correctness.

**Hardware:** CPU transactional store, no learned accelerator by default.

## C08 — HDC / vector-symbolic relational indexing

**Current:** Original K4 HDC archive and opt-in overlay hash-verified/retested; **not a Cognitum production plugin**. Original retrieval pilot includes negative results relative to competent baselines.

**Question:** Do bounded hypervector binding/bundling/unbinding and cleanup retrieval improve incremental relational multi-hop reasoning, noise tolerance or energy efficiency beyond exact graphs and lexical/dense retrieval?

**P0:** Reuse archived BSC/MAP/FHRR/HRR kernels after license/provenance audit. Distinguish bipolar XOR/Hadamard/circular convolution families; do not assume arbitrary Gaussian multiplication is self-inverse. Schema: IndexBuild(snapshot_id, representation_family, dimension, encoder_version), RelationBind(entity IDs, typed relation, revision), RelationQuery(constraints, top_k), Candidate(canonical_record_id, score, cleanup/uncertainty), Staleness/invalidations. No natural-language meaning is automatically contained in random hypervectors.

**P1:** Canonical Lu state → explicit encoder → derived HDC index with version/source mapping → exact authorization and source revision recheck on hit. Source ledger stays outside the hypervectors; deletion invalidates all affected bindings/cleanup caches.

**P2:** Algebraic unbinding and capacity tests, collisions, noisy aliases, multi-hop composition, update/delete under concurrent use, stale index denial and reconstruction against exact store. Preserve archived 41-unit and 20-selftest evidence as **CPU prototype** results only.

**P3:** Strong SQLite FTS5/graph, BM25, dense and binarized+rescore controls; measure relational end-answer accuracy, update complexity, memory/energy, false matches and synergy with C07 event-state context. No unconditional HDC retrieval win.

**Hardware:** CPU packed bitwise baseline; GPU/FPGA batch hypothesis to compare encoding and transfer latency. Archived K4 remains unmodified.

## C09 — KAN / learned symbolic-function challenger

**Current:** Portable NumPy KAN, trainable variants and optional depth overlay recovered/tested as historical separate research; **not an exact calculator** and not integrated into Cognitum.

**Question:** Can KAN learn compact interpretable functions, or act as a bounded solver/simulator surrogate, with better held-out behavior, inference cost or formula recovery than strong conventional approaches?

**P0:** Typed FitRequest(dataset_split_ids, function_family, input units, resource budget), ModelArtifact(checkpoint hash, architecture, preprocessing, training manifest, license), PredictRequest(model_hash, values, OOD envelope), PredictResult(approximate values, model uncertainty, domain check, escalated_to_exact). Training and inference are separate privileges; no automatic model-weight changes to Lu's transformer.

**P1:** Reuse and pin K4 trainable/portable artifacts; default-off extra depth; versioned feature bridge from canonical numeric data, never a universal vector field. Train with documented seeds and held-out functions. OOD detection may force exact solver fallback.

**P2:** Checkpoint validation, schema drift, deterministic/preprocessing fingerprints, load/unload/restart, NaN/overflow, resource limits, extrapolation warnings and isolated hardware modes.

**P3:** Compare PySR or domain symbolic regression, B-spline MLP, ordinary MLP/interpolation and exact incumbent solver. Score expression recovery, error, complexity, OOD refusal, training energy and whole-task latency; composite KAN-surrogate effects separately.

**Hardware:** CPU portable inference first; measure GPU training and large-batch benefits explicitly, including model transfer and power.

## C10 — SMT, constraint solving and formal proof

**Current:** Design only.

**Question:** Can a typed formal question be checked with independently verifiable witnesses/counterexamples rather than model confidence?

**P0:** Scoped operation VerifyConstraints(formula_ast, logic_fragment, timeout, proof_required, symbol_table, units). Outcomes SAT(witness), UNSAT(proof/certificate if available), UNKNOWN, TIMEOUT, MODEL_INVALID, UNSUPPORTED. Transport success is not a proof. **Natural-language-to-formula mapping is independently risk-checked.**

**P1:** Use established Z3/cvc5 for bounded SMT; optional Lean/checker artifacts for independently replayable proofs where justified. Avoid unrestricted generated scripting as primary parser; bound formula nodes and solver threads.

**P2:** SAT witness reevaluation, UNSAT claims under omitted constraints, UNKNOWN/timeouts, quantifier theory limitations, overflow/bitvector-vs-integer distinction, inconsistent units, unsound simplification and parser injection.

**P3:** Compare Lu alone and competent conventional solver; evaluate formalization and useful final task resolution, proof/check overhead and abstention. Never describe unchecked UNSAT as certified.

**Hardware:** CPU mature solver; GPU/FPGA not justified as default for branch-heavy SMT.

## C11 — Combinatorial optimization and scheduling

**Current:** Design only.

**Question:** Can Lu derive a correctly constrained feasible or optimal schedule/assignment with honest solver bounds and assumptions?

**P0:** OptimizeRequest(domain_model, variables, hard_constraints, soft_objective, units, time_limit, scaling, proof_gap), OptimizeResult(status FEASIBLE/OPTIMAL/INFEASIBLE/UNKNOWN/TIMEOUT, solution, objective, bound, integrality_gap, validation). No invented optimum after interrupted search.

**P1:** OR-Tools CP-SAT for integer assignment/scheduling; HiGHS for LP/MIP as appropriate. Exact constraint compiler or audited structured builders, bounded size and independent candidate feasibility checker.

**P2:** Conflicting constraints, objective scaling errors, overflow, bad units, infeasible instances, timeouts, canceled incumbent, and distinction between incumbent feasible solution and certified optimality.

**P3:** Matched standard solver controls and Lu's existing tools; objective quality, constraint violations, solver time, bad-model cases and user satisfaction for real scheduling tasks.

**Hardware:** CPU standard first; GPU/FPGA for large specialized linear algebra only if measured benefits and correctness maintained.

## C12 — Planning, search, MCTS and dynamic programming

**Current:** Design only.

**Question:** Can explicit states/actions/preconditions produce plans that actually satisfy goals, recover from invalid assumptions and avoid hallucinated preconditions?

**P0:** Typed PlanProblem(initial_state, goal, action_schema/preconditions/effects, horizon, cost, risk_budget), PlanResult(plan_steps, predicted_state, validation_trace, optimality_claim, uncovered_constraints). MCTS is a **search heuristic** with no automatic optimality guarantee; DP needs suitable state decomposition.

**P1:** Start with deterministic graph search/BFS/A*/DP or established PDDL planners; only add MCTS when branching/stochastic rollout structure justifies it. Use a host-controlled action simulator, never execute real-world writes during search.

**P2:** Invalid preconditions, nondeterministic outcomes, cycles, repeated states, unreachable goal, partial plan, timeout/interrupt, state explosion and untrusted action effects.

**P3:** Compare approved Lu planner and conventional PDDL/OR-Tools/A* controls with exact plan-validator checking; measure success, cost, recovery, state expansions, energy and mis-execution risks.

**Hardware:** CPU priority queues/dynamic programming reference; GPU rollout only for sufficiently batched bounded tasks.

## C13 — Probability, Bayesian inference and calibrated uncertainty

**Current:** Design only.

**Question:** Can Lu perform explicit probabilistic updates with faithful assumptions and calibrated uncertainty instead of verbal probability guesses?

**P0:** ProbQuery(model_id, priors, likelihoods, independence/conditional assumptions, evidence, query), ProbResult(distribution, normalization, credible intervals, calibration provenance, unsupported assumptions). Separate aleatoric, epistemic and numerical uncertainty; avoid user-invented confidence being treated as calibrated.

**P1:** Analytical Bayes for small models, scipy.stats and pgmpy-style Bayesian networks as optional mature baselines. Check probability bounds and evidence consistency; require provenance of priors.

**P2:** Base-rate inversion, dependent-evidence double counting, zero-probability events, contradictory evidence, numerical underflow, impossible model and false causal inference.

**P3:** Ground-truth labeled probability tasks and proper scoring rules (Brier/log loss) plus calibration ECE/reliability and decision utility. Compare no-tool model and standard analytical/library workflow.

**Hardware:** CPU small inference; GPU large probabilistic simulations only after scale and precision study.

## C14 — Causal inference, interventions and counterfactuals

**Current:** Design only.

**Question:** Can a requested causal effect be **identified** from the available data and assumptions, or must the system abstain?

**P0:** CausalQuestion(DAG, treatment, outcome, covariates, identification assumptions, dataset/counterfactual regime), CausalResult(identifiable? estimate? sensitivity, adjustment_set, caveats). A causal graph alone does not establish truth or remove unobserved confounding. Distinguish observational association from interventions.

**P1:** Established causal libraries such as DoWhy/EconML for narrowly identified estimands, with assumption records and independent backdoor/frontdoor checks where applicable.

**P2:** Unobserved confounders, collider bias, selection bias, positivity violations, small sample and reversed edges; forbid confident causal estimates when assumptions fail.

**P3:** Synthetic causal-ground-truth and cautiously selected real benchmark tasks; compare competent conventional estimators; grade recognition of non-identification, estimate error and sensitivity disclosures.

**Hardware:** CPU causal identification/reference; GPU/accelerator for large estimation as an optional data-scale need.

## C15 — Spatial objects, scene graphs and capsule-model research

**Current:** Design only. Film Studio Workspace can prioritize domain tasks under a later explicit integration plan.

**Question:** Can the host preserve object identity, geometry and relations under occlusion, edits, scene changes, renaming and multimodal evidence?

**P0:** SceneObject(stable ID, time/version, coordinate frame, units, pose, geometry refs, confidence/evidence, visibility/occlusion state), SceneRelation, TrackUpdate and SceneQuery. Source image/video observations are permissions-bound; coordinate vectors are **not** generic latent embeddings. Capsule networks are optional learned challengers, not a synonym for a point-cloud or typed pose record.

**P1:** First build deterministic scene graphs, geometry transforms/relations and stable IDs. Optional perception/segmentation features are derived, versioned and auditable. Keep camera/world coordinate-frame conversions explicit.

**P2:** Occlusion/reappearance, aliases, orientation frame errors, conflicting camera observations, deletion, identity swap, model hallucination, sensor uncertainty and workspace detachment.

**P3:** Compare scene graph + conventional tracking, dense embeddings and capsule/object model challengers on held-out temporal identity tasks. Measure tracking errors, scene consistency, latency, VRAM and source attribution.

**Hardware:** CPU graph/geometry, optional GPU perception for actual image/video loads; no default visual sensor ingestion without consent.

## C16 — Physical modeling, numerical integration and learned dynamics

**Current:** C05 ships only a *bounded reference discrete harmonic oscillator*, **not** a general physical simulator or continuous ODE solver.

**Question:** Given a dimensioned physical model and boundary/initial conditions, can Lu compute a robust prediction and honestly quantify discretization/model uncertainty?

**P0:** SimulationModel(units, state variables, differential equations, constraints/events, solver tolerances, initial/boundary conditions, validation domain), SimulationResult(trajectories or aggregates, method/order, convergence diagnostics, invariant drift, uncertainty, OOD). Separate mathematical model agreement from correspondence to reality.

**P1:** Standard CPU solvers (SciPy solve_ivp class) with explicit tolerances/stiffness selection, dimensioned tests and conservative methods when appropriate. Learned Neural ODE and KAN surrogates are optional, independently tested challengers.

**P2:** Energy/momentum/invariant drift, stiff-system failure, missed events, timestep instability, units mismatches, incorrect boundary data, non-finite outputs, solver cancellation and resource limits.

**P3:** Compare analytic reference solutions and standard numerical integrators on held-out regimes; if learned dynamics considered, compare solver accuracy/error bounds, OOD behavior, throughput and **training cost**. Report whether a simplified predictive model serves the actual Lu user task.

**Hardware:** CPU baseline; GPU batched PDE/ODE research after size/precision/cost analysis. FPGA is a targeted real-time hypothesis only.

## C17 — State-space models and learned temporal representations

**Current:** Design only; not to be confused with C07's exact typed state service.

**Question:** Does an SSM improve long-sequence prediction, change detection or temporal reasoning **over** the already correct event/snapshot system?

**P0:** TemporalSequence(input typed events, time delta, missingness, sample lineage), StateModelArtifact(checkpoint, training split, normalizer, architecture), Prediction(time horizon, variance, OOD, calibration). An arbitrary random recurrent hidden-state oscillation is **not** semantic contradiction detection.

**P1:** First implement labeled benchmarks on typed temporal evidence. Compare explicit state/events, classical Kalman/filter/HMM where suitable and learned SSM/sequence baseline. No hidden replacement of Lu's model or canonical memory.

**P2:** Timestamp disorder, missingness, concept drift, false change points, long-horizon instability, checkpoint corruption, training leakage and representation conversion loss.

**P3:** Held-out future prediction and correct conflict/transition handling; report user-task accuracy, update cost, catastrophic forgetting, energy and ungrounded temporal claims.

**Hardware:** CPU short-sequence baseline; GPU SSM training/large-batch evaluation when justified.

## C18 — Meta-learning, adaptation and learning from traces

**Current:** Design only, deliberately postponed until retention/security/evaluation are operational.

**Question:** Can consented adaptation produce durable, real improvements on future data **without** leaking user content, overfitting benchmark splits or modifying the selected transformer unexpectedly?

**P0:** AdaptationProposal(training data provenance, privacy class, allowed update target, transform/normalizer, versioned frozen policy, evaluator, rollback strategy, consent and retention), with explicit separation of tool-routing policy vs domain expert checkpoint vs Lu base LLM weights.

**P1:** Start with retrieval tuning, deterministic routing heuristics, lightweight calibration and simple fine-tuning baselines; then study MAML/LoRA/online updates only when evidence justifies added complexity. Training must be a *separately permitted action* with its own resource/security policy.

**P2:** Stop/pause/revoke, deletion from future training, data poisoning, prompt-injection through traces, split leakage, checkpoint tampering, rollback and regression against old supported tasks.

**P3:** Train-on-past/test-on-future heldouts, fixed-lag evaluations, negative transfer, stability and continual learning comparisons. Require real user-permitted training inputs and independent replication before any policy becomes default.

**Hardware:** CPU baseline for small policies, optional GPU training; cost and power/training time are first-class primary outcomes.

## C19 — Topological data analysis (TDA)

**Current:** Design only; task-dependent research candidate, not a general reasoning upgrade.

**Question:** For appropriate point clouds, time series or shape/embedding data, do persistent topology features provide useful, robust, task-grounded information beyond geometric/statistical baselines?

**P0:** TopologyQuery(dataset snapshot, metric, filtration type, scale/range, homology dimensions, sample rate, provenance), TopologyResult(persistence diagram intervals, uncertainty, interpretation limitations, units/metric, resource cost). No assumption that topology of embedding vectors corresponds directly to semantic truth.

**P1:** Established GUDHI/ripser/Python TDA libraries for bounded data and dimensions; preserve reproducibility and explain applicability. Derived diagrams never become canonical scene objects or memories.

**P2:** Noise and outlier robustness, metric choice, degenerate point sets, filtration bounds, huge persistence complexes, downsampling instability, privacy and malformed data.

**P3:** Compare direct geometry/statistics, spectral features and task-domain incumbents; score actual classification/anomaly/shape outcomes, not just whether a diagram looks structured.

**Hardware:** CPU bounded diagrams; optional GPU or distributed distance/filtration computation only for empirically justified large datasets.

---

## Mapping the original twelve technologies to the nineteen delivery components

| Original ambition | Current delivery placement | Correct interpretation |
|---|---|---|
| Hyperdimensional computing / VSA | C08, plus C06–C07 dependencies | Derived associative/relational research, not canonical storage |
| Kolmogorov–Arnold Networks | C09, C05/C16 comparison | Learned function approximator/surrogate, not exact calculator |
| State-space models | C17 vs C07 baseline | Learned temporal modeling is separate from state correctness |
| Capsules / object models | C15 | Learned object-centric challenger against stable scene graph |
| MCTS + dynamic programming | C12 | Bounded planning, no unearned optimality |
| Causal models | C14 | Identification and sensitivity, not correlational causal claims |
| Bayesian networks | C13 | Probabilistic reasoning with sourced assumptions/calibration |
| Neural ODE and physics | C16 | Numerical solver incumbent first, learned dynamics second |
| SMT/formal provers | C10 | Typed formalization and verified witnesses/certificates |
| Combinatorial optimization | C11 | Feasible vs optimal vs infeasible/unknown states distinguished |
| Meta-learning / MAML | C18 | Explicit consent, temporal holdouts, safe rollback |
| Topological data analysis | C19 | Task-defined shape/structure analysis, not universal semantic space |

C01–C04 are the infrastructure **required to evaluate and safely expose** these research domains. C05 exact calculation, C06 canonical retrieval and C07 typed state are indispensable reliable baselines, not replacements for the original scientific ambitions.

## Entry/exit rules for every future P0 component spec

For every C06–C19 module, create a source-specific spec at docs/components/<family>/P0-research.md that: (1) cites this card and any new scientific sources; (2) narrows a **real** Lu-selected-model task; (3) selects a competent incumbent and negative case; (4) pins formal input/output and trust assumptions; (5) assesses CPU/GPU/FPGA relevance; (6) estimates resources/licensing; (7) defines test/benchmark artifacts and falsifiable advantage; (8) records stop/go; (9) reserves Protobuf namespace and schema ownership; (10) labels unimplemented capabilities Proposed until code/tests exist. These **entry specifications** must not be converted into made-up P1/P2/P3 completions.

**Current production promise:** none of C06–C19 is registered as a default Lu model tool by this design. Only host-approved, separately tested implementations may be promoted.
