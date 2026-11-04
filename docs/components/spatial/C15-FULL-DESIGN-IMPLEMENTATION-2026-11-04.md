# C15 — Full practical design completion and acceptance matrix

**Updated:** 2026-11-04
**Current branch:** `c15-spatial-practical-20261104` / PR #71.
**Engineering status:** All four design phases have a practical implementation or bounded validation interface. **Native CI and independent real-data acceptance are not verified; no merge/production claim.**

## Design contract and evidence

The controlling design is `docs/design/technology-portfolio-C01-C19.md`, C15 P0–P3.
Its question is whether stable object identity, geometry, relations, time,
occlusion, edits, scene changes, renaming and multimodal observations can be
preserved without unwarranted evidence/identity assumptions.

### P0 — Typed persistent world/scene representation

- `spatial_geometry.py`: stable object ID, version, evidence source, timestamp,
  metres, full world SE(3) quaternion pose via SciPy Rotation, geometry
  reference, declared confidence and explicit parent-coordinate frames.
- `spatial_scene_graph.py`: version-scoped typed relation edges with original
  stable IDs, relation frame `world`, metric value, evidence sources and
  automatic stale-edge refusal after edits, tombstones or epoch changes.
- `spatial_lifecycle.py`: compare-and-swap scene revisions, creation, updates,
  rename/aliases, explicit occlusion/reveal/deletion tombstones and append-only
  observation evidence records. Duplicate names, conflicting aliases,
  invalid source digest/time and stale mutations are refused.
- `spatial_scene_journal.py`: stdlib SQLite atomic WAL/FULL commits, immutable
  versioned scene snapshots, per-workspace custody namespace, per-scene
  SHA-256 hash chain, strict canonical JSON decode, restart recovery and
  rollback/CAS checks. Durable event adjacency, tombstones, alias history,
  old evidence preservation and irreversible workspace detachment validated.
  Hashes alone are not signed tamper-resistant storage or hardware rollback
  protection.
- `spatial_core_wire.py`, `spatial_core_pb2.py`,
  `proto/cognitum/spatial_core/v1/spatial_core.proto`: strict typed canonical
  Protobuf scene queries and tracking requests with independently recomputed
  responses, complete world pose and source metadata. The in-memory lifecycle
  and SQLite journal remain *host-owned modules*, not model-callable file APIs.

### P1 — Conventional geometry, tracking and optional appearance

- SciPy `Rotation` for metric frame transforms, SciPy
  `linear_sum_assignment` for gated track↔observation identity association.
  Box overlap/distance, per-track missed-frame counts, preserved stable IDs
  for bounded occlusion, explicit unmatched detections and ID retirement.
  No silent creation of an object from an unapproved raw detection.
- `spatial_appearance_core.py`: opt-in versioned descriptor matching with
  SciPy cosine distance, original encoder digest and source/frame lineage,
  explicit compatible vector-space rules, rejection of ambiguous near-ties,
  not a claimed learned re-identification network.
- `spatial_cv_features.py`: opt-in Pillow bounded decode of **explicit
  host-supplied PNG/JPEG bytes** and an OpenCV normalized HSV histogram
  descriptor with exact source-frame SHA-256. No camera opening, automatic
  file discovery, model download, detector weights or host tool grants.
- Capsule models are an **optional learned challenger**, per the controlling
  design, not a mandatory production dependency. The benchmark recognizes
  caller-supplied challenger descriptors without executing arbitrary networks
  or declaring any histogram a capsule model.

### P2 — Adversarial identity, source and temporal behavior

- `spatial_observation_consistency.py`: time-aligned conflicting camera
  positions compared after explicit world-frame conversion, with bounded
  isotropic sigma and conservative source correlation uncertainty. Returns
  `CONFLICT` rather than blending incompatible reports or assigning source
  credibility; no source authentication claim.
