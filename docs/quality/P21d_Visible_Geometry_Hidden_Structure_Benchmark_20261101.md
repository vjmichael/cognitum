# Cognitum P21d — Observed surfaces, uncertainty, and HDC visual association

**Date:** 2026-11-01, America/Phoenix. **Status:** Scoped synthetic Linux research PASS; physical-world-model and safety inference **NO-GO**. Lu unchanged. All Windows tasks deferred.

## Why this test

P21c demonstrated bounded HDC associative graph retrieval but not physical knowledge. P21d tests whether a P19-trained HDC centroid can associate *visible patterns* with prior examples using **32×32 orthographic RGB and depth rasters of synthetic box-union geometry**, without access to simulator-only hidden interiors or object names. The target segmentation mask comes from the synthetic renderer as an **oracle**; actual perception and segmentation remain unsolved. This is NOT a photorealistic renderer or reliable robotics sensor model.

720 training observations cover plate, column, angled shape families; validation contains 320 known-pattern examples from bridge/offset and 80 synthetic checker-pattern novelties. Frozen evaluation uses 480 known appearance cases from entirely withheld cross/frame/steps shapes and 120 novel chevron examples. A similarity threshold is selected only using validation (maximum 10% false accept on that specific synthetic novelty family). After freezing, stress tests recolor surfaces, contaminate perfect segmentation with the nearer occluder, and introduce a second novel hybrid texture resembling known examples. Training/validation/test seeds and geometric families are disjoint.

## Measured local results

| Test | HDC correct | Accepted | Incorrect among accepted | Conventional token-frequency baseline correct |
|---|---:|---:|---:|---:|
| 480 withheld-shape known appearances | 438 | 443 | 5 | 475 |
| 480 recolored appearances | 382 | 387 | 5 | 418 |
| 480 imperfect target segmentation examples | 101 | 102 | 1 | 299 |

The same HDC without abstention got 474/480 on clean known patterns. Its clean visual success is **associative pattern retrieval**, not identification of material composition. The conventional baseline outperforms selective HDC on the known-pattern test.

Unknown appearance refusal: 73/80 checker validation, 120/120 chevron test, 106/120 hybrid adversarial probe. The other **14/120 hybrid examples were incorrectly accepted as familiar**, showing calibration does not generalize to all novelties.

A separate HDC trained to infer hidden bulk from visible tokens achieved only **119/480 (24.79%)**, worse than the held-out majority-class baseline **131/480 (27.29%)**. There were **120 exact RGB/depth-matched pairs** with different hidden internal structure; an evidence policy withheld **240/240** unsupported interior statements. This refusal is by explicit policy, not learned physical intelligence.

## Reproducibility

- P21d standalone experiment: **26/26 pytest tests passed** (16 observation/evidence tests + 10 benchmark/provenance tests).
- Independently extracted archive: all **26 manifest entries** SHA-256 verified; **26/26 tests passed** again; benchmark replay matched all **11** result files byte-for-byte.
- Local archive `Cognitum_P21d_Synthetic_Visual_Grounding_2026-11-01.zip`: SHA-256 `efde728ef51210ae9899852be5bf1be72c9aac3f3cfeec2b4381008011943e66` (27 entries including checksum manifest). Contains source, P19 research checkpoint loader/trainer, trained appearance and bulk negative-control NPZ, tests, case-level decision logs, debug images, reproducibility readme and detailed engineering report.
- Trained appearance checkpoint SHA-256 `e34469505282fa484afb366e3a555d2d9351c00311fb646a63e88ea74712c7ee`.
- These source files and weights are in the **local verified archive, not committed or merged** into the GitHub repository. This branch is a documentation-only research checkpoint.

## Decision and next work

**Do not promote HDC as a physical-world perceiver, material inspector or collision controller.** Approximate associative indexing may still be useful, but segmentation noise and novel-looking similar patterns reduce reliable coverage. Continue with actual multi-view geometry, observed occlusion and unseen interior uncertainty; compare against conventional image embeddings. Keep authoritative scene geometry and contact/physics checks independent. Then evaluate KAN on bounded physical-dynamics approximations against numerical solvers, and SSM on temporal object-state tracking. The broader Linux production cgroup/supervisor gates and causal inference release gates remain open.

