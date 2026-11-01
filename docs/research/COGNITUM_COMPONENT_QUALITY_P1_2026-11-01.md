# Cognitum component quality program — P1 engineering report

**Date:** 2026-11-01  
**Candidate:** `cognitum/component-quality-p1-20261101` based on unified HDC/KAN/SSM branch.  
**Product:** ONE Cognitum distribution. Cognitum remains separate from Lu on all platforms.

## Decision

Make every Cognitum component as reliable, efficient and diagnosable as possible. **Engineering readiness and demonstrated usefulness are separate release dimensions.** HDC/KAN/SSM ship in the same Cognitum package regardless of whether matched real-LLM studies have yet shown benefit in a particular workload. They must never be mislabeled calibrated, authenticated, causal or universally superior. Research enablement flags are runtime safety policy, not a second product.

## Concrete defects fixed

1. **SSM resumption:** Before P1, a legitimate first chunk could produce latent state `2000`, yet the next chunk would reject that saved state as exceeding the **coefficient** bound `1000`. Resume now validates state against the already-existing `MAX_STATE=1e6` limit; input and coefficient limits remain `1000`. Public direct `DiagonalSSM(...)` construction also checks shapes and bounded finite values rather than silently bypassing `from_mapping`. Old and new valid computations are numerically identical. The 250 random seeded chunk-partition cases pass bitwise equality of outputs and final states.
2. **KAN boundary:** A degree-zero spline checkpoint at the allowed maximum knot previously emitted **zero** even though the immediately interior knot value was nonzero (e.g. last interval value 5). The spline basis now evaluates the last accepted knot at the immediately preceding representable float32 value. Interior spline and all RBF paths retain previous behavior. Explicit degree 0, 1, 2, boundary and RBF negative controls pass.

No scientific algorithm, model training, causal estimator or Lu code was promoted or changed.

## Verification and scope

| Verification | Observed result | Qualification |
|---|---:|---|
| Unified current specialist subset suite | **69 passed** | original 44 plus 25 new assertions/tests, local Linux |
| Seeded SSM whole vs chunked comparisons | **250 exact** | real state carries across 1–8 boundaries |
| Historical cross-domain + new specialist overlay | **378 passed**, 1 deselected, 243 subtests | 689 byte/hash-verified files archived Oct 29 with 19 selected newer source overlays; **not** the canonical Nov 1 full repository |
| Missing transferred historical doc | **1 test excluded** | 10/29 source packet lacked a C14 real-LLM-deferred decision file; test not silently waived |
| Single component-level wheel in clean prefix | **PASS** | HDC/KAN/SSM available in one wheel; not full Cognitum distribution acceptance |
| Python compileall | **PASS** | Unified specialist subset only |
| Windows installed acceptance | **OPEN** | independent Windows binary and tested dependencies not available |
| Current full-repo regression | **OPEN** | checkout at a single verified current SHA required |
| Model usefulness | **OPEN** | paired WITH/WITHOUT LLM experiments and baselines not yet conducted in this task |

## Real performance baseline (Linux, Python 3.13.5; warm, single process)

| Workload | Median per request | What it measures |
|---|---:|---|
| Original SSM 64 x 8 | 1.305 ms | bounded 64-step 8x8 scan |
| Corrected SSM 64 x 8 | 1.311 ms | same outputs; ratio 1.0045x |
| HDC 32 candidates | 0.101 ms | hashing, Hamming ranking and Protobuf |
| KAN small checkpoint | 0.363 ms | checkpoint integrity + CPU inference |
| Standalone Cognitum worker round-trip | **490.3 ms** | 12 independent spawn/IPC/compute/teardown calls; control calculator ~514 ms |

**Finding:** Disposable Python process startup dominates current local single-operation latency, not the HDC/KAN/SSM mathematics. Do not remove containment/permissions to optimize a benchmark. Profile safe session batching or bounded worker leases separately with exact task scopes and lifecycle receipts. The warm numbers above are *not* end-user latency, OS-isolated installed performance or proofs of real task usefulness.

