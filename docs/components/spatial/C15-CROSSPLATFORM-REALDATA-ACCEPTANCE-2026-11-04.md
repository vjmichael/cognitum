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
