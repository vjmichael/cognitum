# C15 T1 P2E — First real annotated sequence evaluation

## Outcome

A public real-world multi-object tracking *annotation and reference-prediction* fixture was fetched through the GitHub connector and evaluated in an isolated JavaScript diagnostic. **This was not an official DeepSORT/ByteTrack comparison.** The source is `cheind/py-motmetrics` (`motmetrics/data/TUD-Campus`), branch `develop`.

| Data | Git blob SHA-1 | Entries |
|---|---|---:|
| `gt.txt` | `182d09a1683b0e87349b00661d9cdcc1ffaf39df` | 359 |
| `test.txt` | `64b0fe10e177ea92dd9bbe0e9385d721edb33982` | 222 |

The 71 frames contain eight distinct annotated identities. The local calculation compared the independently supplied `test.txt` predictions with the ground truth using IoU >= 0.5 and a maximal-cardinality, then maximal-IoU per-frame assignment. It observed 209 matched boxes, 150 false negatives, 13 false positives, and **eight diagnostic ID changes**. The **approximate** MOTA and IDF1 computed by this diagnostic were 0.523677 and 0.516351, respectively; do NOT publish these as official tracking metrics.

The py-motmetrics project reports approximately 58.2% recall and 94.1% precision for its TUD-Campus comparison, consistent with the 209/359 and 209/222 counts. It reports seven official-style ID switches, demonstrating that our simplified identity accounting is not equivalent to an official evaluation. Its published IDF1 is also computed differently from our diagnostic.

The independent evaluator additionally tried IoU and constant-velocity assignment using ground-truth boxes **as oracle detections with object IDs removed**. Both produced perfect assignments on this small sequence. This is an *easy association sanity check* with information leakage from perfect detection boxes, NOT a real tracker-vs-detector benchmark and NOT meaningful evidence of superiority. Those results are deliberately excluded from release benchmark acceptance criteria.

## Reproducing with actual external data

The source bytes are **not included** in this archive. Obtain `gt.txt` and `test.txt` from the pinned public GitHub repository, subject to the original dataset conditions, then run:

```bash
python tools/c15_real_annotation_pilot.py --gt /path/to/gt.txt --pred /path/to/test.txt --out /tmp/tud_campus_diagnostic.json
```

The script uses the inherited Cognitum MOT parser and evaluator and validates each Git blob SHA-1 before calculating diagnostics. It may differ from the JavaScript diagnostic in marginal assignments or identity switches; this difference must be recorded, not hidden.

## Unfinished requirements

- Genuine SportsMOT or MOT17 full dataset: frames, official ground truth and detection files
- Genuine DeepSORT pretrained MARS appearance features or weights and image-derived embeddings
- Original ByteTrack execution with the same public detection inputs
- Official `TrackEval`/`motmetrics` scores, HOTA/IDF1/IDs, versioned configs
- Genuine multi-frame Cognitum T1 P2C 3D tracking evaluation (its current proposal engine is limited to six detections/tracks)
- Real-world tracking benchmark and native Windows/Lu security integration

Source: https://github.com/cheind/py-motmetrics/tree/develop/motmetrics/data/TUD-Campus