## Tracked component gates

| Family | Current evidence | Next genuine acceptance target |
|---|---|---|
| C05 — Scientific and exact math | archived selected tests pass | Fresh parity and numerical conditioning under large inputs |
| C06 — ANSF memory and provenance | archived selected tests pass | Cross-revision, tombstone, corruption and cold restart on full source |
| C07 — Belief revision and structural memory | archived selected tests pass | Long-horizon contradictions and incremental consistency |
| C08 — HDC representations/retrieval | unified local tests pass | Recall/precision vs exact, BM25, dense; stale-index revisions and P3 retest |
| C09 — KAN approximators | unified local tests pass; spline endpoint fixed | Trainer/checkpoint lifecycle, CPU/GPU parity, uncertainty and MLP/spline baselines |
| SSM — State-space temporal sequence kernels | unified local tests pass; state-resume fixed | Real long context, model state provenance, training/learned SSM, throughput and stability |
| C10 — Formal/SMT | archived selected tests pass | External solver parity, timeouts and adversarial formula corpus |
| C11 — Optimization | archived selected tests pass | HiGHS/CP-SAT comparative solutions, infeasibility certificates, solver limits |
| C12 — Planning | archived selected tests pass | Search explosion budgets, realistic multistep tasks, recovery |
| C13 — Probabilistic reasoning | archived selected tests pass | Held-out calibration and independently verified posterior/intervals |
| C14 — Causal inference and sensitivity | archived selected tests pass; G25 research-specific failures remain | Confidence calibration, broad SCM, external Firth comparison; no estimator promotion |
| C15 — Spatial tracking and 3D | archived selected tests pass | Real MOT/BDD sequence metrics, identity switch, scene persistence and platform tests |
| C17 — Temporal filtering and advanced sequence | not in reconstructed Oct29 test sample | Run current C17 Kalman tests and independent state-space baselines |
| Runtime — Worker lifecycle and capability routing | Linux local component worker acceptance | ~490 ms per disposable process; OS safety, grants, cancellation and Windows production acceptance |
| Packaging — One Cognitum distribution | one component-wheel clean install | Full canonical source wheel, pinned dependencies, Linux+Windows installed smoke |

## Gate policy to v1.0

Apply a common quality rubric to each family: (A) reference parity and analytic invariants, (B) malformed/OOD, timeout, refusal and fallback correctness, (C) persisted state / cancellation / crash recovery, (D) p50/p95 latency and memory with fixed work and hardware, (E) matched real task success versus credible baseline algorithms and WITH/WITHOUT transformer augmentation, (F) clean single-distribution Linux/Windows install from one pinned commit, and (G) independent scientific review where claims require it. Record explicit PASS/FAIL/OPEN, provenance and metrics. A failing empirical HDC/KAN benchmark does not remove its implementation from Cognitum; it governs automatic routing and quality claims.

**Work priority:** obtain canonical current-source full-repository snapshot; rerun whole-suite + artifact checks; close C08/C09 P3 invalidation/signature grants; establish actual worker lifecycle and installed Windows tests; measure throughput/memory across other C05-C17 families; then undertake *predeclared* task-value ablations. Do not restart indefinite C14 G25 confidence-method research without a real blocker.

## Provenance and limitations

- The historic 689-file transfer is user-owned and its original Git blob SHA for each file was verified before reconstruction. It is **not a complete current repo checkout**. 19 selected unified files were overlaid onto it solely to detect cross-domain regression collisions.
- The original local component wheel from the unified branch was only a reconstruction; this P1 wheel remains a testing convenience, not a Cognitum release installer.
- A 2026-11-01 Windows acceptance run, signed worker containment and full source packaging remain unverified.
- Original C08/C09 P3 durable-index invalidation and signer approval files are present on the research branch but were **not run in this P1 component subset**. They must be reconciled and tested against current code before any trust claims.
