# Cognitum C15 P1 observation contract update + T1 P2F external evaluator gate

**Date:** 2026-10-28. **Disposition:** New P1 wire contract and staging implemented, adversarial tests passed; **official TrackEval metric parity NOT run** (external engine and full dataset source files unavailable locally). Research-only; no Lu, GitHub, Windows, or native sensor changes.

## Motivation / P0 finding

P0 re-audit found that the T1 3D identity contracts cannot express all information necessary to evaluate 2D multi-object tracking, open-world object instances, and mask-based tracks. The additive `benchmark_observation.proto` is a *transport and evaluation adapter* rather than a replacement of the canonical P1 scene graph. It supports both GT and tracker observations without merging their authority domains.

### P1 versioned schema

`proto/cognitum/spatial/v1/benchmark_observation.proto` has `schema_version == 1`, enum `ObservationRole` (`GROUND_TRUTH`, `DETECTION`, `TRACKER_PREDICTION`), and explicit optional fields for ID, confidence, nanosecond timestamp and GT visibility. It contains sequence/frame, class id and label, image and camera-frame metadata, pixel-space bounding boxes, and uncompressed, **column-major** COCO mask RLE. It includes dataset identity/version, source URI, annotation version and SHA-256 digest of external source bytes. **SHA-256 does not authenticate a sensor, a curator, a publisher, a class or a human identity.** The contract is research-only and cannot grant authority.

Strict checks include: source hash 32-byte shape; unknown fields rejected; missing and zero are distinct; no GT ID on detector inputs; GT and tracker predictions require an ID; duplicate within-frame IDs rejected; monotonic timestamps per camera; nonfinite/negative geometry rejected; exact mask size / RLE totals; malformed COCO compressed RLE rejected rather than silently interpreted; GT-only ignore and visibility; no mask drops into a bounding-box evaluator. GT rectangles partially outside image bounds are accepted because authentic 2D annotations may be clipped or out of frame. Detection confidence is required; tracker prediction confidence can be absent (MOTChallenge `-1` placeholder), not misreported as probability zero.

### Supported adapters

- Strict MOTChallenge 10-column text import for GT, detections and predictions, with an **explicit legacy GT option** for MOT15/TUD-style `-1` class/visibility sentinels. The source file bytes are hashed, but not included in the archive.
- Restricted COCO-video JSON import. Requires a real `video_id`, `frame_index`, image dimensions and explicit annotation role. Accepts bbox, uncompressed RLE masks and optional recorded timestamps. Does NOT accept arbitrary still-image COCO files as tracking sequences, COCO compressed masks, TAO-specific category mapping, BDD100K proprietary keys, segmentation polygon inference, or hidden camera calibration.
- Conservative MOTChallenge bounding-box export. **Fails closed for masks and nonpedestrian categories**: mask tracking needs original MOTS/RobMOTS engine, and TAO/BDD100K require their own evaluators rather than forced fake MOT pedestrians.
- No automatic conversion of annotation IDs into model predictions; input roles must remain separate.

### P2F external TrackEval gate

`cognitum/spatial_trackeval_bridge.py` stages a valid MOTChallenge-like tree:

```
<staging>/gt/MOT17-train/<sequence>/gt/gt.txt
<staging>/gt/MOT17-train/<sequence>/seqinfo.ini
<staging>/gt/seqmaps/MOT17-train.txt
<staging>/trackers/MOT17-train/<tracker>/data/<sequence>.txt
```

A genuine separately installed/checked-out TrackEval may be invoked with `--DO_PREPROC False` for controlled custom data, `--METRICS HOTA CLEAR Identity`, explicit source paths and bounded execution timeout. Its summary is parsed only on an actual success return; HOTA, MOTA and IDF1 must all be present. Failure, timeout, missing checkout or incomplete outputs cause a blocked/failed result **without any manufactured score**. The runner records script and summary hashes, but those hashes **are not signatures**, and source checkout revision authentication remains a separate external gate. `frameRate=1` in generated `seqinfo.ini` is only a TrackEval-compatible placeholder; **not a source-video FPS measurement**.

### Runnable reproduction with genuinely acquired files

```
PYTHONPATH=. python tools/c15_p2f_trackeval_probe.py \
  --gt /data/gt.txt --pred /data/pred.txt \
  --staging /tmp/c15-trackeval-stage \
  --sequence MySequence --width 1920 --height 1080 \
  --trackeval-root /path/to/pinned/TrackEval \
  --out /tmp/c15-p2f-results.json
```

For the older pinned TUD-Campus `gt.txt`, add `--legacy-gt`. `--trackeval-root` is optional; omit it to inspect output staging and the honest `blocked_external_engine_missing` status. Running with real data requires a real external **tracker output**; supplying a ground-truth file as `--pred` is not an acceptable benchmark even if the runner can only structurally check the difference in path and data role. A real benchmark also requires a registered detector, appearance-feature provenance, matched frames, policies for ignore regions and independent auditing of the TrackEval checkout.

### Source references checked, not bundled

- TrackEval original project and evaluator: https://github.com/JonathonLuiten/TrackEval, `master` commit `12c8791b303e0a0b50f753af204249e622d0281a` as returned by the connected repository interface. Its documented metric families: HOTA, CLEAR, Identity. Its own README recommends normalizing custom benchmarks into MOTChallenge where appropriate.
- LaGOT annotations / tracking predictions: https://github.com/google-research-datasets/LaGOT, `main` commit `47428480d0e824524e10ede12848dbbe64a6461d`. Additional labels exist separately from LaSOT pixels, which must be independently acquired. The downloaded GitHub data ZIP entries are Git LFS pointers in this connector, not the underlying annotation archive.
- Earlier genuine TUD-Campus externally read labels: `cheind/py-motmetrics/motmetrics/data/TUD-Campus`, GT Git blob `182d09a1683b0e87349b00661d9cdcc1ffaf39df`, predictions Git blob `64b0fe10e177ea92dd9bbe0e9385d721edb33982`. P2E analysis was a diagnostic, not an official TrackEval run.

## Verification and limitations

- **52 new focused tests passed**: role isolation, Protobuf optional presence, serialized unknown field rejection, uncompressed RLE, COCO-video, MOT legacy and placeholder confidence, class/mask rejection, frame/time bounds, output path and file hashes, evaluator absent/failure and summary parsing.
- **C15: 291 pass; C13: 139 pass + 2 skips; C14: 615 pass + 37 skips; 61/61 independent Protobuf wire-schema checks.** No failures in these selected suites; not the unrestricted repository suite.
- Four-frame synthetic MOTChallenge staging actually executed; engine returned `blocked_external_engine_missing` as designed. The synthetic frameRate value has no empirical meaning.
- **No official HOTA/IDF1/MOTA score; no actual LaGOT sequence evaluated; no original DeepSORT/ByteTrack/OC-SORT/BoT-SORT tracker execution; no real appearance features or learned video embedding.** This P2F release is a *parity readiness and adapter validation checkpoint*, not a scientifically certified benchmark result.

## Next measurable gate

Acquire authentic LaGOT or MOT17 full annotation **and frame files** plus public tracker outputs, pin/verify an external TrackEval source checkout and its dependencies, run the genuine evaluator on the adapter-exported file tree, then compare HOTA/DetA/AssA/IDF1/MOTA and ID switches against independently published reference numbers. Follow with identical-input baseline tracker runs. Preserve the separate T2/T3 P2C scientific-engine parity gate and the deferred real LLM evaluations.
