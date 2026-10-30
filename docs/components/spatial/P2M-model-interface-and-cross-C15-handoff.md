# Cognitum C15 P2M — Model interface and cross-technology evidence handoff

**Checkpoint:** 2026-10-28 (local project milestone), P2M offline P1 implementation plus P2 smoke checks. **Not** a new real MOT17 appearance benchmark, installed learned model, production host integration, validated 3D camera calibration, or Lu-side implementation.

## Purpose and boundaries

P2K found a loss against original MPNTrack IDs on 3 real annotated sequences even with matched boxes. P2L showed some synthetic improvement from handcrafted appearance features. P2M is the bounded handoff for model inputs and future independently supplied model weights; it does not implicitly load external Torch/Pickle checkpoint files or permit model-requested tool execution.

- `proto/cognitum/spatial/v1/appearance_pipeline.proto` is the new internal Protobuf wire contract: model spec (backend/version/128D/preprocessing/encoder digest/weight digest), ordered image+box inputs, response frame/descriptor digests, T1 2D track candidates, and T2/T3 handoff flags. No JSON is used for native execution transport; JSON in the backlog and report is documentation evidence only.
- `cognitum/spatial_p2m_pipeline.py` supports `inspect_model`, `extract`, `check_response`, `research_pipeline`, `integration_handoff`, `load_named_frames`, `build_request_from_frames`. Bytes and pixels are bounded (4 frames/batch, 16 boxes/frame, 8 MiB per compressed image, 20 MiB total, 8 million pixels each). Input frames have explicit source identifiers and their exact raw bytes are hashed but not copied into the feature response.
- Only `P2M_HISTOGRAM_CPU` executes. `P2M_EXTERNAL_LEARNED_DISABLED` models can be declared and have local weights SHA-256 checked without deserialization or arbitrary code execution, but **always remain blocked** until an independently approved, bounded host worker implements safe load/inference. Digest checking is not publisher authentication or sandboxing. Do not trust pickle-based model files by default.
- Protobuf descriptor validation, unknown-field rejection, identity-blind detection geometry, per-box/frame checks, fixed model preprocessing, no surprise downloads, no default-on activation. Existing P2L schema and six-by-six canonical identity engine unchanged; existing P2L callers stay backward compatible, with optional explicit conversation scope for P2M.

## C15 internal integration (no unsafe 2D→3D upgrade)

| Component | P2M integration | Restrictions |
|---|---|---|
| T1 identity persistence | `research_pipeline` runs P2L association and emits 2D track-candidate IDs with descriptor hash and exact original box/frame identity | Forced research top-choice, not person identity or scene admission; no calibrated uncertainty proof |
| T2 composition/structure | Builds a real `cognitum.spatial.v1.StructureGraph` with **hypothetical** image-track nodes, consumable by existing `spatial_composition.validate/query` | No *part-of* edges inferred; normal queries suppress unadmitted hypotheses |
| T3 sparse occupancy/volumes | `t3_projection_blocked_without_calibration=true` | A 2D box/descriptor has no depth, intrinsics, extrinsics, or 3D pose; **zero rays and zero voxels** may be emitted from this bridge |
| Canonical scene graph | `canonical_scene_mutation_blocked=true` | Requires separate Lu host authority and verified sensor/world coordinates; no direct mutations |

Handoff validity is checked against the exact request, rederived feature bytes, conversation, frame and bounding boxes. Rejected cases do not return partial authenticated results. Requests must not include ground-truth identities. The 2D tracker IDs in output are hypotheses only.

## Real model readiness (blocked intentionally)

Mature comparison candidates: Torchreid `FeatureExtractor`/OSNet, original source https://github.com/KaiyangZhou/deep-person-reid; BoxMOT ReID https://github.com/mikel-brostrom/boxmot. Those APIs often produce dimensions other than 128 (for example, 512); a future **explicit, independently tested versioned projection or dimension-aware schema** is required before passing them into the existing 128D contract. Neither an implicit truncate nor a fake renormalization is acceptable. Source and trained weights are not bundled; licenses must be reviewed individually, and test/build must not download weights automatically.

## Benchmark preservation

`C15-benchmark-backlog-v1.json` records known measured P2I/P2K results, negative findings, a synthetic-only P2L checkpoint, and the six deferred external/real-data/host gates with input requirements, matched arms, metrics, acceptance criteria and resume conditions. None is marked passed by P2M.

## Reproduce

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_p2m_pipeline.py tests/test_c15_p2l_appearance.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_p2m_interface_smoke.py --output /tmp/c15_p2m_smoke.json
```

The `C15` selected suite is useful for regression, not an unrestricted whole-repository or Windows-native certification. A future audited Lu CE worker must separately validate permissions, policy, sandbox and real sensor provenance.
