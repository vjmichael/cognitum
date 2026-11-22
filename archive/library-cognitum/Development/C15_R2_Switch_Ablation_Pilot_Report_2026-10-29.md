# C15 R2 switch-isolation pilot — 2026-10-29

**Decision:** The frozen **C15 R1** real-image grayscale+velocity associator remains the performance baseline. **R2 remains experimental.**

## Scope and methods

- Prespecified first 120 frames from MOT17-02-DPM, MOT17-05-DPM, MOT17-09-DPM (2,413 unchanged MPNTrack boxes). MOT17-09 is not a previously used Cognitum performance sequence, **but a 120-frame easy window is not a genuine unseen full-sequence generalization benchmark**.
- Both R1 and R2 assign identities without seeing original tracker IDs or ground-truth identities. Inputs are authentic images, native GT annotations cropped only by frame index, and the same original MPNTrack boxes.
- Official pinned TrackEval is executed with `DO_PREPROC=True`; however these **modified 120-frame subsets are not official full-MOT17 submissions**. The standard MOT17 `seqLength` metadata and GT rows are scoped to the first 120 frames for each research window, recorded in the study stage.
- The R1 code/configuration is **not edited**. R2 uses benchmark-only forced top-1 hypotheses (`ambiguous_abstention=False`), with ambiguity audit. This is not Lu identity authorization.
- Each R2 ablation turns exactly one of six **non-safety** feature switches off. The seventh feature (strict ambiguity abstention) was separately measured in R2 and is not switched on for metric-required identity tracks because it produces massive fragmentation; that result remains recorded in backlog v3.
- No tuning/search over parameters is done. These are diagnostic comparisons, not optimized candidates.

## Aggregate official TrackEval scores on the nonstandard pilot

| Arm | HOTA | IDF1 | ID switches |
|---|---:|---:|---:|
| MPNTrackFixed | 60.778 | 63.928 | 1 |
| CognitumR1Frozen | 60.677 | 63.762 | 2 |
| R2FullForced | 60.448 | 61.853 | 12 |
| R2OffAdaptiveAppearance | 60.500 | 62.047 | 10 |
| R2OffGuardedUpdates | 60.671 | 62.932 | 2 |
| R2OffColorFeatures | 60.642 | 63.098 | 4 |
| R2OffKalmanMotion | 60.645 | 63.071 | 9 |
| R2OffLongGapGallery | 60.738 | 63.873 | 7 |
| R2OffSizeGeometry | 60.114 | 60.664 | 17 |


## Interpretation

- Frozen R1 is 60.677 HOTA, 63.762 IDF1, 2 switches, compared with full forced R2 at 60.448 HOTA, 61.853 IDF1, 12 switches. **R2 does not beat R1 on this pilot.**
- Disabling guarded updates improves R2's IDF1 from 61.853 to 62.932 and switches from 12 to 2, suggesting the guarded template policy deserves investigation; this is not proof it is generally harmful.
- Disabling geometry increases switches from 12 to 17, suggesting the geometry gate helps on these windows.
- Disabling long-gap gallery has mixed effects: IDF1 63.873 versus R2 61.853, but switches 7 versus 12. It must not be promoted without a longer occlusion study.
- MOT17-09 was **not challenging in the first 120 frames**: all selected methods including R1, full R2 and some ablations matched 0 switches. Do not use this limited window as evidence of held-out generalization.
- All scores here are **identity-only**: original MPNTrack detections and frame pixels, not an independent detection pipeline or learned person ReID.

## Verification

- Matched input rows (frame and all columns except track identity), no dropped detections, image provenance bound to each descriptor and original GT absent from associator call.
- Pinned TrackEval rerun on the fixed prediction files returned **byte-identical aggregate score summaries** for every arm.
- Selected C13/C14/C15 regressions: 1,275 passed, 39 skipped; 574 subtests passed. 68/68 Protobuf schemas verify independently.
- The new focused tests include switch isolation, truncation, invalid track IDs and missing-row failure paths. No Windows-native tests and no unrestricted repo test claim.

## Next action

Keep R1 frozen. Investigate template-update suppression (rather than removing guards universally), test long occlusions and camera motion, then run full-length per-sequence ablations with independent challenge splits before accepting any R2 feature combination.

**No edits to Lu, GitHub, original MOT17 archives, R1 source, or baseline test artifacts.**