# Cognitum C15 T1 P2I — Official pinned TrackEval execution

**Date:** 2026-10-28 (user local). **Disposition:** Verified external evaluator execution **completed for an existing MPNTrack baseline**, but **not** a Cognitum tracking-model efficacy or full adapter-parity result. **No Lu or GitHub modifications.**

## Verified materials and source integrity

- Library input: `Cognitum/Datasets/TrackEval/data.zip` (149,957,160 bytes, SHA-256: `148a4bdf56f8cb32f9bde4b3d70717242cbb2e61900ef0101abc4652e268f2a5`).
- Independent labels: `Cognitum/Datasets/MOT17/MOT17Labels.zip` (10,107,022 bytes, SHA-256: `0aa79322e91583369f42f17c4d79a0b145380d8732487bba59272048dc82b2b9`).
- TrackEval code: `Cognitum/Datasets/TrackEval/TrackEval-master.zip` (261,136 bytes, SHA-256: `5a089bf3638d1f3a7ae8383ccebf774146f7b1ceca1de989a97b55c76248eb5c`).
- TrackEval pinned GitHub commit: `12c8791b303e0a0b50f753af204249e622d0281a`.
- **All 86 archive files** reconstruct official Git tree hash `ce583e59d96b33aad5f8f62149d96bc6bc4d8f96`; checkout bytes were compared both before and after the successful run.
- All 64 staged GT, sequence-information, tracker-output, and seqmap files were hash-verified before and after. The 21 native MOT17 labels/MPNTrack predictions were not converted through Cognitum's simplified Protobuf observation export, avoiding loss of ignore/non-pedestrian classes.
- Runtime: Linux, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0. A separate opt-in launcher restores the old `np.float`, `np.int`, `np.bool` aliases at process startup; **TrackEval's pinned source itself is unchanged**. `pycocotools` is absent and TrackEval prints an optional BURST import warning, but MOTChallenge HOTA/CLEAR/Identity completed.

## Official MOT17-train results — MPNTrack existing tracker

**Standard MOT17 `DO_PREPROC=True`**, 21 train sequence/detector combinations (7 sequences × DPM/FRCNN/SDP); classes `pedestrian`, metrics HOTA/CLEAR/Identity. Values are 0–100 percent-style reporting for HOTA, MOTA and IDF1, not accuracy percentages.

| Metric | TrackEval official aggregate |
|---|---:|
| HOTA | **61.904** |
| DetA | 57.989 |
| AssA | 66.240 |
| MOTA | **64.399** |
| IDF1 | **71.206** |
| ID switches (IDSW) | 482 |
| CLEAR true positives | 223,153 |
| CLEAR false negatives | 113,738 |
| CLEAR false positives | 5,715 |

- The single-sequence `MOT17-02-DPM` run produced HOTA 43.339, MOTA 39.040, IDF1 48.608.
- Repeated CLI single-sequence run reproduced those scores exactly.
- Independently executed single-sequence output matches the corresponding row in the 21-sequence official detailed report on **276 common fields**, zero mismatches.
- The first 21-sequence run and the pinned-verified repeat produced the same aggregate numbers.
- Per-sequence values: `Cognitum_C15_P2I_TrackEval_Per_Sequence_2026-10-28.csv`. Full original evaluator `pedestrian_detailed.csv` and `pedestrian_summary.txt` are included in the source checkpoint's evidence directory, not the raw datasets.

## Corrections to Cognitum (no changes to TrackEval)

1. Fixed a runner configuration error: `--SEQMAP_FILE` was incorrectly supplied explicitly; pinned TrackEval's parser treats this parameter as a list. Let the official default resolve `GT_FOLDER/seqmaps/MOT17-train.txt`.
2. Added opt-in legacy NumPy dtype-compatibility launcher outside TrackEval, preserving original evaluator bytes and metric code.
3. Added complete ZIP-to-Git-tree verification for the pinned commit, plus exact extracted-checkout content checks before and after an evaluator run; archive manipulation fails closed.
4. Added source-integrity and CLI option regression tests. The official run remains constrained to authentic native MOT17 format with standard preprocessing.

## Verification

- C13/C14/C15 selected suites: **1,080 passed, 39 skipped; 543 additional subtests passed** (23.58 sec). Five warnings; no selected-test failures.
- Independently compiled/checked **61 Protobuf source/binding schemas**.
- Reproducible one-sequence end-to-end CLI run: **passed** with source ZIP verification, alias shim, and official metrics.
- Source checkout is an external evaluator, not a Cognitum CE or a Lu integration; no Windows-native TrackEval/CE test performed. The full unrestricted Cognitum suite remains unclaimed.

## Reproduction after obtaining the three Library ZIP files

Unzip `TrackEval-master.zip` into an isolated directory (`/path/TrackEval-master`), and unzip this **Cognitum source snapshot** to an isolated directory. From the Cognitum directory:

```sh
PYTHONPATH=. python tools/run_c15_p2h_gate.py \
  --data-zip /path/to/data.zip \
  --labels-zip /path/to/MOT17Labels.zip \
  --stage /tmp/c15-official-fresh-stage \
  --out /tmp/c15-official-gate.json \
  --sequence MOT17-02-DPM \
  --trackeval-root /path/TrackEval-master \
  --source-zip /path/to/TrackEval-master.zip \
  --legacy-numpy-compat
```

Use a *fresh/empty* stage and a genuinely independent prediction source. TrackEval writes results next to the tracker outputs in the staging tree. For all 21, repeat `--sequence` for every sequence listed in the accompanying CSV (exclude `COMBINED`).

## Open scientific gates

- **No Cognitum-generated tracker outputs** were evaluated. A baseline's official metrics do not prove Cognitum performance improvement.
- No published reference score comparison (independent of the same evaluator code) or multi-implementation metric equivalence is claimed; only same-source evaluation and reproducibility.
- The canonical P1 Protobuf adapter cannot yet losslessly round-trip full MOT17 ignore regions and multi-class annotations; native-source staging is a parallel experimental path.
- Full video-based inference, learned appearance features and matched tracker model comparison are not run; they require frames, trained model checkpoints and reproducible detector/feature inputs.
- This does **not** close C15's OWL 2 / OctoMap / OpenVDB or T2/T3 scientific parity gates, nor security/host/Windows gates.

**Next:** Freeze this verified MPNTrack dataset/reference as a baseline; evaluate Cognitum's own T1 identity-association output on matched authentic inputs, then compare against strong conventional trackers using the same sequences, policies, initialization, and metrics. Keep separate T2/T3 geometry/scientific reference validation on the backlog.
