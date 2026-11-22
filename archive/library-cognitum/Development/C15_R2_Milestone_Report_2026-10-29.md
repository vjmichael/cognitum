# Cognitum C15 — Appearance Association R2 (experimental)

Date: 2026-10-29 UTC. This is a **research-only source checkpoint**, not a tracking-performance acceptance or Lu integration milestone.

## Implemented

- Adaptive appearance weighting based on similarities among active templates.
- Guarded image-template updates; conflicting/ambiguous evidence does not contaminate enrolled appearance templates.
- Pinned, 128-D spatial HSV appearance descriptor combined with the frozen R1 grayscale 128-D descriptor. **Not** a pretrained person-ReID encoder.
- Proper 4-state Kalman constant-velocity estimate with explicit process covariance, innovation gating and Joseph covariance update; research heuristics are not calibrated motion uncertainty.
- Size/overlap consistency and bounded re-entry using a finite appearance gallery.
- Explicit near-tie alternative identities, an abstention path with short-lived tentative tracks, and a separate benchmark-only forced-hypothesis path.
- Read-only protobuf R2ResearchReport with schema/version/model/config digest, ambiguity and no-authority flags. Previous source files remain intact except the descriptor registry addition.

## Official reproducible evaluation

The frozen matched-box study uses MOT17-02-DPM, MOT17-05-DPM and MOT17-13-DPM, unchanged MPNTrack input boxes, same real frame bytes and ground truth, the previously pinned official TrackEval (MOT17 preprocessing enabled). There are 18,512 source boxes and **no original or GT IDs exposed to the associator**.

| Method | HOTA | AssA | MOTA | IDF1 | IDSW |
|---|---:|---:|---:|---:|---:|
| MPNTrackOriginal | 47.590 | 53.586 | 45.945 | 54.976 | 60 |
| CognitumRealAppearanceVelocity | 44.173 | 46.194 | 45.786 | 48.952 | 99 |
| CognitumR2ForcedColor | 43.693 | 45.284 | 45.565 | 46.347 | 201 |
| CognitumR2ForcedGray | 42.799 | 43.375 | 45.611 | 46.695 | 186 |
| CognitumR2All | 41.108 | 39.899 | 37.399 | 45.028 | 3,248 |
| CognitumR2NoColor | 40.511 | 38.734 | 36.852 | 44.902 | 3,445 |

**Negative result:** R2 forced-color is -0.480 HOTA and -2.605 IDF1 versus frozen R1, with +102 ID switches. Strict abstention generates 3248 switches; this policy is not viable for the MOT metric's compulsory identity labels.

Color improves HOTA versus R2 forced-gray but **does not improve IDF1 or switches**; full independent switch ablations remain outstanding. The three sequences have been used during engineering and **are not an unseen holdout**; do not optimize to these then report gains as generalization.

## Verification

- Selected C13/C14/C15 suites: **1,271 passed, 39 skipped, 574 subtests passed**, including R2 tests.
- C07 suite: **218 passed**, 71 subtests passed.
- New focused R2 tests: **13 passed, 7 subtests passed**; source-binding forgery, size limits, separate switches, gray/color, Kalman covariance, delayed reentry, ambiguity and crowd capacity.
- **68/68 independently compiled Protobuf schemas** agree with checked-in Python bindings.
- Original P2L code, Lu, GitHub and the uploaded MOT17 dataset files were not modified.
- Actual sensor calibration, pretrained ReID, independent detector, Windows host tests and production security remain **unverified/deferred**.

## Recommendation

Freeze R1 as the performance baseline and keep R2 as an optional experimental component. Next run a prespecified ablation matrix on a validation split, then evaluate on **unseen** MOT17 train sequences. Do not silently tune on the same three-sequence score.