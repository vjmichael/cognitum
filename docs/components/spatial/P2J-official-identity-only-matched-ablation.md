# Cognitum C15 T1 P2J — Matched identity-only ablation on authentic MOT17

**Date:** October 28, 2026 (US/Phoenix). **Result:** official TrackEval matched-input comparison completed; **tie on limited pilot**, no production authorization and no P3 improvement claim.

## Experiment and strict interpretation

- Sequence: **MOT17-05-DPM, original frames 1–120 of 837**. Preselected for the existing six-observation/six-track hard cap; not a held-out, representative, preregistered or full-sequence evaluation. This was capacity-aware sample choice after checking density. Repeating on multiple scenes is required.
- Boxes: **481 authentic MPNTrack prediction boxes**. One control retains their original MPNTrack IDs; the other removes the IDs *before* handing the identical box geometry to the real Cognitum `spatial_identity_association.propose` engine. No independent detector has been executed. Both use identical GT, time window, frame cropping, output geometry, score values, evaluator, and MOT17 preprocessing.
- Real GT: source labels match the independently uploaded `MOT17Labels.zip`; the GT data is passed only to the evaluator and is never supplied to Cognitum.
- The two output text files are identical except column 2 (track ID). Post-hoc, all **nine** identity streams form a single bijective label permutation, which is why official metrics tie. The post-hoc mapping was NOT an algorithm input.
- Cognitum's native module proposes bounded hypotheses, **not authorized scene updates**. This offline experiment forces its top-ranked proposal even on **119/119 ambiguous proposals** to generate comparable tracker files. That policy is NOT permitted as a production rule and is the central limitation of this ablation.
- The XY image centers were divided by 100 and fed to metre-labeled offline scene fields as **proxy units**. No camera calibration, 3D world coordinate conversion, height/depth inference, or physical-world identity proof is implied. No learned appearance embeddings were used.

## Official TrackEval results (metric scale 0–100, counts where noted)

| Metric | MPNTrack unchanged IDs | Cognitum position proposals | Difference |
|:--|--:|--:|--:|
| HOTA | 46.862 | 46.862 | 0.000 |
| DetA | 38.010 | 38.010 | 0.000 |
| AssA | 57.840 | 57.840 | 0.000 |
| MOTA | 43.309 | 43.309 | 0.000 |
| IDF1 | 54.658 | 54.658 | 0.000 |
| ID switches | 1 | 1 | 0 |
| CLEAR TP / FN / FP | 453 / 526 / 28 | 453 / 526 / 28 | 0 |

**These are first-120-frame, identity-only comparison scores; they must not be compared numerically to the previous full 21-sequence MPNTrack aggregate (HOTA 61.904 / MOTA 64.399 / IDF1 71.206).** No claim that Cognitum equals, matches or outperforms full MPNTrack generally follows from this pilot.

## Execution provenance

- Official TrackEval source pinned commit `12c8791b303e0a0b50f753af204249e622d0281a`, complete **86-file ZIP-to-Git-tree verification**, tree hash `ce583e59d96b33aad5f8f62149d96bc6bc4d8f96`.
- Linux Python 3.13, opt-in NumPy legacy alias wrapper outside unchanged TrackEval code. `HOTA CLEAR Identity`, official MOT17 `DO_PREPROC=True` in **one evaluator invocation** for both competitors.
- Source ZIPs remained external in Library; original raw GT, MPNTrack prediction ZIP, independent labels ZIP, and official evaluator source were not edited or redistributed here.
- **New tests:** 11 passed + 4 subtests for ID leakage prevention, six-object limit, numerical input rejection, deterministic association, one-to-one ID safety and ambiguous collision.
- **Selected C13/C14/C15 tests:** 1,091 passed, 39 skipped, 547 additional subtests passed; 5 warnings. **61/61 independent Protobuf descriptor compilations verified**. Unrestricted repository suite and native Windows testing were not asserted.

## Reproduction (run in extracted source root)

```bash
PYTHONPATH=. python tools/run_c15_p2j_matched_identity.py \
  --data-zip /path/data.zip \
  --labels-zip /path/MOT17Labels.zip \
  --stage /tmp/empty-c15-p2j-stage \
  --trackeval-root /path/TrackEval-master \
  --source-zip /path/TrackEval-master.zip \
  --out /tmp/c15_p2j_evidence.json
```

The stage directory must be **empty**. Source verification is fail-closed, and prior evaluator summaries are rejected. Canonical P1 scene-graph data/provenance/auth requirements are **not** overridden by this offline coordinate shim.

## Next measurable work

1. Independent detector inputs from MOT17 (not MPNTrack-produced boxes), frame handling, and externally measurable detector/embedding provenance for genuine stand-alone tracking comparison.
2. Scale the bounded six-by-six hypothesis engine explicitly or adopt a reviewed assignment backend with capacity-safe complexity; do not silently drop crowded frames.
3. Compare the association-only policy in crossing, occlusion, long-gap, and appearance-similarity adversarial cases on multiple sequences and held-out configurations, retaining ambiguity/abstention.
4. Only then attempt full P3 matched Lu+transformer / Cognitum-with-and-without trials, permission boundaries, and Windows-native verification.

**Scope:** Cognitum source snapshot and offline tests only. Lu, GitHub, and all uploaded source datasets left unchanged.