- `spatial_identity_eval.py`: ground-truth is passed exclusively to an
  evaluator; it is NOT passed into geometry, appearance or optional challenger
  matchers. Reports correct/false/missed identity pairs and latency.
- Native regressions test cyclic/invalid frames, quaternion composition,
  stale or forged Protobuf replies, aliases/identity swaps, occlusion,
  deletion, workspace detachment, concurrent edit conflict, duplicate
  evidence, source mismatch, descriptor near-ties, image byte bounds,
  SQLite restart, tampered hash chains and false metric claims.
- **Trust boundary:** A Boolean test seam or caller-provided source identifier
  is not Lu authorization. A real host must authorize the source bytes,
  filesystem path, permissions and OS-isolated worker before use. Host paths,
  provenance, pose correctness and user intent are not automatically
  authenticated by these modules.

### P3 — Reproducible matched comparison and external evaluator

- `tools/c15_spatial_benchmark.py`: deterministic real SciPy boxes,
  identity preservation, occlusion and unmatched detection smoke.
- `tools/c15_full_design_benchmark.py`: frozen matched identity fixtures
  exercising geometry-only, appearance and supplied challenger vectors; true
  labels used only AFTER solver output, not as tracker inputs; records matches,
  misses, false matches and real measured wall time.
- **Selected existing technology from historical PR #19:** the self-contained
  `cognitum/spatial_mot_adapter.py` includes MOTChallenge-format data
  parser and transparent diagnostic ID switch/global identity overlap
  counts, with explicit `not_official_motchallenge_metrics`. This is a
  selective source-reconciliation commit, not a bulk merge.
- `spatial_official_trackeval.py`: opt-in host-controlled TrackEval CLI
  adapter requiring separate original GT and tracker prediction files,
  pinned source/runner content hashes, fixed benchmark configuration,
  no shell execution or automatic downloads, stale summary refusal, and
  source-unattested result status. **This is not evidence that a real official
  MOT17/TAO/BDD100K dataset or official evaluator ran.** Requires licensed
  external dataset, known detector/weights, authorized source, exact TrackEval
  checkout, OS-isolated process and held-out sequence evaluation.
- No empirical GPU VRAM or energy number is invented. CPU timers record only
  measured component runs. Model-level Lu/Cognitum A/B requires C03, a
  separately controlled test and user authorization.

## Existing historical C15 work

PR #19 (`c15/source-checkpoint-2026-10-29`) contains hundreds of historical
T3/T4 scene, depth, volume, benchmark and provenance experiments, and is
**not merged**. Its dedicated portable C15 CI passed at its final head but the
full Python regression failed on the same head. Preserve that source/evidence
history; do **not** import all 611 changed files or overwrite newer `main`.
Source variants are historical comparisons, not automatically production
requirements or validated real sensor observations. The selected standalone
MOT diagnostic above was imported with its original implementation and given
new focused tests.

## Remaining acceptance, not new research scope

1. Exact PR #71 head must pass Windows/Linux native NumPy/SciPy, OpenCV/Pillow,
   Protobuf descriptor parity, revised lifecycle/journal, appearance, source
   scope, MOT diagnostics, and negative tests; main Python regressions must
   pass. **CI queued is not a pass.**
2. For real-world multi-object tracking claims, test a permitted held-out
   MOTChallenge/TAO/BDD100K or actual film sequence through the real official
   evaluator with baseline comparisons, source provenance and GPU memory/
   latency measurement. No source files/weights have been authenticated here.
3. Lu/C02/C04 must supply OS-isolated worker termination, host source
   permissions, durable authorization receipts and user opt-in before
   model-visible perception, journal mutation, or benchmark subprocess.
4. C03 must verify actual Lu task-success benefit and false-confidence rate
   over the standard-library baseline.

**Completion definition:** The practical C15 design is implemented as
a bounded component and external acceptance adapters; it is **not verified
or production closed** until those acceptance gates have real evidence.
Do not start an open-ended capsule-network research campaign merely to
produce a misleading checkmark.
