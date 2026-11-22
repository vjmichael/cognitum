# Cognitum C15 Appearance Association R2.1 — reliability, gallery and targeted efficiency review

**Status:** engineering implementation and selected regressions passed; **performance NOT accepted**. R1 remains the frozen baseline. No Lu/GitHub edits.

## Changes

- Optional `reliability_updates`: update template only for a mature track after a sufficiently unambiguous, recent, appearance-compatible match. The default remains the original R2 policy.
- Optional `coherent_gallery`: a grayscale/color match must be supported by the **same historical snapshot**. No mixing independent feature-minima from unrelated past observations.
- Match-margin minima avoid allocating two `np.delete` arrays for each matched detection. **No standalone runtime gain is claimed.**
- Prior default R2 protobuf configuration hashes and predictions remain backward-compatible (checked in focused tests and compared to three prior pilot prediction files byte for byte).
- Research association proposals remain hypothetical; benchmark-forced labels have no permission/identity authority.

## Official pinned TrackEval results

The scores come from MOT17 GT/preprocessing and original MPNTrack detection boxes, using real training frames. The 120-frame pilot is a **nonstandard modified window**; the 837-frame check covers exactly one complete MOT17 training video, **not the whole MOT17 training benchmark**.

| Method | Pilot HOTA | Pilot IDF1 | Full MOT17-05 HOTA | Full MOT17-05 IDF1 | Full MOT17-05 switches |
|---|---:|---:|---:|---:|---:|
| CognitumR1Frozen | 60.677 | 63.762 | 42.827 | 49.767 | 45 |
| R2LegacyFrozen | 60.448 | 61.853 | 42.202 | 47.123 | 101 |
| R2ReliableUpdate | 60.538 | 62.241 | 39.172 | 41.127 | 107 |
| R2CoherentGallery | 60.440 | 61.853 | 41.338 | 45.239 | 104 |
| R2ReliableAndCoherent | 60.538 | 62.241 | 39.113 | 41.006 | 111 |

The stricter policy blocked 786 template updates during the full MOT17-05 run. This is a plausible mechanism for stale appearance templates, not proof of causation. The coherent gallery removes a provable historical-evidence cross-join but reduces complete-sequence score, so it remains opt-in for research.

## Targeted efficiency review (not a full profile)

1. High: image bytes are decoded/validated more than once across grayscale, color and each benchmark association arm. Add single-authority prevalidated per-frame cache with immutable provenance.
2. High: feature comparison is scalar Python per detection-track-gallery pair. Batch cosine operations with explicit finite/dimension checks and bounded memory.
3. Medium: Hungarian assignment grows rapidly in dense/long-gallery scenes. Use physics/appearance gate to prune candidates before constructing cost matrices, preserving no-silent-drop behavior.
4. Medium: Kalman measurement update computes tiny matrix inverses. Test analytical 2×2 solves with numerical parity, do not sacrifice Joseph covariance stability.
5. Already improved: `np.delete` temporary allocations removed from competitor-margin checks; not yet performance profiled.

All optimization proposals require byte-identical or explained identity-output comparisons, CPU and RSS measurements, and failure-path tests.

## Verification and limitations

- **1,282 selected tests passed**, 39 skipped, 574 subtests passed; **68/68 Protobuf** schema checks passed.
- 24 focused R2/R2.1 tests passed; three unchanged previous R2 pilot prediction files matched byte-for-byte.
- Pinned TrackEval commit: `12c8791b303e0a0b50f753af204249e622d0281a` and matching 86-file source tree.
- No independent detection, learned ReID, real-world camera certification, Windows validation or unseen full-sequence generalization.
- Prior v4 benchmark backlog retained in v5 as original entries, and new unsuccessful/efficiency tasks added.

**Decision:** preserve R1 and do not promote R2.1. Consider controlled template-aging / sample-quality model and an independent held-out full-video validation in a future milestone.