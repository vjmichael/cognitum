# Cognitum C15 — T1 P2D data gate, T2 structural graph and T3 volumetric reference

**Status:** T2 and T3 local offline reference implementations TESTED. P2D actual MOT17 / true image-derived appearance / original DeepSORT–ByteTrack benchmark is **NOT COMPLETED**. Research-only, no trusted perception, identity promotion, real-world navigation, physics, medical/construction decisions, Lu authority, or Windows certification.

## T1 P2D: source survey and honest empirical status

The original open-source references were inspected:
- MOT17 and SportsMOT annotated sequences: https://trackers.roboflow.com/latest/learn/download/ (MOT17 CC BY-NC-SA 3.0; SportsMOT CC BY 4.0; check terms separately). Annotated *train/val* are available. Test split lacks public GT. Preferred MOT17 train or validation sequence; do NOT use test labels fabricated from detections.
- Original DeepSORT: https://github.com/nwojke/deep_sort commit `f08cf1dc470eeb1cd2add1cbf077d95ac6c48aab`, GPL-3.0. Official 128-D MARS descriptor weights/precomputed embeddings are distributed via a Google Drive link in its README, not bundled here. Requires actual image frames and aligned detections.
- Original ByteTrack: https://github.com/FoundationVision/ByteTrack commit `d1bf0191adff59bc8fcfeaa0b33d3d1642552a99`, MIT. Requires original tracker implementation and fixed detector outputs.
- The `cheind/py-motmetrics` open repo also contains compact published real-world TUD-Campus and TUD-Stadtmitte ground truth files, and accompanying `test.txt` tracking results: https://github.com/cheind/py-motmetrics/tree/develop/motmetrics/data. Their published trajectory annotations were inspected remotely via connected GitHub; they are not downloaded into the offline workspace.

Container network download of official MOT17 ZIP failed; no real image frames, annotated local sequence archive, pretrained MARS weights, or runnable original tracker software is present. Hence: **no honest numerical MOT17 DeepSORT/ByteTrack/Cognitum ranking**, no HOTA, official MOTA, IDF1, real-world IDSW or frame-derived learned-feature trust claims. Synthetic or copied GT boxes used as detections would leak the oracle and invalidate the comparison. Do not do that.

### Reproduce the full dataset gate on a networked research host

1. Obtain MOT17 *train/val frames, GT, and public detections* under the dataset's terms, e.g. via `trackers download mot17 --split val --asset frames,annotations,detections` (check the installed CLI's exact flag spelling). Record archive checksum, sequence ID, split, frame count, and public detector choice. An alternate original archive is https://motchallenge.net/data/MOT17.zip.
2. Obtain the **original DeepSORT** source at the pinned SHA and its real MARS-128 weights, or precomputed MARS features with an independently checked mapping to frame/detection. Obtain **original ByteTrack** source at the pinned SHA. Isolate environments, record package locks and model checkpoints, comply with GPL-3.0/MIT obligations.
3. Run both trackers on the **same public detections and frames** with frozen thresholds and no GT labels exposed to the trackers. Record original tracker output `frame,track_id,x,y,w,h,score,...` files.
4. Run `PYTHONPATH=. python tools/c15_tracking_preflight.py --gt <gt.txt> --det <det.txt> --deep-sort <results_deepsort.txt> --byte-track <results_bytetrack.txt>`. The built-in diagnostic computes explicit IoU-matching and global identity pairing, **not official MOTChallenge scores**. For official HOTA/IDF1/MOTA use the independent TrackEval evaluator, ensuring proper ignored-object filtering and protocol.
5. Compare with Cognitum only after adding an **image-plane candidate adapter** that uses the *same* detections and properly timestamped, calibrated frame assumptions (P2C currently assumes 3D positions in metres and <=8D caller-supplied descriptors). Never pretend direct substitution of 2D pixels for world metres or an arbitrary 8D compression of MARS-128 is the same algorithm.

The new Protobuf `appearance.proto` checks 128-D normalized descriptor **format and source hashes**, but outputs `independently_authenticated=false`. A digest proves integrity only relative to a supplied value, NOT sensor authenticity, source trust, accurate person re-ID, or model calibration. Proper host attestation and controlled held-out feature accuracy testing are still needed.

## T2: typed part/whole reasoning

`composition.proto`, `spatial_composition.py`. A bounded typed graph contains nodes and directed part–whole / contains relationships, plus symmetric connections. Acyclic part/whole graph, single-parent structural constraint, source identifiers, research-only flag, scope check and resource caps; no inferred or hypothetical node promoted to observed. Queries return ancestors, descendants and links. HYPOTHETICAL descendants remain excluded by default; the exact contents of an unseen person/building are not fabricated. Scope is intentionally simple, not an authenticated Lu host token. It is **not** a complete ontology, semantic geometry model, or multi-parent assembly graph.

## T3: sparse occupancy evidence

`volume.proto`, `spatial_volume.py`. Bounded grid stores occupied/free/unknown/conflicted separately. Only explicitly *measured* claims establish occupied/free; hypotheses stay UNKNOWN; unobserved cells remain UNKNOWN. Contradictory independent source claims become CONFLICTED. Repeated evidence from one source uses only its latest observation to avoid naïve duplicate voting. Log-odds are descriptive, not calibrated posterior or a proof of physical material. Does not create voxels from camera images or perform raycasting, TSDF fusion, meshing, CAD, or physics simulation.

## Scientific findings and next research gates

- A surface recognition label is not a 3D measurement of interior structure. Part–whole priors should remain labeled inferred/hypothetical until independent evidence.
- A negative observation should not be confused with *unknown*; a cavity requires observed free space, not simply absence of occupied observations.
- Structural graph and volumetric evidence must keep independent uncertainty and provenance; they can eventually cross-reference one another without manufacturing facts.
- Next: T2 hierarchical ontology/part graph benchmarks, multiple-parent systems and functional constraints; T3 ray-based occupancy, sensor calibration, multi-resolution sparse voxel structures, uncertainty coverage and visual-world-model interfaces.
- True learned CAPS and physically grounded sim-to-real research remain open. No Lu code or Github source modified.
