# Cognitum C15 — T2 P2C / T3 P2C research report

**Date:** 2026-10-28. **Status:** Verified offline reference milestone, **not** real-world scientific/production certification. **Scope:** mathematical/AI components only; no Lu modifications or application-specific workflows.

## Starting point and scientific references

Built on the sealed `Cognitum_C15_T2_T3_P2B_Assembly_Mereology_Sparse_Ray_Occupancy_2026-10-28.zip` source. Its assembly membership and ray-occupancy implementations are unchanged. Two **new standalone Protobuf contracts** preserve existing callers:

- `proto/cognitum/spatial/v1/structural_hypotheses.proto`; `cognitum/spatial_structural_hypotheses.py`
- `proto/cognitum/spatial/v1/temporal_occupancy.proto`; `cognitum/spatial_temporal_occupancy.py`

Established alternatives, without asserting parity: OWL 2 + Owlready2/HermiT for ontology consistency and classification, RDFLib/NetworkX for graph operations, OctoMap for probabilistic octree occupancy, OpenVDB for sparse hierarchical grids, SciPy rotations for frame registration, and proper scoring rules for probability evaluation. No third-party algorithms or sources are bundled.

References: https://owlready2.readthedocs.io/en/latest/ ; https://octomap.github.io/octomap/doc/ ; https://www.openvdb.org/documentation/doxygen/overview.html ; https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.html

**Actual available independent checks:** NumPy posterior-like weight normalization, NetworkX DAG checks, SciPy frame rotation, SciPy `expit` and independent Brier arithmetic. **Not available:** genuine Owlready2/HermiT, OctoMap, and OpenVDB execution. The latter checks are mandatory before any parity, runtime, memory or quality comparison.

## T2 P2C: Competing explanations and functional constraints

- Up to 16 hypothesis alternatives and 128 distinct observed source-tick records; all IDs are scoped to one conversation and graph.
- Candidate hypotheses contain an explicit prior weight and object/part/role present-or-absent assertions. Assertions producing contradictory presence/absence or cycles are flagged and assigned zero relative weight, but their identity and contradiction remain visible.
- Each observation supplies a **complete likelihood vector** over alternatives. A bounded log-domain update yields normalized relative weights. This is only a discrete Bayesian-style calculation **conditional on the supplied priors, likelihoods and independence assumptions**. It is not evidence that those likelihoods were learned, calibrated or authenticated.
- Requests contain explicit function-related required/excluded roles. Finding the roles only returns `STRUCTURAL_PRECONDITIONS_CLAIMED`, never verified physical functionality. Missing roles return `UNDETERMINED` unless explicitly contradicted. Incompatibilities return `CONTRADICTED`.
- The ambiguity signal uses a provisional relative-weight gap and best-weight threshold; it is **not** a calibrated error probability. Source duplication and attempted authorization are rejected.
- **Known failure:** 3/200 confidently wrong top choices in the synthetic study. Even an optimal assignment under incorrect evidence may be falsely confident.

## T3 P2C: Time, frames, and measured calibration diagnostics

- 3D rigid quaternion+translation coordinate frames, validated unit quaternions and bounded metric map; ray-level source labels and ticks are preserved.
- Ray-grid intersection uses the inherited bounded DDA. Independent time discounting via `2^(-age/half_life)` reduces the contribution of old inverse-sensor log odds. This decay is a declared heuristic, not a learned or validated dynamic-world model.
- Mixed hit/free evidence remains explicitly conflicted, even when the summed log odds favors one side. No unknown cell is marked free from lack of measurement.
- Optional disjoint calibration and holdout voxel-label sets. Select a scalar **temperature** from a fixed range by training Bernoulli negative log likelihood on calibration labels, then independently report holdout Brier score and a five-bin expected calibration error, both before and after temperature adjustment. Reject duplicate labels, training/holdout overlaps and unseen labeled cells. Labels are caller-asserted and not authenticated.
- Temperature fitting does **not** establish generally calibrated occupancy probability; real calibration would require trusted representative datasets, quality-controlled labels, correlated-sensor modeling, out-of-distribution checks and independent prospective evaluation.
- Different frames must share a common registered coordinate system; the code does not estimate pose uncertainty or validate frame origins.

## Reproducible experimental results

Regenerate `docs/components/spatial/P2C-reproducible-studies.json` with `PYTHONPATH=. python tools/run_c15_t2_t3_p2c_study.py`.

### Structural hypotheses (200 synthetic draws)

- Two candidate interior explanations (hidden support present/absent); six noisy, conditionally independent observations per case, with 80% agreement with the hidden simulated truth.
- **191/200** correct top selections; **14/200** flagged ambiguous. **9** incorrect top selections; **3** incorrect cases did not trigger the ambiguity flag.
- **200** NumPy independent normalization checks and **200** NetworkX directed-acyclic checks passed. Those graph checks are narrow mathematical checks, **not** equivalent to OWL reasoning.
- Results are partly self-consistent with the assumed generator and therefore **must not be read as real-world accuracy or independent model generalization**.

### Occupancy uncertainty (80 synthetic sensor trials)

- Each trial contains 60 indexed synthetic cells, 25 calibration labels and 35 disjoint holdout labels; total **2,000** train and **2,800** holdout labels.
- Synthetic true occupancy prevalence 35%; noisy observed ray outcome agrees with truth 80% of the time. The caller intentionally supplies overconfident inverse-sensor probabilities (.97 hit/.03 free).
- Mean holdout Brier score fell **0.17849 -> 0.15749** after temperature fitting; mean five-bin ECE fell **0.16137 -> 0.12066**. Brier score improved in **71/80** runs; it did not improve in every run.
- Scores were independently recomputed using SciPy sigmoid and a separate Brier calculation in all 80 runs. The synthetic exercise is **not** a real-world sensor calibration study.

## Software and protocol verification

- `PYTHONPATH=. python -m unittest discover -s tests -p 'test_c15*.py' -q`: **233 run, zero failures**.
- C13 selected suite: **141 run, two optional skips**.
- C14 selected suite: **652 run, 37 optional skips**.
- **987 passed / 39 optional skips across all three suites, zero failures** (1,026 tests executed).
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`: **60/60** independently compiler-matched schema/binding pairs.
- New focused P2C tests: **41/41** passed, including unknown fields, inter-scope action denial, spoofed/replayed source-ticks, stale time evidence, non-unit frames, label leakage, and unobserved-space assertions.

## Outstanding evidence gates

1. Genuine ontology reasoner comparison (OWL 2 semantics with HermiT/Pellet): **not run**.
2. Genuine OctoMap/OpenVDB correctness, memory, and performance parity: **not run**.
3. Real sensor calibration, externally verified pose estimates, trusted observations and statistically independent labels: **not run**.
4. T1 real MOT tracking with learned appearance embeddings, CAPS alternatives, real LLM benchmarks, native Windows confinement and Lu authenticated integration: **still open/deferred**.
5. Confidence of explanation selection under spoofed evidence, duplicate correlated sources and open-world knowledge: **not solved**.

**Safety and integrity:** all tools produce **read-only research results** with `grants_authority=false`. Neither numerical ranking nor a favorable diagnostic may authorize medical, construction, rescue, robotic, or other physical actions. They do not establish that a hidden interior has actually been measured.
