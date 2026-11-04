# C15 cross-platform and real-world tracking acceptance — November 4, 2026

## 1. Verified native cross-platform baseline

At PR #71 commit `8ae637ab0ab22a4b29bda314e83561cf724330cb`,
[GitHub C15 native workflow 41806431596](https://github.com/vjmichael/cognitum/actions/runs/41806431596)
completed with **success** on:
- Windows / CPython 3.11
- Windows / CPython 3.13
- Ubuntu / CPython 3.11
- Ubuntu / CPython 3.13

Actual success steps included importing NumPy/SciPy/OpenCV, real Hungarian and
rotation tests, compiled Protobuf schema parity, full C15 lifecycle/SQLite
restart, source scope, appearance and synthetic challenge, MOT diagnostics,
official evaluator refusal tests. This is **component-level cross-platform
acceptance**; it does not demonstrate real scene perception accuracy.

On the SAME SHA, [global Python regression 41806431620](https://github.com/vjmichael/cognitum/actions/runs/41806431620)
**failed**. Investigation showed two independent categories:
1. The global workflow installed only `security,scientific` extras despite
   importing optional C15 SciPy/OpenCV tests. The Linux suite failed with
   NumPy/SciPy/cv2 missing and corresponding C15 `UNSUPPORTED` results.
2. Windows global `unittest discover` attempted Linux-only cgroup, pipe2,
   fcntl and host-recovery test modules, which require a Linux kernel.
   These failures were unrelated to C15 tracking algorithm correctness.

**Remediation committed:** `.github/workflows/python-tests.yml` now
installs `spatial-vision` in the core regression matrix; the suite is run
by `tools/run_crossplatform_regression.py`. Linux runs all modules, while
Windows explicitly lists and does not load five Linux-only module families
(`test_host_recovery`, `test_lu_linux_readiness`,
`test_p46r5_handoff_integration`,
`test_p46r8_recovery_cli_hardening`, `test_recovery_service`).
Those are NOT counted as Windows passes; the real Linux matrix runs them.
All portable modules remain tested on both platforms. If new kernel-only
test modules are introduced the explicit manifest must be reviewed, not
hidden by blanket skip patterns.

**Latest-head workflow remains required** after these workflow changes;
historical passing head does not automatically certify new code.

## 2. Real-world benchmark protocol

Official [MOTChallenge/TrackEval](https://github.com/JonathonLuiten/TrackEval)
supports MOT17 HOTA/DetA/AssA, MOTA and identity metrics. Benchmark input
must preserve actual detector detections, separate publicly licensed ground
truth, prediction identity and matching evaluation conditions. Do NOT use
ground truth as tracker input, invent perfect detections or present toy
identity tests as official leaderboard evidence.

The public [Roboflow Trackers download/evaluation workflow](https://trackers.roboflow.com/latest/learn/download/)
supports MOT17 *validation* annotations/detections. This benchmark is
licensed under **CC BY-NC-SA 3.0** (noncommercial/attribution/share-alike);
use only where license permits. Do not redistribute the dataset in CI
artifacts or infer rights for Lu commercial packaging.

- `tools/c15_real_mot_acceptance.py`: loads only `det.txt` first, sends
  detector boxes to actual C15 `spatial_tracking.update` (SciPy gated
  Hungarian matching), initiates new baseline track IDs only from
  previously unmatched *detector* boxes, and writes valid MOTChallenge-format
  prediction rows. Only **after** prediction output is frozen does it
  load separate ground truth for transparent nonofficial diagnostics.
- The 64-track/64-detection hard bounds are retained; input filtering
  uses detector confidence only, and records every dropped observation.
  Dropping detections can reduce recall and must appear in the report.
- Outputs include GT/detector/prediction SHA-256 digests, exact number of
  frames/rows, dropped detections, component tracking wall time and honest
  diagnostics (`not_official_motchallenge_metrics`).
- `.github/workflows/c15-real-mot17.yml`: downloads MOT17 *validation*
  `annotations,detections` (not image frames) and runs C15 on
  `MOT17-02-FRCNN` before computing official-style standard HOTA/MOTA/IDF1
  through the maintained Roboflow `trackers eval` package. It separately
  runs **ByteTrack** against the *same* independent detections and evaluates
  under the same metrics. Archives prediction/score JSON for 14 days,
  **without GT/detector/image dataset files**.
- The original `spatial_official_trackeval.py` remains a distinct adapter
  requiring a pinned official external TrackEval checkout. Roboflow
  `trackers eval` scoring is a real established library result but should
  not be described as an independently source-pinned official MOTChallenge
  submission without a pinned TrackEval checkout and verified source.
- `tests/test_c15_real_mot_acceptance.py` validates GT/detector separation,
  non-overwrite of evaluation artifacts, licensing-gate behavior and 64-track
  capacity accounting on deliberately **synthetic contract fixtures**. These
  tests are not real-data benchmark scores.

## 3. Acceptance checklist

- [x] C15 real SciPy/OpenCV Windows/Linux Python 3.11/3.13 native
      **previous-head** run passed (workflow 41806431596).
- [x] Root cause of unrelated global regression failure identified.
- [x] Explicit portable-vs-kernel-only CI partition and correct dependency
      installation committed.
- [x] Real public-detector tracking runner, dataset acquisition, baseline
      comparison workflow, provenance digests and fixture negative tests
      committed.
- [ ] Latest exact branch-head C15 native matrix passes.
- [ ] Latest exact branch-head global regression passes in all four
      environments (Linux-only tests transparently excluded on Windows).
- [ ] Real MOT17 validation dataset successfully acquired on runner.
- [ ] Actual C15 vs ByteTrack standard metric scores computed, preserved
      and compared on the same input rows with dropped detections reported.
- [ ] Pinned official TrackEval verification and more than one held-out
      sequence/detector quality, source/dataset redistribution review.
- [ ] Actual OS-isolated Lu worker authentication/source consent and
      real-model task-level efficacy benchmarks (distinct integration gate).

No C15 overall closure or merge should be claimed before all *required*
current-head tests pass. A genuine low score is still a valid benchmark:
do not falsify or tune results against held-out labels to force a win.

## 4. First actual public-data execution evidence (not official metrics)

[GitHub run 41851706457](https://github.com/vjmichael/cognitum/actions/runs/41851706457)
successfully downloaded MOT17 validation ground truth and independently supplied
FRCNN detector observations, and executed C15's actual SciPy association on
`MOT17-02-FRCNN` **before opening the ground-truth file**.

Runner diagnostics, taken directly from the CI log:
- 299 frames; **4,009 public detector rows**, **4,009 C15 prediction rows**,
  **zero detector rows dropped** under the bounded 64-track capacity.
- 9,880 reference ground-truth boxes, 3,273 matched boxes, 6,607 false
  negatives, 736 false positives; **63 diagnostic identity switches**.
- Diagnostic global identity overlap F1: **0.3104615163** (not official IDF1).
- Measured aggregate C15 association time: **112.638 milliseconds** on
  that GitHub runner (excludes reading, evaluation, download and startup).
- SHA-256 input/source/prediction digests recorded in the job output and
  uploaded benchmark evidence artifact.

That run then **failed** on `trackers eval` CLI argument syntax. This is an
evaluator invocation failure, not an invented low-or-high official score.
The installed `trackers==2.6.1` expects `--tracker` (not newer
`--predictions`) and lists supplied as `--metrics CLEAR HOTA Identity`,
not `'[CLEAR,HOTA,Identity]'`. These have been corrected on the branch.
No official/standard HOTA/MOTA/IDF1 figures or ByteTrack comparator are
available until a corrected run completes.


## 5. Standardized MOT17 scoring on real detector data

[GitHub run 41852112626](https://github.com/vjmichael/cognitum/actions/runs/41852112626)
successfully scored the frozen C15 `MOT17-02-FRCNN` predictions using the
installed `trackers==2.6.1` standardized benchmark evaluator:

| Metric | C15 score |
|---|---:|
| MOTA | **30.202** |
| HOTA | **31.143** |
| IDF1 | **34.205** |

Same 299 frames, 4009 public detections and 0 capacity drops. C15 tracking
time was 106.127 ms in that run, excluding disk, external scoring and setup.
The result is a **genuine measured real-data baseline**, not a synthetic
regression or independent *official submission*. Scores are evaluator outputs,
not percentages of development completion. A low result is expected for a
minimal IoU/Hungarian tracker and must remain unmodified.

That workflow then failed only at the **ByteTrack comparator CLI step**:
installed `trackers 2.6.1` rejected newer
`--detection.mot_file` / `--output.mot_results` argument names. The
workflow now uses 2.6-compatible legacy `--detections` and `--mot-output`,
while preserving the identical public detector input path. Until this
comparator step succeeds, no relative C15-versus-ByteTrack claim is valid.

The current closeout rules require this real-data workflow, native Windows/
Linux matrix and portable/core regression to pass at the **same exact latest
PR SHA**, not merely earlier heads.


## 6. Matched real C15 versus ByteTrack evaluation

[GitHub workflow 41852572707](https://github.com/vjmichael/cognitum/actions/runs/41852572707)
completed successfully using installed `trackers==2.6.1` on the real public
`MOT17-02-FRCNN` validation detector rows. Both C15 and the established
ByteTrack baseline used the **same independent detection file**, not GT input:

| Standardized metric (higher is better) | C15 SciPy Hungarian | ByteTrack | C15 − ByteTrack |
|---|---:|---:|---:|
| MOTA | 30.202 | 30.213 | −0.011 |
| HOTA | 31.143 | 35.468 | −4.325 |
| IDF1 | 34.205 | 38.501 | −4.296 |

The workflow saved C15 and ByteTrack prediction files and each evaluator
score JSON as CI artifacts; dataset bytes were excluded. This is an actual
single-sequence measured comparison. **ByteTrack wins HOTA and IDF1.** We
must not tune using that same validation sequence and claim the improved
score is held-out.

The additional, independent `TrackEval` official-reference verification now
checks out pinned commit
`12c8791b303e0a0b50f753af204249e622d0281a`,
prepares original GT and the two frozen predictions via
`tools/c15_stage_trackeval.py`, and executes reference HOTA/CLEAR/Identity
scoring. Its code and regression contract are committed, **but this pinned
official-reference step has not yet been shown to succeed**. The original
2022 source revision must be identified in any acceptance report and its
metrics may not be conflated with the newer `trackers eval` CLI scores,
especially when preprocessing and ignore-region policies differ.

The global regression now installs `spatial-vision` and `causal-stats`, runs
its harness as a Python package module to preserve `tools` and `tests`
imports, and explicitly segregates Linux kernel-only recovery tests on
Windows. This reconciliation must also pass on the latest PR head before
merge; cross-platform success of the C15-specific matrix alone is not
sufficient proof of the full repository.

Superseded GitHub Actions runs are canceled through per-workflow/ref
concurrency. Cancellation of stale revisions is not a test failure; **only
the latest exact-head completed checks count for closeout**.
