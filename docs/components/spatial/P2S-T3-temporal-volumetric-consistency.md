# Cognitum C15 T3 P2S — Temporal volumetric consistency

**Scope:** Bounded research-only cross-capture reasoning for sparse 3D occupancy. Built as an additive extension to P2R; no changes to P2R within-capture correlation code, prior R1/R2 tracking baselines, Lu, or any canonical scene state.

## Architecture

`P2STemporalRequest` contains two to twelve strictly ordered, independently captured `P2RFusionRequest` frames. A frame requires a single depth source reference, one depth-frame digest and one capture tick. The camera is validated by the P2Q validator inside P2R. Source references, camera calibration, and digests are **caller-declared, not authenticated**. Cross-conversation, volume-grid mismatches, duplicate frame digests, replayed capture IDs, unknown Protobuf fields and over-capacity requests fail closed.

Each P2R call first adjusts **within-capture** equicorrelated rays. The P2S layer treats one voxel contribution from one P2R capture as one event, avoiding per-pixel double counting. The baseline is:

`L(t) = clamp(sum_i(P2R_logodds_i * 2 ** (-(t-t_i)/half_life)))`.

This is a *heuristic* cross-capture score, **not a statistically calibrated probability**. Adjacent images and sensors may still be correlated. P2S preserves this unmodified baseline for comparison.

To examine persistence and moving objects, P2S looks for sign reversals in the latest non-zero voxel evidence. A single contrary event leaves the cell `CONTESTED`; after at least `min_stable_observations` consecutive opposing-frame observations, the change is classified as a **streak-confirmed hypothesis**. Its adjusted score discounts historical pre-transition evidence by the caller-supplied `historical_retention` factor (0–1). The complete original timeline remains in the per-voxel provenance journal, including frame request hashes and retention weights. This is not statistical proof of a move or physical ground truth. A later return to the original sign triggers the same logic in reverse. A streak is never promoted to an occupied/free state while the final adjusted score still favors the *opposite* sign. Within-capture mixed free/hit evidence breaks the streak and forces a contested state for that cell.

`max_age_ticks` marks cells without recent observations `STALE`; weak and under-supported evidence is `INDETERMINATE`. Confirmed transitions need *one more* consistent capture before a predicted-only voxel can be handed to T2; disputed and stale voxels are never handed off. Every T2 voxel is `VOLUME_PREDICTED_*`, and the existing `spatial_volume.classify` must classify all these as `CELL_UNKNOWN` in the verified/canonical sense. No host permission or scene write is authorized.

## Reproduction

```sh
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2s_temporal_consistency.py
PYTHONPATH=. python tools/run_c15_t3_p2s_demo.py
PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14* tests/test_c15*
PYTHONPATH=. python -m pytest -q tests/test_c07*
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

## Limits and deferred validation

- P2S operates on synthetic or externally supplied depth readings; no real calibrated temporal RGB-D or LiDAR series has been evaluated.
- `historical_retention`, half-life, correlation `rho`, and streak thresholds are assumptions, **not trained or calibrated sensor parameters**.
- Identical frame hashes and IDs are rejected as replays; truly duplicated or correlated cross-frame content under different hashes cannot be detected reliably without trusted capture attestation.
- This module does not perform simultaneous localization and mapping (SLAM), pose refinement, moving-object 3D segmentation, navigation, collision avoidance, physical safety, or belief promotion.
- External benchmarks: dynamic RGB-D/point cloud datasets, independent OctoMap and OpenVDB comparisons, correlated-sensor calibration, dynamic-object tracking, host-enforced permissions. Recorded in a separate deferred backlog.
