# Cognitum C15 T3 P2U — Dynamic/static scene hypothesis mapping

**Status:** offline, research-only engineering checkpoint. Not sensor validated or authorized for navigation, actuation, scene writes, or Lu integration.

## Scope

P2U consumes 2–8 existing P2T *requests*, recomputes P2T outcomes, binds rolling depth captures and motion links, and produces two disjoint **research representations**:

1. `objects` + `cells` — track and voxel *dynamic hypotheses*, with explicit tentative, persistent, dormant and retired object states; unresolved/contested or recently dynamic voxels never become static hypotheses.
2. `stationary_hypothetical_volume` — a separately copied VolumeGrid, restricted to stable, recent, independently corroborated predicted evidence. It never includes measured evidence, and T2's volume classifier must still return `CELL_UNKNOWN`.

### Data provenance and anti-replay

Every P2T input is independently recomputed, including the original P2S/P2R calibrated-depth checks and T1 scene binding. Windows must share conversation, volume, scene and grid; have monotonically increasing evaluation ticks; and each must contribute at least one new capture. Reused capture IDs must have exactly the same serialized content. Reusing the same source+frame digest under a new capture ID is rejected.

A fresh motion link only counts when its **destination capture ID** is newly introduced in that window. Multiple voxel pairs in one window do not multiply the number of distinct motion windows. A persistent object is a repeated, matching *caller-supplied ID* with qualifying fresh motion candidates, **not a validated object identity**.

Stationarity likewise requires an actual *fresh contributing capture* for the specific voxel at every counting window; simply re-evaluating the same voxel in an overlapping window cannot increase its consecutive stationary count. In this offline implementation, the bounded P2S provenance is recomputed separately to make that check auditable; a future host integration may share an immutable verified P2S result to reduce repeated computation.

### Bounded policy

- Input: `proto/cognitum/spatial/v1/dynamic_scene_mapping.proto` with `P2UDynamicSceneRequest` and `P2UDynamicSceneResult`.
- Runtime: `cognitum/spatial_dynamic_scene_mapping.py` exports `map_scene` and `verify`.
- Up to **8 windows**, 7,000,000 serialized request bytes, 4,096 resulting cells and 128 distinct object IDs; upstream P2T/P2S resource limits remain in force.
- At least 2 distinct motion windows for tentative-to-persistent status, configured by `min_motion_windows`.
- At least 2 consecutive, cell-fresh stationary windows, configured by `min_stationary_windows`.
- A dynamic voxel remains withheld for `dynamic_hold_ticks` after its latest fresh motion candidate. Expiry alone is **not enough** to make it static: fresh stable evidence must still satisfy the stationary threshold.
- An object's last bound sample time determines active/dormant/retired staleness; `max_object_gap_ticks` is a caller-declared heuristic, not a calibrated tracking filter.
- Entire upstream P2T motion paths/overlaps remain excluded, as do disputed and unconfirmed temporal cells.

### Reproduction

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2u_dynamic_scene_mapping.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2u_demo.py
PYTHONPATH=. python -m pytest -q tests/test_c15* tests/test_c13* tests/test_c14*
```

A synthetic 2-window motion example yields 1 persistent object hypothesis, 2 dynamic-voxel hypotheses and 12 stationary-volume predicted cells. It uses 10 unique depth captures. These counts are **not accuracy measurements**.

### Open validation gates

- Independent RGB-D/stereo/LiDAR sequences with ground truth dynamic masks, ego-motion and object IDs.
- Independent reference comparisons (OctoMap, OpenVDB, dynamic SLAM / occupancy maps); different representations require explicit common evaluation contracts.
- Quantified false-static/false-free, false-dynamic and ID-reassignment errors, calibration and compute bounds.
- Publisher, source and conversation authority in the actual Windows Lu host; caller hashes and identifiers alone cannot confer it.
- Dynamic scene map lifecycle and bounded replay-performance profiling; avoid redundant P2S recomputation without changing the verified evidence contract.

Deferred experiments are tracked in `C15-T3-P2U-deferred-validation-backlog-v1.json`. This milestone does not change R1 performance tracking, P2T/P2S internals, Lu, or GitHub.
