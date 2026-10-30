# Cognitum C15 T1 P2H — MOT17 genuine-data staging and independent cross-archive verification

**Checkpoint: 2026-10-28.** **Disposition: data gate PASSED, official metric parity still BLOCKED.**

Cognitum only. Research-only. Neither Lu nor GitHub was modified. Previous P2G archive remains immutable. This checkpoint extends the isolated P2G research working copy with a native benchmark staging path, 0-based-ID compatibility for *diagnostic* parsing, and adversarial tests. These are not approved production capabilities.

## Real materials actually used

- `/Cognitum/Datasets/TrackEval/data.zip` (149,957,160 bytes), user-supplied official TrackEval example-data archive.
- `/Cognitum/Datasets/MOT17/MOT17Labels.zip` (10,107,022 bytes), user-supplied MOT17 label archive.
- MOT17-train 21 named combinations = 7 distinct video sequences × 3 detector suffixes (`DPM`, `FRCNN`, `SDP`), not 21 independent videos.
- MPNTrack example **predictions are external tracker output**, not Cognitum model predictions or new tracker execution.

For **all 21** combinations, GT and `seqinfo.ini` from TrackEval's archive were checked for byte equality with the separate MOT17Labels archive, and native prediction/label bytes were staged unmodified. `seqinfo.ini` retains original source frame rate, dimensions and length; the derived sequence map selects exactly the requested sequences. SHA-256 is recorded for source archive bytes and all 64 staged files. These SHA hashes detect file changes; they are **not** publisher signatures.

## Key compatibility discovery and correction

Original MOT17 GT rows have **nine comma-separated columns**, include ignored regions and non-pedestrian classes, and must go through TrackEval's actual MOT17 preprocessor. The prior specialized Protobuf adapter expects a narrower schema/strict positive track IDs; it **must not** be used to fabricate canonical MOT17 results through a lossy or guessed conversion. Instead, `cognitum/spatial_mot17_realdata_gate.py` stages native source bytes and keeps roles separate. Original MPNTrack results use 0-based IDs in all 21 combinations. `cognitum/spatial_mot_adapter.py`'s diagnostics have been updated to accept ID zero rather than discard a valid track. This does **not** change the strict positive-ID canonical P1 Protobuf contract; original GT/prediction bytes are untouched.

For official MOT17 evaluation, `evaluate_with_official_trackeval(...)` requires actual TrackEval source and deliberately selects `--DO_PREPROC True`, unlike the synthetic/custom-P2F adapter path (`False`). Stale summaries, missing engine, invalid hash, bad names, nonmatching archives, illegal row formats and negative prediction IDs are rejected. The source revision is not authenticated merely because a checkout exists.

## Measured evidence

- Authentic 21-sequence stage: **21/21 independent label+metadata byte matches**, **64 staged files hashed and verified**, **614,103 GT rows**, **228,890 MPNTrack prediction rows**, **21/21 zero-based ID sources**.
- Independent internal diagnostic run on `MOT17-02-DPM`: 18,581 included pedestrian GT rows; 7,464 tracker prediction rows; 7,373 matched boxes; 23 diagnostic ID switches; heuristic global-IDF1 diagnostic 0.472413. **These are not official HOTA, MOTA or IDF1; diagnostic filtering/matching policies differ from official MOT17 preprocessing. Do not compare them with published TrackEval results.**
- Focused P2H synthetic tests: pass (metadata, roles, changed inputs, staging hashes, zero IDs, missing evaluator, negative IDs, wrong frame, invalid path/row formats).
- C15 selected regressions: **321 passed, 504 subtests passed**.
- C13+C14 selected regressions: **754 passed, 39 skipped, 39 subtests passed**.
- Compiler-based Protobuf source/binding verification: **61 / 61**.
- Sum selected tests: **1,075 passed, 39 skipped** (plus **543 subtests**); no unrestricted repository green claim, no Windows-native execution.

## Explicit remaining gate

The **official TrackEval Python source checkout** is not available in this runtime; the ZIP in `Cognitum/Datasets/TrackEval/` contains **example data only**. An attempted GitHub code-archive download was blocked by this runtime's network restrictions. Therefore TrackEval's genuine metric implementation **has NOT executed**, no official HOTA/DetA/AssA/IDF1/MOTA scores are claimed, and published benchmark-parity requirements remain OPEN.

One small independent source ZIP is sufficient to continue: download official TrackEval code from `https://github.com/JonathonLuiten/TrackEval`, ideally pinned at git commit `12c8791b303e0a0b50f753af204249e622d0281a` and supply the source checkout or ZIP. Do **not** upload the MOT17 data again. Install its minimum NumPy/SciPy dependencies (both available in this Linux environment), then run this gate with an explicit `--trackeval-root` path. The runner will only state an executed result with an unverified-source revision until source identity is independently checked.

## Reproduce

```bash
PYTHONPATH=. python tools/run_c15_p2h_gate.py \
  --data-zip /path/to/TrackEval/data.zip \
  --labels-zip /path/to/MOT17Labels.zip \
  --stage /fresh/temp/MOT17-02-DPM \
  --out /fresh/temp/P2H-data-evidence.json \
  --sequence MOT17-02-DPM \
  --trackeval-root /path/to/TrackEval
```

To stage the full 21-sequence collection, supply all 21 sequence names via repeated `--sequence` arguments. Use a *fresh* stage directory per run. Without `--trackeval-root`, the runner returns `blocked_official_evaluator_missing` and `official_scores: null`, which is the expected honest outcome for this checkpoint.

## Research promotion decision

Data integrity and native staging gate: **PASS**. Original P1 canonical Protobuf adapter and synthetic/custom data path: **unchanged**, except the pre-existing simple MOT diagnostic parser's ID-zero acceptance. Independent published score parity: **BLOCKED_EXTERNAL_EVALUATOR_MISSING**. C15 production/default-on/Lu integration: **NOT AUTHORIZED**.
