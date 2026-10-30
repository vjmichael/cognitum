# C15 T3 P2Q — Calibrated depth and sparse occupancy bridge

**Status:** research-only software engineering checkpoint. Existing T3 P2B/P2C ray and
occupancy engines are reused without modifications. No actual sensor calibration,
validated camera pose, or real-world mapping accuracy is established here.

## Input contract

New `proto/cognitum/spatial/v1/calibrated_depth.proto` (`P2QDepthRequest`):

- Explicit conversation, volume, capture IDs; schema v1; `research_only=true`,
  `grants_authority=false`; no implicit host privileges.
- Pinhole intrinsics `(fx,fy,cx,cy)`, image dimensions, axial max depth, and
  a normalized **camera-to-world** quaternion (w,x,y,z) and translation in meters.
- **Rectified image only**. No distortion coefficients or inversion are supported.
  `rectified_pinhole` is a caller assertion, not a proof of image rectification.
- A SHA-256 of the serialized camera contract, source reference and a SHA-256
  **claimed** for each depth frame. Hashes establish internal binding consistency
  only: input bytes have not been independently inspected or signed.
- Each pixel sample uses integer index `(u,v)`, depth along camera Z in meters,
  source reference, logical tick, and endpoint-hit flag. The pixel represents the
  **center** `(u+0.5,v+0.5)`. Non-return rays MUST reach `max_axial_depth_m`
  and become free-space observations without an occupied endpoint.
- `P2QDepthRequest` is capped at **256 samples**, 100 KB, 8192x8192 image,
  128 voxel axes, bounded depth/intrinsics, and strictly finite geometry.
- Duplicate `(source,tick,pixel)` events, inconsistent frame hashes for the same
  source/tick, unknown Protobuf fields, and missing source evidence fail closed.

## Transformation and integration

Camera endpoint `(X,Y,Z) = (((u+0.5-cx)/fx)d, ((v+0.5-cy)/fy)d, d)`;
world endpoint `R(q)(X,Y,Z)+t`; start is `t`. All rays must remain inside
specified **positive-origin world volume**, otherwise the entire request fails.

Ray source refs are **derived per pixel event** and source/tick/frame hash, so
multiple pixels from one image can be ingested by existing temporal sparse DDA
without accidental event-key collisions. This does **not** establish statistical
independence: same-frame rays are correlated, and log odds may be overconfident.
Downstream results carry an explicit correlation warning.

The resulting `P2QDepthResult` embeds:

- A per-pixel provenance/coordinate mapping;
- Existing `TemporalOccupancyRequest` and `TemporalOccupancyResult` v1;
- Existing `VolumeGrid` v1 restricted to **predicted-only** occupancy evidence,
  with conflict/near-0.5 cells left unknown, for T2 structural auditing;
- Source and request SHA-256, research flags, and limitation warnings.

`spatial_volume.classify` **must** keep all predicted-only cells UNKNOWN;
`spatial_structural_audit.audit` may report hypothetical coverage but must remain
INDETERMINATE for an otherwise unsupported structural claim. No 2D appearance
embedding (P2M) can substitute for depth or physically calibrated extrinsics.

## Reproduce

```bash
PYTHONPATH=. python tools/run_c15_t3_p2q_demo.py
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2q_calibrated_depth.py
PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14* tests/test_c15*
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

## Deferred external validations

See `C15-T3-P2Q-deferred-validation-backlog-v1.json`. No OctoMap or OpenVDB
execution claim, no calibrated depth dataset scores, no quantitative map IoU,
no real sensor validation, and no Windows-native host certification.

References: OpenCV camera calibration / perspective projection documentation
(https://docs.opencv.org/3.3.1/d9/d0c/group__calib3d.html); OctoMap occupancy
representation (https://octomap.github.io/octomap/doc/index).
