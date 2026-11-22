# Cognitum C15 T3 P2Q — Calibrated depth to sparse occupancy

**Status:** Offline engineering checkpoint **passed**, external volumetric
benchmark and real sensor accuracy **deferred**. Research only; no Lu/GitHub
modifications; no Windows host/security certification.

## Implemented

- Versioned, bounded Protobuf camera intrinsics, rigid camera-to-world pose and
  depth-pixel observations. Claims only rectified pinhole cameras; no distortion
  solver, monocular depth estimation, raw image-file loader, or learned model.
- Strict positive axis bounds, finite coordinates, unit quaternion checks,
  unique per-pixel events, source/tick image digest consistency, and source
  binding to the camera contract. Neither the user-supplied frame checksum nor
  calibration source ref independently authenticates external readings.
- Correct camera Z-axis depth back-projection using pixel-center convention;
  explicit world-frame rigid transform; input converted to existing bounded
  T3 P2C temporal sparse-ray/occupancy engine.
- Same-frame event source IDs are uniquely derived to avoid unwanted rejection
  of adjacent pixels; they **do not** establish independent measurements.
- Result embeds temporal Protobuf request/result and predicted-only `VolumeGrid`
  usable by existing T2 structural audit. Contradicted and uninformative
  occupancy is withheld; T2 remains indeterminate without trusted observations.
- Deterministic request/camera SHA-256 binding and exact reference replay
  validator; no authority grant or canonical state mutations.

## Actual testing

| Check | Result |
|---|---|
| New focused P2Q tests | 19 passed |
| Cross T2/T3 focused group (including new) | 102 passed, 8 subtests passed |
| Selected C13/C14/C15 | 1,236 passed, 39 skipped, 567 additional subtests passed |
| C07 tests | 218 passed, 71 subtests passed |
| Independent Protobuf compiler parity | 66 / 66 verified |
| SciPy independent camera quaternion reference | 40 deterministic random cases |
| Offline synthetic pipeline demo | Passed: one ray, 5 sparse cells, T2 audit indeterminate |

Independent archive verification: **744 source-file hashes** matched.
A clean extraction passed **48 nearby T2/T3 tests plus 8 subtests**, and
independently compiled all **66 Protobuf schemas**.

The C13/C14/C15 suite contains optional-dependency skips and minor external
library warnings. The full unrestricted repository test suite and Windows host
integration were **not** executed.

## Key scientific constraints

- Observations were **synthetic**; physical camera intrinsics and extrinsics
  are caller assertions, not calibrated or authenticated.
- Multiple pixels from the same frame are correlated; existing log-odds
  integration may be overconfident. This is called out explicitly and retained
  as a deferred experiment.
- P2M 2D appearance embeddings never imply depth or 3D geometry.
- T2's predicted-only grid cannot validate a physical part/void claim.
- No real-world accuracy, quantitative occupancy IoU, map safety, or OctoMap /
  OpenVDB parity is claimed.

## Next steps / preserved benchmarks

1. Obtain calibrated rectified depth frames and independently validated 3D
   reference geometry; run endpoint and reprojection comparisons.
2. Compare with pinned OctoMap under matched voxel size / sensor model.
3. Validate sparse-grid interchange with OpenVDB / NanoVDB.
4. Investigate correlated same-frame ray fusion and calibration.
5. Keep host-owned camera credentials and revocation as a distinct Windows gate.

P2P, P2O, P2N, P2M and the earlier negative P2K tracking results are retained
unchanged. See `C15-T3-P2Q-deferred-validation-backlog-v1.json`.

External model references: OpenCV camera calibration model; OctoMap reference
architecture. These references document conventions, not passed engine parity.