# C15 — Practical spatial core: scene geometry and identity association

**Date:** 2026-11-04. **Status:** New focused implementation committed for native CI. No real-sensor, Lu host, or perceptual-model certification.

## Source-history reconciliation

The historical [C15 source checkpoint PR #19](https://github.com/vjmichael/cognitum/pull/19) remains **open**, with 611 changed files and many previous T3/T4 research experiments. It includes an extensive scene/volume/tracking and signed-evidence stack that did not reach current `main`. Its last native C15 portable tests succeeded, but the same head's full Python regression **failed** (59 failures and 45 errors in that historical run, including cross-component C14 assertions). The historical component's local ZIP evidence is not proof of actual Windows execution, authenticated perception, instrument calibration or Lu permissions.

**Do not bulk merge or replace the older source branch.** Keep PR #19 as an independently reviewable archive and source of design/fixtures; reconcile it in small batches against latest `main` only if there is a concrete requirement not met by this bounded core. This branch is additive and does not rewrite historical C15 tracking research.

## Library adoption

The practical baseline uses mature `numpy` and `scipy`:

- `scipy.spatial.transform.Rotation.from_quat` for metric frame transforms and quaternion rotation, instead of hand-written 3-D quaternion engines.
- `scipy.optimize.linear_sum_assignment` for globally optimized gated detection-to-track assignments (Hungarian/Jonker-Volgenant family), instead of custom combinatorial matching.
- Small explicit independent rectangle overlap/scene-state checks verify candidate geometry, permissions absence, original source metadata and stable IDs; they are **not learned detectors**.

`opencv-python`, TrackEval, BoT-SORT, ByteTrack and image/appearance encoders are candidates for **separate perception/real-MOT experiments**, not mandatory dependencies for a no-camera typed spatial-core module. Their licenses, training weights, dataset licensing, genuine evaluation and GPU cost must be reviewed before adopting a product capability. Capsule models remain research challengers, never conflated with a typed spatial pose.

## Implemented bounded scope

- `cognitum/spatial_geometry.py`: versioned scene objects with stable IDs, observation-source string, timestamp, visibility, metric position and dimensions, and explicit parent coordinate frames anchored to `world`. Frame graph rejects missing parents, cycles, duplicate IDs, invalid coordinates, nonfinite dimensions, and invalid quaternions. World position and simple relations (distance, coincident, x-left-of, z-below) are computed using SciPy rigid rotations and translations.
- `cognitum/spatial_tracking.py`: up to 64 prior tracks and detections, positive-area 2D bounding boxes, IoU and centre-distance gated assignment through SciPy, controlled missed-observation ageing up to eight steps, reappearance retaining previous stable ID on validated match, explicit unmatched detections and retired IDs. A new raw detection does not silently mint a stable world identity or bypass source review.
- `proto/cognitum/spatial_core/v1/spatial_core.proto`, `cognitum/proto/spatial_core_pb2.py`, `cognitum/spatial_core_wire.py`: strictly typed scene query and association request/response. Canonical Protobuf rejects unknown/noncanonical/duplicate fields and oversized frames; replies are re-executed against the original typed request and checked byte-for-byte. Request SHA-256 provides **correlation**, not authentication.
- `tests/test_c15_spatial_core.py` and `tests/test_c15_spatial_wire.py`: real SciPy transforms, quaternion rotation, provenance/time rejection, identity-preserving crossing/reordered detections, occlusion/reappearance/retirement, untrusted far observation, alias duplication, forged response identities, malformed/unknown protobuf, and missing sensor/permission fields.
- `.github/workflows/c15-spatial-core.yml`: Windows/Linux × Python 3.11/3.13, real NumPy/SciPy imports and tests, separately compiled Protobuf schema parity.

## Honest guarantees and limits

**Validated within the typed model, not perception truth:** A stable ID references a caller-defined track, not an authenticated real object. Hungarian assignment does not solve arbitrary target identity swaps during long occlusion; shared appearance and ambiguous crossings need separate trusted appearance evidence and measured MOT benchmarks.

**No visual data ingestion:** This component accepts typed observations. It cannot acquire camera/screen data, infer object boxes or labels from images, open files, import scene assets, or operate on real-world tool permissions. Source strings do not authenticate observational provenance. `visible` is caller-supplied; physical occlusion reasoning is not inferred from raw pixels.

**No physics/certified units:** Metric metre coordinates and box width/height are caller-declared; cross-camera calibration, sensor uncertainty propagation, homography errors, robust SLAM, point clouds, capsule networks, graph neural networks and physically certified geometry are beyond this bounded core. There are no native worker launches or Lu model-visible tools.

**No invented scientific acceptance:** Historical P13B checkpoint synthetic signing/verifier gates are not proof of real instrument data or Windows host evidence. Full official MOT17/BDD100K/TAO identity benchmarks and matching baseline comparisons remain C15 research/acceptance gates if that functionality is wanted.

## Release conditions

Do not merge before current-head native CI and core Python regression pass. Once verified, this bounded spatial-core foundation can close as a practical component while full C15 learned tracking/vision and historical PR #19 remain separately accounted for. Real-world images and source provenance require Lu host authorization, worker isolation and user consent; C03 must evaluate true model A/B efficacy before product claims. Avoid C14-style unconstrained research expansion.
