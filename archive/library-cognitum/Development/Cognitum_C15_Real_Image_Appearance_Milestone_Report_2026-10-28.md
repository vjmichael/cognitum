# Cognitum C15 — Real MOT17 Appearance Benchmark (P2M-R1)

Date: 2026-10-28 (America/Phoenix) / 2026-10-29 UTC

## Outcome

**Official matched-box 3-sequence experiment completed**. The research-only 128-dimensional grayscale image histogram is an improvement over the P2K position/velocity-only association rules in the three-sequence aggregate, **but remains worse than the MPNTrack original identity baseline**. Sequence-by-sequence results are heterogeneous, including degradation on `MOT17-02-DPM`.

## Protocol / data provenance

* Full sequences preselected in P2K: `MOT17-02-DPM`, `MOT17-05-DPM`, `MOT17-13-DPM`; 2,187 elapsed frame slots, 2,186 frames with tracker boxes, 18,512 original MPNTrack prediction bounding boxes.
* Input frames: reconstructed byte-verified MOT17 training JPGs in `Cognitum/Datasets/MOT17`; matching annotations independently verified from `MOT17Labels.zip` in earlier dataset checkpoint.
* All five arms share exactly identical frame IDs, box coordinates, widths, heights, confidences, and metadata. Each proposed arm changes only the tracker ID column. 18,510 processed detections counted by TrackEval after official preprocessing; source rows total 18,512.
* Arms: MPNTrack source ID control; Cognitum P2K position; Cognitum P2K velocity; Cognitum P2L grayscale histogram + position; Cognitum P2L grayscale histogram + velocity.
* Associators never receive MPNTrack's identity labels or ground truth. Only the evaluation stage sees GT. Frames are hashed individually and bound in Protobuf descriptors to specific box, frame, sequence, and model digest. Those hashes are **integrity references, not independent authenticity attestations**.
* P2L defaults frozen prior to this real-image result: `appearance_weight=8.0, max_cosine_distance=0.85, momentum=0.6, near_tie_margin=0.75`; P2K default motion capacities unchanged. No post-hoc hyperparameter tuning.
* Official TrackEval pinned commit `12c8791b303e0a0b50f753af204249e622d0281a`, Git tree `ce583e59d96b33aad5f8f62149d96bc6bc4d8f96`, all 86 source files verified; `--DO_PREPROC True`, metrics HOTA/CLEAR/Identity; NumPy compatibility shim does not modify TrackEval sources.

## Aggregate metrics (0–100 except ID switches)

| Arm | HOTA | DetA | AssA | MOTA | IDF1 | ID switches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MPNTrackOriginal | 47.590 | 42.312 | 53.586 | 45.945 | 54.976 | 60 |
| CognitumP2KPosition | 41.365 | 41.471 | 41.342 | 45.536 | 45.563 | 186 |
| CognitumP2KVelocity | 41.996 | 41.691 | 42.373 | 45.600 | 46.203 | 186 |
| CognitumRealAppearancePosition | 44.122 | 42.257 | 46.137 | 45.794 | 48.726 | 96 |
| CognitumRealAppearanceVelocity | 44.173 | 42.302 | 46.194 | 45.786 | 48.952 | 99 |

## Sequence-level appearance + velocity, compared to velocity-only

| Sequence | velocity IDF1 | histogram+velocity IDF1 | delta | histogram+velocity HOTA | histogram+velocity switches |
| --- | ---: | ---: | ---: | ---: | ---: |
| MOT17-02-DPM | 45.790 | 44.200 | -1.590 | 40.854 | 25 |
| MOT17-05-DPM | 41.369 | 49.767 | +8.398 | 42.827 | 45 |
| MOT17-13-DPM | 49.903 | 55.294 | +5.391 | 49.456 | 29 |

## Reproducibility and test gates

* Original baseline and both P2K arms match all nine recorded published P2K metric fields per sequence and combined (12 rows) within 0.001 units.
* Official evaluator rerun on an independently copied score-free input tree: all 5 aggregate metric objects and all 5 summary-file SHA-256 hashes identical to first run.
* Source-geometry equivalence checked for every output tracker line (only column two changed); unchanged stage hashes validated before and after scoring.
* 1,258 selected C13/C14/C15 tests passed, 39 skipped, 567 additional subtests passed; all 67 independent Protobuf schema checks passed. This does not claim an unrestricted repository, cross-device, Windows-native, or deployed Lu validation.
* Batched PIL decoder retains *byte-identical Protobuf appearance descriptors* versus the original one-image-decode-per-box API on comparison fixtures.

## Scientific and security limitations

1. This is an identity-relabeling ablation on MPNTrack output, **not** an independent tracker or detector. Tracker boxes and identities originate in the same provided conventional tracking result.
2. Grayscale image histograms are a CPU reference, **not trained OSNet/Torchreid/FastReID**. Learned ReID remains deferred for pinned licensed weights and authorized worker.
3. 3 preselected sequences from MOT17 train are not a held-out benchmark of generalizable tracking. No published-accuracy or statistically significant improvement claim.
4. TrackEval's preprocessing can cause slight changes in detection-side metrics even when raw boxes are identical. We preserve exact source rows other than IDs and attribute that difference to evaluator semantics, not independent detection improvements.
5. All forced top-1 associations are **research-only, not authority**, even when official identity metrics increase. Lu, GitHub and host policy were not changed.
6. Timings are incidental on one CPU/Linux environment; the two appearance arms repeat feature extraction, so timing here is not a fair throughput comparison against a trained model or optimized tracker. No energy/VRAM measurements.

## Next experiments

Preserve `benchmark_backlog_v2.json`. Learned person-ReID and independent detector comparisons remain deferred, now pending pinned weights, security-approved execution, known preprocessing and fair evaluation. More MOT17 sequences can be added as a prespecified separate experiment rather than opportunistic cherry-picking.