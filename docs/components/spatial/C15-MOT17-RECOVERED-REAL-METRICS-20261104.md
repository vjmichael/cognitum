# C15 vs ByteTrack: recovered real MOT17 validation metrics (NOT final official TrackEval)

Date: 2026-11-04
Evidence: GitHub Actions run 41862628132, artifact 13340462184
Source files: `c15-real-mot17-scores.json`, `bytetrack-real-mot17-scores.json`,
`c15-diagnostic.json`, `trackeval-staging-audit.txt`.
The source workflow used `trackers eval` for these metrics. The
**separate pinned official TrackEval step FAILED** with
`TypeError: stat: path should be string, bytes, os.PathLike or integer, not list`
before metrics could be produced. The CLI bug has been repaired on PR #71,
but the exact latest SHA has not yet executed the official checker.

## Real-data metrics from the earlier evaluation engine

Dataset: MOT17-02-FRCNN, 299 public-detection validation frames.
Both trackers used the same detection input, frozen before GT evaluation.
Values are expressed as percentages; differences are percentage points.

| Metric | C15 | ByteTrack | C15 - ByteTrack |
|---|---:|---:|---:|
| HOTA | 31.143264 | 35.467664 | -4.324400 |
| MOTA | 30.202429 | 30.212551 | -0.010121 |
| IDF1 | 34.205021 | 38.500645 | -4.295624 |

### Interpretation
- In these prior **real** test outputs, ByteTrack leads C15 on HOTA and
  identity F1; MOTA is nearly equal.
- This does **not** establish an official TrackEval score or MOTChallenge
  leaderboard result; the separately pinned official verifier failed to run.
- No claim that C15 is superior to ByteTrack. No additional optimization
  is required merely to record the evidence.

## Input/provenance and staging safeguards

- C15 detector SHA256:
  `bc4b9db23735d22333422a63457641f282ef2052fb583e04b155f8d820a475a6`.
- Frozen C15 predictions SHA256:
  `86c30ab3c6f1eeb2945c7d916dc5d2de5bab007d85f7b9c8792d3af11176ce18`.
- Ground-truth SHA256:
  `54cfe9a00b402996589c69ae348adc730ccb68254c51a434db291266f79a7b6a`.
- ByteTrack predicted file hash:
  `03d26ed97aed2430ea5f3b974041e3eaba4c015e596c5aca05570870631d37cf`.
- The TrackEval staging adapter excluded 221 ByteTrack `-1`
  (unassigned) detection placeholders, without renumbering valid identities.

## Official acceptance

The fixed pipeline on `c15-spatial-practical-20261104` now:
1. Downloads public MOT17 annotations and detections via `trackers`.
2. Freezes C15 and ByteTrack predictions from the same detections.
3. Stages ground truth only after generation of both predictions.
4. Uses the pinned official TrackEval checkout and its standard
   `GT_FOLDER/seqmaps/MOT17-train.txt` discovery.
5. Requires both official `pedestrian_summary.txt` files and extracts
   HOTA, MOTA, IDF1 into `evidence/trackeval-c15-vs-bytetrack.json`.

**Gate remains open until the repaired official workflow actually finishes
and its produced metrics are inspected.** The public GitHub connection
available in this session does not expose a workflow-dispatch action.
No fake or synthetic official scores have been substituted.
