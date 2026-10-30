> **Research scope expanded (2026-10-28):** [Compositional/volumetric physical-world research plan](P0-expanded-compositional-physical-world-model-research.md). Current P0/P1 implementation remains unchanged; C15-P2A adds baseline adversarial tests only. Application ecosystems and direct Lu integration are out of scope.

# Cognitum C15 P0–P1 — spatial-object and scene-graph reference

**Milestone:** 2026-10-28. **Status:** P0 specification and bounded deterministic P1 reference implemented and tested locally on Linux. **Research only; no Lu integration, camera capture, learned perception, capsule network, or production authorization.** C14 G15 actual model benchmarks were explicitly **deferred / NOT RUN** by the owner; see `docs/decisions/2026-10-28-C14-G15-real-LLM-gate-deferred.md`.

## Selected task and incumbent

Maintain stable IDs and relative geometry for a small virtual 3D scene over explicit observations, renames and visibility changes. A practical Film Studio scenario: a repair drone appears, disappears behind a derelict spacecraft and reappears under the **same host-assigned stable identity**, rather than hallucinating a different object. Another task is determining whether one object is to the world-X left/right of another across camera coordinate frames.

- **Conventional incumbents:** A typed object registry / property graph (e.g. NetworkX `MultiDiGraph`) for edges, plus standard rigid-transform computation (SciPy `RigidTransform` or `Rotation`) and, for eventual real tracking, established multi-object tracking baselines. The implemented P1 uses **pure Python** for deterministic geometry with an independent SciPy parity test; no external library is required for runtime. References: [NetworkX MultiDiGraph](https://networkx.org/documentation/stable/reference/classes/multidigraph.html), [SciPy RigidTransform](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.RigidTransform.html), [MOTChallenge tracking evaluation](https://link.springer.com/article/10.1007/s11263-020-01393-0).
- **Research challenger (not implemented):** capsule/object-centric networks for learned pose and part-whole representations, benchmarked against conventional scene graph + trackers rather than equated to typed geometry records. Reference: Sabour, Frosst & Hinton, [Dynamic Routing between Capsules (2017)](https://arxiv.org/abs/1710.09829). Other potential challengers include dense embeddings and learned segmentation/tracking, all optional, permission-bound and independently benchmarked.
- **Negative case:** a model invents an object ID after occlusion, treats an alias as a different object, silently changes object category or observation source, combines metres with unmarked units, or treats user-provided visual labels as new instructions.

## Typed contract and invariants

`proto/cognitum/spatial/v1/scene.proto` introduces `SceneObject`, `CoordinateFrame`, `SceneMutation`, `SceneCommand`, `DerivedRelation`, `SceneSnapshot`, and `SceneReceipt`. Internal communication is Protobuf. JSON, if present later, remains at an explicitly named external boundary.

1. **Stable identity:** all IDs are explicit host supplied; labels and aliases are not identity. Re-observation maintains the same ID and increments an object version. Deletion is a tombstone and prevents unreviewed resurrection. An observed category or source cannot silently switch in P1. Cross-source identity transfer is deliberately deferred for a distinct P2 admission rule.
2. **Frames and units:** canonical `world` frame; all translation and position vectors are in **metres**, proper unit quaternions in `(x,y,z,w)`, fixed right-handed frames with child-to-parent transforms and a directed acyclic parent chain. Zero/invalid quaternions, cycles, unknown frame and nonfinite values reject. Relative relations are explicitly **world-X** (not subjective camera-left); `NEAR_3D` is a configurable reference convention fixed at ≤1 metre in P1, not a perception classifier. Frames are immutable once admitted.
3. **Visibility:** explicit `VISIBLE`, `OCCLUDED`, `OUT_OF_FRAME`, `DELETED`; occlusion preserves the last known pose but **derived visible-object relations are withheld**. Reappearance requires a newer host-admitted observation. No automatic matching based on appearance.
4. **Evidence and privacy:** source IDs are provenance labels, not cryptographic attestations. No camera/audio/screen I/O; geometries are opaque references and are not opened; no raw frames recorded. The in-memory snapshot is replayable as a data structure but is **not** a durable SQLite journal or certified erasure method.
5. **Scope, revision and authority:** command requires scene/conversation/task/trace/request IDs and expected snapshot revision plus per-object expected version. A supplied host-admission callback must return literal `True` for every action; missing/denied admission fails closed. **This callback is a test seam, not an authenticated Lu host.** Models cannot grant authority. Every transition is calculated on a copy, returning an unchanged prior snapshot on any rejection. Request IDs in the snapshot reject replay (bounded to 2,048; no journal compaction yet).
6. **Bounds:** ≤96 objects, 64 frames, 32 mutations/command, 16 new frames/command, ≤8,192 derived relations, ≤65,536 serialized command bytes. Resource exhaustion rejects without accepting partial transitions. These are arbitrary research bounds, not tuned limits.
7. **Receipt:** SHA-256 for command, prior state and resulting snapshot; deterministic Protobuf replay check. **A hash is not a signature**, and replay under a caller-supplied admission stub does not authenticate the worker or a Lu principal. Untrusted prior snapshots cannot be admitted from an LLM; they must come from host-controlled storage in a future implementation.

## Implementation and test artifacts

- `cognitum/spatial_scene_reference.py`: bounded pure-Python Protobuf scene transitions, independent `world_pose` API and relation derivation.
- `cognitum/proto/spatial_scene_pb2.py`: compiler-derived v1 schema binding; new descriptor registered in `tools/check_proto_descriptors.py`.
- `tests/test_c15_scene_reference.py`: admission, scopes, identity, occlusion, aliases, frame transforms, nonfinite payload, stale versions, replay, atomic failure, receipt tampering, hostile labels and independent SciPy geometry parity.
- `tools/run_c15_scene_smoke.py`: deterministic end-to-end synthetic scenario demonstration and evidence JSON.
- No outside inference provider, film editor, camera, Windows Lu bridge or model is invoked.

## Exit criteria, P2/P3 and kill rules

**P0–P1 acceptance:** every focused test and all existing C13/C14 regressions pass, complete Protobuf source-to-binding comparison passes, and a deterministic scenario demonstration returns stable IDs and correct frame-relative relations. Negative tests must fail closed. Additional metrics such as elapsed CPU time and RAM are not claimed until measured under a bounded bench.

**P2 stress tests (not yet implemented):** occlusion across long gaps, motion/frame timestamps and moving cameras, conflicting independent sensors, identity swaps, wrong-handed coordinate frames, misleading labels, revoked/deleted source references, snapshot tampering and persistence/rollback. Explicit consent for image/video capture must precede any data ingestion.

**P3 evaluation (not yet run):** temporal identity F1/IDF1, identity switches, relation consistency, frame transform error in metres/radians, false matches after occlusion, explanation provenance, runtime latency and VRAM. Use held-out sequences and compare standard scene graph+tracking to embedding-based and capsule/object-centric challengers under identical observations. Stop an experimental model if it cannot improve a specified metric over the conventional baseline at an acceptable cost or violates source/permission isolation.

**License and hardware:** pure-Python, CPU P1; SciPy/NetworkX for possible reference comparisons, each with their separately verified package/version/licensing in any eventual bundle. No required GPU/FPGA or extra weights; learned vision modules would be resource-intensive, and licensing/training data would require separate review.

**Release gates remain open:** authenticated Lu permission/caller identity, Windows-native confinement, durable task / state journal, feature-scoped user camera consent, actual model-augmented benchmarks, independent object-tracking ground-truth benchmarks, and integration with any Film Studio Workspace.
