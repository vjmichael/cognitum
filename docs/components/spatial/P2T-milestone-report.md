# Cognitum C15 T3 P2T — Object-aware volumetric candidate reasoning

**Milestone:** completed as an **offline research engineering checkpoint**, **not** validated on physical sensors. **No Lu/GitHub changes.** Earlier R1 tracking performance and P2S temporal fusion remain unchanged.

## Implemented

- New `P2TObjectAwareRequest/Result` native Protobuf contract, independently checked against compiler descriptors.
- Read-only fusion of P2S temporal occupancy with T1 `SceneSnapshot` object IDs and world-coordinate tracks.
- Deterministic SHA-256 binding to the supplied scene and capture frames; strict cross-scope, schema-version, frame-reference, request-size and replay checks. **These hashes establish internal consistency, not external authenticity.**
- Candidate motion links **only when paired** recovered-free and recovered-occupied voxels spatially agree with a bounded displacement of the same caller-supplied object track. Ambiguous multiobject associations remain explicit and non-authoritative.
- Separate stationary-map hypothesis excludes changing, stale, contested, overlapping, and object-path-intersected cells, and contains exclusively predicted-class evidence. A T2 structural audit verifies **no measured facts** arise from that handoff.
- Research-only replay verifier and fixed synthetic calibrated 5-capture demo.

## Verification observed

| Check | Result |
|---|---|
| Focused C15 T3 P2T tests | 21 passed |
| Selected C13/C14/C15 regression suite | 1,296 passed, 39 skipped; 567 subtests passed |
| C07 regression suite | 218 passed, 71 subtests passed |
| Protobuf descriptor parity | 69 of 69 compiled/binding matches |
| Synthetic motion study | 1 linked object-motion hypothesis from 5 calibrated depth captures |
| T2 authority isolation | Predictive stationary evidence cannot establish measured occupancy |

The synthetic scenario has origin `(4,4,6)` recovering as provisionally free and destination `(6,4,6)` recovering as provisionally occupied after a one-metre object displacement. Both remain **hypotheses**; neither establishes causation or physical safety. The run demonstrates software logic, not real camera motion estimation.

## Limitations and deferred work

- True object identification is not authenticated. Caller-provided T1 tracks are bound to their supplied scene and capture metadata only.
- Sensor timestamps, hashes, world poses and calibration are not host-attested; spoofed internally consistent data remains possible.
- Real 3D tracking, ego-motion rejection, occlusion/reentry, moving vs stationary ground truth, external OctoMap/OpenVDB comparisons and dynamic-occupancy calibration are deferred.
- This is not a production static map, navigation map, safety or collision detector, or a Lu-authorized capability.

## Reproduction

From extracted checkpoint root:

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2t_object_aware_volume.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2t_demo.py
```

See `docs/components/spatial/P2T-object-aware-volume.md`, `P2T_SHA256SUMS.json`, and accompanying machine-readable evidence and backlog. All prior milestone records and benchmarks are preserved.
