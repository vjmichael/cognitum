# C19 — Practical topological data analysis P0–P3

**Date:** 2026-11-04. **Status:** implemented on standalone feature branch, native Linux/Windows verification pending. No real user input, data files or transformer models have been used.

## Design and engine decision

C19 is **task-specific topology**, not a general-purpose improvement in reasoning. Its controlling question is whether bounded persistent-homology features offer extra held-out task success beyond standard geometry, statistics and spectral baselines. This implementation chooses the established **Ripser.py** library as the Vietoris–Rips H₀/H₁ engine. It does not implement or claim a novel persistent homology algorithm. **GUDHI** independently cross-checks finite intervals on small clouds. **SciPy** provides Euclidean/Manhattan pairwise distances, an independent minimum-spanning-tree H₀ oracle and graph-Laplacian eigenvalue baselines; **Persim** supplies bottleneck diagram distances. scikit-learn fits the same regularized logistic classifier for each compared feature family.

Library references:
- <https://ripser.scikit-tda.org/en/latest/reference/stubs/ripser.ripser.html> — maxdim, threshold and distance-matrix APIs; Ripser.py is MIT licensed
- <https://gudhi.inria.fr/python/latest/rips_complex_user.html> — full clique Vietoris–Rips filtration at simplex diameter; GUDHI core Rips interface MIT
- <https://pypi.org/project/persim/> — persistence diagram distance utilities
- Dependency and packaging review: optional CPU-only extras `topology-rips` and `topology-verify`. No TDA package is added to stdlib-only Cognitum core. Final binary/native licensing and distribution review must precede bundling into Lu.

## P0: typed and bounded domain

`cognitum/topology_rips.py` declares `TopologyQuery`, `TopologyResult`, `Interval`. Request parameters: source/snapshot SHA-256, unit declaration, Euclidean or Manhattan distance, explicit Vietoris–Rips filtration, finite maximum distance scale and homology dimensions 0/1. Inputs are 3–64 numeric samples with at most 8 dimensions, finite real coordinates of limited magnitude. Output records finite/essential persistence, component counts, strongest finite H₁, independent SciPy H₀ deviation, input cardinality, unique point cardinality, pairwise distance upper count, and limitations. A bounded scale can censor features; never call an essential class proof of a truly permanent physical hole. Source hashes correlate already supplied snapshots, not their authenticity.

`proto/cognitum/topology/v1/topology.proto`, checked-in `cognitum/proto/topology_pb2.py`, and `cognitum/topology_wire.py` define strict canonical Protobuf request/reply, finite-death flags rather than infinity sent as a `double`, source-bound result hashes and replay verification. Neither the request nor returned diagrams execute tools, search files, acquire sensors, write C07 memory, or authorize a Lu action.

## P1: genuine conventional topology

`compute` constructs a bounded distance matrix with SciPy, runs actual Ripser over the finite scale, translates diagrams, validates them, and cross-checks the finite H₀ endpoints with a separately computed SciPy minimum spanning tree. Duplicate-coordinate zero-length edges are accounted for independently instead of silently dropped by SciPy's sparse graph representation. `topology_gudhi.crosscheck` expands an independently constructed bounded GUDHI Rips simplex tree for at most 40 points and checks finite H₀/H₁ interval counts and endpoints against Ripser; if the optional verifier is not installed or an input is too large, it explicitly returns a nonpassing unsupported status.

## P2: adversarial inputs, scope and robustness

Strict numeric, source, filtration, dimension, metric and scale validation; bounded points/coordinates, matrix size and interval output; explicit refusal on malformed/noncanonical Protobuf and tampered results. `perturbation_stability` computes actual Persim bottleneck distances for the finite diagrams of two compatible queries. Stability distance is **descriptive**, not an input-noise uncertainty certificate or cross-metric proof. Degenerate/duplicate sets and truncated scales have dedicated tests. Further host-hard CPU cancellation, memory limits, trusted input provenance, confidential coordinates, outlier policies, dataset retention and OS worker isolation are **Lu integration concerns**; bounded dimensions do not replace kernel-enforced resource containment.

## P3: falsifiable task-level benchmark

`cognitum/topology_evaluation.py` and `tools/c19_topology_benchmark.py` generate fixed-seed synthetic ring vs disk clouds, fit strictly on earlier seeded examples, and report held-out accuracy for four matched scikit-learn models:
1. geometric statistics (radius dispersion, nearest-neighbor and covariance eccentricity);
2. geometry plus graph-Laplacian spectral eigenfeatures;
3. geometry plus persistent H₁ summary;
4. geometry plus spectral and persistent H₁.

Actual CPU/wall timings, independent GUDHI parity, H₀ MST check and genuine Ripser H₁ values are emitted. **No minimum TDA uplift is forced.** If pure geometry does as well or better, say so. Because geometric radius statistics are a competent circle-vs-disk baseline, the expected honest finding is that topology may be redundant on this toy task. Synthetic labels are known only to the evaluator; those do not establish held-out real-world object perception, semantic structure of embeddings, or Lu's transformer task success.

`tests/test_c19_topology.py` and `tests/test_c19_wire.py` cover real library calls on circles, duplicate points, disconnected-scale components, metric sensitivity, nonfinite/oversized requests, source mismatch, independent GUDHI checks, bottleneck perturbations, held-out modeling and forged typed results.

## Real acceptance and nonclaims

`.github/workflows/c19-topology.yml` requires actual **Windows/Linux Python 3.11/3.13** Ripser, GUDHI, Persim, NumPy, SciPy and scikit-learn; compiled original Protobuf schema parity; real standalone tests and measured synthetic classification. Dedicated native test skips are not acceptable for C19 closeout. General repo smoke/regression and branch mergeability must also pass at the same latest commit SHA.

The cloud development runner could not install Ripser/GUDHI locally because its package-index hostname was unreachable. Code is **not declared tested**, and feature PR cannot be merged as verified until native CI produces evidence. External licensed geometry/time-series point clouds and Lu with/without model comparisons remain separate production-efficacy requirements. TDA diagrams never become canonical scene objects or remembered facts without a separately authorized, independently justified host integration.
