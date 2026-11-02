# Cognitum — Component Quality and Integration Hardening Roadmap

**Decision date:** 2026-11-02  
**Status:** Approved engineering direction; this document does not certify completion or authorize production promotion.  
**Repository:** `vjmichael/cognitum`; **GitHub is a repository and milestone record, not the development hub.**  
**Scope:** Cognitum Linux/local development; **no Lu source changes**, no Cognitum core coupling into Lu. All Windows Cognitum tasks, including P15, remain **deferred indefinitely**.

## Why return to the components?

The Cognitum × NVP editable feature-film preflight exercised selected specialists successfully, but the 1,320/1,320 fixture-continuity score was also achieved using SQLite and deterministic rules alone. C05, C10, C14, C15 and KAN had mostly isolated preflight probes; an end-to-end orchestrated film-production decision using every relevant specialist was **not** demonstrated. Acting Coach, Voice Director and an integrated physical world model are not implemented.

**Decision:** improve each specialist where there is a measured deficiency, retain a conventional baseline, then revalidate through small joint tasks before another feature-length film acceptance attempt. Do not optimize away safeguards for speed.

## Prioritized component program

| Priority | Workstream | Known evidence / observed weakness | Exit criteria |
|---|---|---|---|
| 1 | **C14 causal inference** | G25N failed all 12 width/calibration precision cells; pointwise LR oracle diagnostic is not global inversion; hidden confounding cannot be certified from observation | Scoped inference report with identifiability, refusal and provenance; fresh preregistered calibration with no hidden failures; external review before any estimator promotion |
| 2 | **Selective SSM** | P23b improves on P23 scalar tracking but loses to robust baselines on corrupt sensors and long outages | Fresh disjoint sensor-regime tests, uncertainty calibration, chunk/reset/continuation equivalence, verified memory provenance |
| 3 | **KAN** | P22/P22b learns nonlinear simulators but violates monotonicity and its safety margins fail under unmodeled braking conditions | Compare against exact numerical solver, polynomial/boosting baselines; bound extrapolation and safety abstention; no use as safety controller |
| 4 | **C15 tracking/spatial** | Geometry transform preflight only, NVP actor identity, occlusion and multi-target tracking not accepted | Benchmarks with actor identity swaps, occlusion, geometry, frame-of-reference and time-scoped evidence |
| 5 | **C05 mathematics** | Symbolic/preflight works; rigorous large scene transforms and solver coverage not yet measured | Independent geometric/numerical oracles, degenerate and ill-conditioned cases, precision and latency budgets |
| 6 | **C10 SMT/constraints** | Bounded solver preflight; large production scheduling not exercised | Contradictory and feasible multi-actor resource schedules, proofs/witness checking, timeouts and recovery |
| 7 | **HDC** | P21–P25 repeatedly loses to exact graph, FTS5 or tuned robust classifiers; representation bit tolerance documented | Optional **specialist-only** noisy pattern task with matched augmentation, calibration, hardware cost and strong baselines; no lexical search or primary memory job |
| 8 | **Orchestration/memory/runtime** | Selected component preflight works; no complete cooperative NVP advantage; worker cgroup/supervisor gates not fully live-verified | Cross-specialist provenance/schema/uncertainty, appropriate bypass to conventional methods, cancellation, resource cap, OS-enforced containment, reproducible effect journal |

Priority is **review order, not a promise to defer critical runtime safety defects**. Linux cgroup v2 live containment and independent supervised recovery remain release blockers if a DLC promises kernel protection.

## Shared acceptance discipline

1. **Pin provenance**: branch/source tree, dependency version, dataset/checkpoint hashes and immutable seed/split records. Keep training, model selection and test datasets separate; measure full attempted cohorts including refusals and timeouts.
2. **Predeclare metrics and thresholds**: correct answers, false factual assertions, credible uncertainty, coverage, refusal appropriateness, worst-case failures, latency (warm vs cold), peak memory, energy if available, and continuous-operation recovery.
3. **Use decisive controls**: exact numerical solvers for defined physics; symbolic graph for proven relations; FTS5 for text retrieval; Kalman/robust filters for motion; ordinary statistics for causal inference; no credit for a specialist that does not improve or safely enable the task.
4. **Preserve truth boundaries**: SQLite/verified evidence authoritative; approximate specialists cannot silently rewrite facts, promote causal confidence, alter geometry, or authorize tools.
5. **Evaluate ablations**: combined architecture vs baseline; each specialist disabled in turn; separate router selection errors from model/worker/tool errors and scene-fixture weaknesses.
6. **Stage gates**: component correctness → cross-component typed I/O and error/failure semantics → single cohesive scene with real tool calls → adversarial scenario → feature-length NVP editability and continuity.
7. **Never conflate**: test pass ≠ scientific calibration ≠ production readiness. Skips and blocked environments are explicit; no mock counted as real specialist success.

## Milestone sequence

- **CH-00 (this checkpoint):** record plan, inventory existing research and open gates.
- **CH-C14-01:** audit causal assumptions, calibrations, numerical/oracle validation and reporting boundary; prioritize robustness and clear refusal rather than constructing an unmotivated new interval.
- **CH-SSM-01:** corrupt-sensor/noisy-observation with confidence-aware gating, frozen P23b and Kalman/GRU controls.
- **CH-KAN-01:** constrained dynamics with OOD/monotonicity tests and exact solver control.
- **CH-C15 / C05 / C10:** spatial/actor tracking, geometry/math, scheduling constraints, each validated with independent oracles.
- **CH-HDC:** optional task-qualified specialist with threshold for disabling when not competitive.
- **CH-ORCH:** co-located Linux worker and typed cross-component scenario with fault injection and independent provenance.
- **NVP feature acceptance:** 60- and 120-minute editable productions; no oracle leakage; compare against SQLite + deterministic production tools; creative quality evaluated separately by people.

No change to production algorithms or cross-project Lu source is authorized by this document.
