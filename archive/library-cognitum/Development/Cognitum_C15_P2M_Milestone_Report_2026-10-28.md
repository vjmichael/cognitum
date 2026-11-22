# Cognitum C15 P2M — Model Interface, T1/T2/T3 Handoff and Preserved Benchmark Backlog

**Date:** 2026-10-28. **Result:** Bounded offline research implementation delivered. Selected smoke and regression verification passed. Real learned-ReID, frame-backed appearance efficacy, 3D scene/volume conversion, and Lu secure-worker integration remain open.

## Implemented

- New **native Protobuf** `appearance_pipeline.proto` with pinned reference encoder contract, strict request/response, source-frame SHA-256 and versioned 2D identity/structural candidate handoff. Protobuf, not JSON, is the native execution interface.
- Real image decoding and CPU 128-D handcrafted histogram extraction with conversation/frame/box/encoder binding, fixed non-executable reference model; bounded four-frame batches, 16 boxes per frame, 20 MiB total image payload, 8M pixels per source image.
- External learned encoder manifest is **non-executable**. Its local weight bytes can be hashed and compared with a declared SHA-256, but neither digest integrity nor a file path means publisher authentication, independent sensor provenance, confinement or permission. No Torch checkpoint is deserialized. Future actual learned model loading must use separately approved host-managed workers and explicit dimension conversion.
- `research_pipeline` runs the bounded P2L 2D association from those actual images. It packages T1 **candidate-only** identity assignments, validates a T2 `StructureGraph` with **hypothetical** nodes (no inferred object parts), and **blocks** T3 3D occupancy/volumes and T1 authoritative scene mutation for absent calibration / host approval. All outputs research-only, authority false.
- Added deterministic fixture-based end-to-end smoke runner, adversarial tests, explicit traceable benchmark backlog with six deferred scientific tasks. P2I/P2K negative and baseline findings retained.

## Verification (Linux Python 3.13)

| Verification | Result |
|---|---|
| P2M + neighboring P2L focused tests | 29 passed, 9 subtests passed |
| Selected C13/C14/C15 regression | **1,139 passed, 39 skipped, 562 additional subtests passed** |
| Independent Protobuf compiler ↔ generated bindings | **62/62 matched** |
| Self-contained image-backed P2M smoke | Passed, 3 descriptors and 3 candidate observations, one T2 hypothetical track, zero T2 edges, T3 blocked |
| Real MOT17 appearance HOTA/IDF1 | **Not run; training JPEGs unavailable** |
| Learned OSNet/Torchreid/BoxMOT actual weight inference | **Blocked; no approved worker or verified weights** |
| Full unrestricted suite / Windows-native / Lu authorization | **Not evaluated** |

The tests use generated sample images. They establish no independently measured accuracy improvement or transfer of camera-derived person identity. SHA-256 checks bind bytes but are not signatures or sensor authentication.

## Deferred experiment ledger

See `docs/components/spatial/C15-benchmark-backlog-v1.json` (v1) for status, dependencies, matched arms, metrics, acceptance and resumption criteria. It includes MOT17-train image appearance evaluation, learned person ReID, independent detections/full tracking, OWL 2 reasoner parity, OctoMap/OpenVDB 3D parity and real Lu+LLM/hardware evaluations. None is silently marked passed.

## Next C15 technology activity

Proceed with T2 structural reasoning and T3 volumetric/occupancy integration **only as separate typed, physically grounded inputs**; the P2M 2D appearance handoff must not fabricate depth or parts. Research candidates include OWL 2 reference reasoners and mature voxel engines where their licenses/dependencies are obtainable. Future integration must retain the primary canonical scene authority and explicit host admission.

## Repro

```bash
PYTHONPATH=. python tools/run_c15_p2m_interface_smoke.py --output /tmp/p2m-smoke.json
PYTHONPATH=. python -m pytest -q tests/test_c15_p2m_pipeline.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python -m pytest -q tests/test_c15* tests/test_c13* tests/test_c14*
```

Compared reference archive: `Cognitum_C15_T1_P2L_Appearance_Research_2026-10-28.zip` recovered from user Library. Original P2L and earlier benchmark evidence preserved; original Lu repo, GitHub, and dataset archives untouched.