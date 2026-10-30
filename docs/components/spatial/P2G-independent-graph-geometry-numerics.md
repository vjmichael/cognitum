# Cognitum C15 T2/T3 P2G — independent-reference validation and geometric boundary correction

**Date:** 2026-10-28 (America/Phoenix project date)  
**Scope:** Cognitum only, isolated recovery of previously verified P2F archive; research-only, no changes to Lu, GitHub or user machine.

## Why this checkpoint

The C15 T2/T3 P2C implementations had narrow mathematical comparisons, but not systematic boundary-crossing validation. We extended testing to independent, pinned-randomness reference oracles and found real flaws in the shared 3D DDA ray traversal used by both the sparse and temporal occupancy workers.

## Actual defects detected and repairs

1. **Negative-start grid plane:** a segment from `(2,.5,.5)` to `(1.5,.5,.5)` previously enumerated cells `(2,0,0)` and `(1,0,0)`. Under a half-open voxel convention, cell `(2,0,0)` is only touched at the exact starting boundary; it cannot be assigned a traversed free-space observation. Now only `(1,0,0)` is enumerated.
2. **Multi-axis endpoint ties:** with one or more coordinates ending exactly on a voxel plane, the previous DDA sometimes attempted another step after `t=1`, rejecting otherwise valid data with `INVALID_RAY_TRAVERSAL`. Compute the final **positive-length interior** voxel first, then append the explicitly assigned endpoint voxel at most once.
3. **No-hit endpoint:** a no-hit ray ending exactly at a grid plane must not label the zero-length endpoint voxel as measured free. A new optional `include_endpoint_cell` DDA parameter is wired from the declared `endpoint_hit` flag. Hits still use half-open endpoint assignment.

Grid planes use **exact** integer checking in normalized voxel coordinates, not tolerance-based snapping. Near-boundary coordinates keep their actual starting cell. The endpoint convention is an engineering choice, **not** an experimentally established physical truth. This patch does not change a Protobuf schema or enable untrusted execution.

## Independent comparisons actually executed

- **Exact rational segment/plane intersection oracle:** 240 deterministic 3D start/end cases chosen from 1/4-voxel coordinates including exact cell faces, edges and corners; the oracle computes exact crossing parameters and samples interval midpoints rather than implementing another DDA. Additional targeted hit and no-hit boundary tests.
- **NetworkX DAG reference:** 96 seeded multi-parent membership graphs compared against `networkx.is_directed_acyclic_graph`, with cycle rejection and per-role distinct-part count comparisons.
- **SciPy `logsumexp` and NumPy:** 64 seeded three-hypothesis comparisons with 12 independent likelihood vectors each; expected normalized relative weights matched with absolute tolerance `2e-12`. This is a numeric equality check, not calibrated inference or ontology equivalence.
- **SciPy Rotation:** 96 seeded quaternion-vector rotations matched to SciPy within `2e-12` absolute tolerance, respecting scalar-last library vs. scalar-first Cognitum ordering.
- **SciPy `expit`:** independently verified decayed log-odds and logistic probabilities for conflicting multi-source occupancy evidence.

All random generators have fixed explicit seeds in `tests/test_c15_p2g_independent_parity.py`. The test module imports SciPy, NumPy and NetworkX as **required**, not silently skipped, dependencies. A dedicated optional extra is declared in `pyproject.toml`. Failure to import them fails the parity suite.

## Verification (2026-10-28 checkpoint)

- C15 selected tests: **311 passed, 504 additional subtests passed**.
- C13/C14 regressions: **754 passed, 39 skipped, 39 additional subtests passed**, five existing warnings.
- Selected combined: **1,065 passed, 39 skipped**, plus **543 additional subtests passed**. Not equivalent to a full repository green build.
- Protobuf schema wire checks: **61/61 passed** with independently run protoc.
- Platform: Linux x86-64, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, NetworkX 3.6.1, protobuf 6.33.6.
- Attempted unrestricted repository `pytest`: without `tests/` in PYTHONPATH, collection fails on two unrelated C06 top-level test imports; with `PYTHONPATH=.:tests`, execution reached ~24% before this environment's 90s timeout. **No full-suite pass claimed.**

### Reproduce selected suites

```sh
python -m pip install -e '.[spatial-reference-parity]'
PYTHONPATH=. python -m pytest -q tests/test_c15*
PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14*
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
# Or run selected checks using tools/run_c15_p2g_gate.py
```

`verify_protobuf_schemas.py --require` also needs a functioning compiler matching its documented detection behavior; the installed torch-bundled protoc was used in this environment. No implicit network downloads occur in the gate runner.

## Scientific and host boundaries

This is **partial independent mathematical reference parity**, **not full engine parity**. NetworkX graph acyclicity is not OWL 2 inference; SciPy sigmoid and rotations are not OctoMap, OpenVDB, pose-estimation or real-sensor benchmarks. External OWL reasoner and OctoMap/OpenVDB correctness/memory tests, genuine sensors, trusted frame registration, representative held-out datasets, and independent model/LLM comparisons remain open. C15 T1 P2F TrackEval remains blocked on an external checkout and matching real data. No OS sandbox, Windows proof, Lu integration, native worker authorization, physical action authority or sensor authenticity is conferred by these checks.

## Recommended next C15 gate

After this **P2G partial reference check**, prioritize OctoMap/OpenVDB and OWL 2 reference **execution** in an isolated dependency environment if genuine parity is the next objective. In parallel, use the small TUD-Campus ground-truth/prediction fixture plus the pinned TrackEval source to satisfy T1 P2F independently without downloading a 5.5 GB image dataset. Any final P3 claim must use representative held-out real data and matched conventional baselines.
