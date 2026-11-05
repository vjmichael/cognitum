# Cognitum C15 T3 P2V — Dynamic Scene Robustness

**Status:** Offline research implementation **passed selected software verification**, not real calibrated 3D sensor acceptance or Lu security integration. Input baseline: immutable C15 T3 P2U checkpoint.

## Code changes

- Added `dynamic_scene_robustness.proto` and generated Python binding; research-only, no authority or canonical writes. Independent compiler match: **71/71**.
- Added opt-in `spatial_dynamic_scene_robustness.py` that re-evaluates P2U, requires consistent camera-frame and calibration-source namespaces, records translation/quaternion rotation continuity, fails closed for unregistered pose frames, and quarantines static hypotheses after abrupt motion.
- Missing objects remain unexplained; suspected reappearance after long gaps is **not** identity authentication. Recently uncertain object positions suppress nearby stationary-volume cells.
- Static output is a filtered subset of the P2U predicted-only output; stale cells are withheld by last real contributing capture tick. T2 remains indeterminate on those predictions.
- Original P2U, T1/T2/T3 internals and R1 performance baseline are unchanged. The only change to an existing source file is additive registration in `tools/check_proto_descriptors.py`.

## Tests

- **1332 passed; 39 skipped; 567 subtests passed**, selected C13/C14/C15 suites, 5 warnings.
- **218 C07 tests passed** (71 additional subtests).
- **21 focused P2V tests passed**, including camera-frame drift, calibration-source drift, translation and rotation jumps, quaternion sign equivalence, static age, object missing/reappearing, forged hashes, scope changes, unknown Protobuf fields, replay tampering, and T2 indeterminate prediction.
- **71/71 independent Protobuf compiler/binding checks passed**.
- Synthetic 10-depth-frame demonstration is saved separately. It is not a 3D mapping accuracy benchmark.

## Boundaries and gaps

1. P2Q already performs caller-calibrated projection into a declared world frame; P2V does not double-transform or estimate ego-motion.
2. Pose and source signatures are untrusted assertions, not independent sensor attestation. Thresholds are policy heuristics without calibrated probabilistic uncertainty.
3. Missing observations cannot establish actual occlusion; reappearance does not prove continuity of identity.
4. P2V may withhold all otherwise useful stationary evidence when a pose jump is detected. Abstention coverage must be measured alongside accuracy.
5. Real RGB-D/LiDAR, camera-motion ground truth, object identity, an external mapping baseline, compute profiling and Windows Lu host security tests remain **deferred**.
6. The unrestricted all-repository suite and Windows-native tests were **not run**.

## Reproduce

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2v_dynamic_scene_robustness.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2v_demo.py
PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14* tests/test_c15*
PYTHONPATH=. python -m pytest -q tests/test_c07*
```

The benchmark backlog in `C15-T3-P2V-deferred-validation-backlog-v1.json` is independent of every prior Cognitum T1/T2/T3 and tracking backlog.