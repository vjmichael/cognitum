# Cognitum C15/T1 P2L — Appearance-aware identity association

**Date:** 2026-10-28. **Disposition:** Research-only P1 implementation and selected P2 validation passed; **real MOT17 appearance metrics unavailable** because the actual MOT17 *training* video frames are not present in the Library. Original P2K 6×6 Protobuf hypothesis engine remains untouched. Lu and GitHub untouched.

## Why P2L exists

P2K's dense position-only and velocity-only ablations underperformed original MPNTrack on three complete MOT17 sequences, in an identity-only test using MPNTrack's existing bounding boxes. P2K official aggregate baseline: MPNTrack HOTA 47.590 / IDF1 54.976 / 60 ID switches; position HOTA 41.365 / IDF1 45.563 / 186 switches; velocity HOTA 41.996 / IDF1 46.203 / 186 switches. Those *prior* scores are not new P2L scores.

P2L implements a separate offline, research-only appearance-aware research arm, reusing `cognitum.spatial.v1.AppearanceDescriptor` and its existing Protobuf binding. External descriptors are **format-checked** and bound to frame bytes, frame sequence, source box coordinates and ordinal, encoder ID, and encoder specification digest. These SHA-256 fields **are not cryptographic authentication** of camera origin or actual encoder execution. No identity hypothesis grants host/model authority; top-1 remains a benchmark-only forced label.

## Implemented P1/P2 components

- `cognitum/spatial_p2l_appearance.py`: CPU-only grayscale 4×4 spatial-tile × 8-bin histogram (128D normalized), as a deterministic *handcrafted visual comparator*, **not trained ReID**; Protobuf descriptor construction; combined motion/cosine Hungarian matching with bounded track counts, expiring stale tracks, explicit distinct frame timing, per-frame cap and pinned descriptor format checks.
- `tools/run_c15_p2l_frame_study.py`: prepares image-backed matched-box association arms using real frames when available; fails closed with `blocked_real_mot17_train_frames_missing` and `official_metrics: null` when missing. Sources MPNTrack boxes from TrackEval data ZIP; source identities never enter candidate association. GT is never read by this runner. Original (unmodified ID) arm is preserved only for **later independent scoring**. The output consists of paired MOT-style prediction files and hashes; it does not claim those files have already been officially scored.
- `tools/run_c15_p2l_synthetic_study.py`: deterministic four-frame image-sequence tests with known synthetic identity continuity held out from association inputs. Records ties/failures, not just wins.
- Focused negative tests: missing images, swapped frames, swapped vectors, corrupted encoder digest, changed geometry, incomplete/extra descriptors, invalid config, inaccessible crops, short/long observation gaps, no-data rejection, identical-looking objects, prohibition on real-score claims.
- Explicit optional `spatial-appearance-reference` dependencies: protobuf, Pillow, NumPy, SciPy. Default Cognitum installation remains dependency-free; no pretrained weights installed or assumed.

## Synthetic comparison (not MOT17)

Identities retained relative to the first frame, on 8 object observations per case:

| Scenario | P2K position | P2K velocity | P2L appearance + velocity |
|---|---:|---:|---:|
| Uniform crossing speed with distinct grayscale cues | 4/8 | 8/8 | 8/8 |
| Abrupt acceleration/crossing with distinct grayscale cues | 4/8 | 6/8 | 8/8 |
| Abrupt acceleration with *indistinguishable grayscale appearance* | 4/8 | 6/8 | 6/8 |

These are **scripted controlled synthetic observations** with image pixels generated for each position, not annotated public videos, detector benchmarks, learned feature evaluations, or claims of statistical superiority. There is no evidence of generalization to actual pedestrian videos. The unchanged standard MPNTrack baseline cannot be compared from these synthetic identity-retention scores.

## Real-data gate

Confirmed Library contains:

- `Cognitum/Datasets/TrackEval/data.zip`: official benchmark examples, tracking predictions, annotations; PNG images in this ZIP belong to **DAVIS masks**, not MOT17 pedestrian source video frames.
- `Cognitum/Datasets/TrackEval/TrackEval-master.zip`: evaluator source.
- `Cognitum/Datasets/MOT17/MOT17Labels.zip`: MOT17 annotations and metadata but **not source JPEG frames**.

The screenshots of `MOT17-test.zip.001` ... `.007` are not files uploaded to the Library, and the MOT17 **test** frames cannot supply public official test GT for local IDF1/HOTA scoring. To run the real image-backed P2L study, upload a MOT17 **training** sequence, such as `MOT17-02-DPM/img1/000001.jpg`, preferably a small first-window or an archive containing that sequence. Ensure license and provenance are retained. A learned ReID model with pinned weights and its own validation is a further independent dependency; a grayscale histogram is not an adequate substitute.

Example preflight after receiving frames (paths are examples):

```bash
PYTHONPATH=. python tools/run_c15_p2l_frame_study.py \
  --data-zip /path/to/TrackEval/data.zip \
  --frames-dir /path/to/MOT17/train/MOT17-02-DPM/img1 \
  --sequence MOT17-02-DPM --frames 120 \
  --output /path/to/new-empty-P2L-output \
  --report /path/to/P2L-evidence.json
```

This emits four prediction arms with *identical boxes/confidence* and an image/feature provenance manifest when the frames exist. A separate official TrackEval stage must then be assembled with matching truncated ground truth, sequence length and preprocessing to measure real HOTA/MOTA/IDF1. **The runner itself does not calculate or claim official scores.**

## Current verification

- 19 focused new tests passed with 5 additional subtests; combined legacy and new selected C13/C14/C15 regression: 1,124 passed, 39 skipped, 558 additional subtests; five nonfatal warnings, Linux/Python 3.13.
- 61/61 independently compiled Protobuf source/binding checks pass; no Protobuf source changes.
- Real MOT17 frame preflight actually run: `blocked_real_mot17_train_frames_missing`, `official_metrics: null`, with process status 2.
- No full unrestricted repo test, Windows-native integration, production/ReID parity, detector-independent evaluation, permission or privacy certification.

## Existing mature comparators / intended research next

- DeepSORT's appearance descriptor association with motion gating and cascaded matching: original project https://github.com/nwojke/deep_sort.
- BoT-SORT, appearance plus camera motion correction: https://github.com/NirAharon/BoT-SORT.
- Torchreid/OSNet offers trainable pretrained appearance encoders: https://github.com/KaiyangZhou/deep-person-reid.
- BoxMOT offers replaceable conventional tracking backends and ReID interfaces: https://github.com/mikel-brostrom/boxmot.

No code or pretrained weights from these external projects were copied or run in P2L. Their published results are not directly comparable with P2K's identity-only use of MPNTrack boxes. **P2L stays research-only/off by default**, and C15 P3 remains open until authentic full-frame inputs and competent conventional baselines are matched.
