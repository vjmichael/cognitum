# C15 T3 P2T — Object-aware volume candidate explanations

**Status:** offline research engineering checkpoint; physical accuracy and host security unverified.

## Goal

Distinguish a *possible moving object* from an unattributed stationary-map
change without mutating T1's scene, T2's structure graph, or T3's occupancy
journal. The feature consumes the **existing P2S temporal request**, a
**caller-supplied T1 scene snapshot** with a deterministic SHA-256 binding, and
**world-coordinate object-track samples** tied to existing calibrated depth
capture IDs, ticks, source refs, and 32-byte frame hashes. P2R/P2S are
recomputed, not trusted from a supplied metric blob.

## Contract / limits

- New schema: `proto/cognitum/spatial/v1/object_aware_volume.proto`.
- Runtime: `cognitum/spatial_object_aware_volume.py`, entrypoints `analyze` and `verify`.
- Request limit 1.1 MB; at most 16 tracks, 12 samples each, 12 P2S captures,
  4096 voxels from upstream P2S and 1024 proposed motion links.
- Reject unknown Protobuf fields, invalid positions/quaternions, mismatched
  conversation and volume scopes, invalid grid policies, mismatched frame IDs,
  duplicate object IDs, nonexistent T1 objects, or tampered scene binding.
- T1 *latest position and timestamp* must match the final track sample in the
  **world** frame. This is binding, not authentication.
- A motion candidate requires a same-object displacement beyond threshold
  and a **paired** P2S `RECOVERED_FREE` (origin) + `RECOVERED_OCCUPIED`
  (destination), each after the first trajectory sample and before the last,
  within spatial tolerance. A single emptied voxel is *unattributed*.
- Disputed, stale, and changing cells never enter the stationary-map handoff.
  The full object path (not only endpoints) blocks stationary assignment.
- Same-cell candidates from multiple objects are explicitly marked competing.
- Stationary candidates retain only P2S `PREDICTED_*` evidence. T2's volume
  classifier must continue to report `CELL_UNKNOWN` for every handed-off cell.
- Replay-verify the entire Protobuf result; no canonical writes, real-world
  sensor attestation, navigation or collision safety claims.

## Reproduction

```
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2t_object_aware_volume.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2t_demo.py
```

The synthetic motion scene has five calibrated depth captures: initial occupied
voxel `(4,4,6)` becomes free, and `(6,4,6)` becomes occupied after a tracked
object moves one metre. The origin/destination labels are caller-supplied,
not independent person-reidentification or sensor-derived motion truth.

## Integration and limitations

- **T1**: scene snapshot object IDs + latest world pose serve as hypothesis
  binding; T1 does not attest identity or sensor provenance.
- **T2**: the filtered `stationary_hypothetical_volume` remains *predicted-only*;
  structural-spatial audit tests verify no evidence promotion.
- **T3**: P2Q calibration, P2R same-frame dependence, P2S temporal decay and
  contradictory-observation rules remain unchanged.
- **Research limitations:** camera ego-motion, occlusion, object geometry,
  actor assignment across gaps, 3D ID confidence, real sensor calibration,
  false-free error, and compute/resource measurements remain open. Attributing
  paired voxel changes to an object is a **candidate explanation, not causal
  proof**. Nothing is authorized to mutate Lu.

Refer to `C15-T3-P2T-deferred-validation-backlog-v1.json` for external gates.
