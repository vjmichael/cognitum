# Cognitum C15 T3 P2S — Temporal Volumetric Consistency

**Status:** Offline research implementation passed selected tests. This checkpoint builds on frozen P2R; it is not a production or real-sensor benchmark pass.

## Deliverables

- `proto/cognitum/spatial/v1/temporal_consistency.proto`: additive Protobuf v1 contract; two to twelve independently captured ordered frames, correlation-adjusted P2R input, explicit policy and no authority.
- `cognitum/proto/spatial_temporal_consistency_pb2.py`: compiled descriptor used by Cognitum's independent compiler verifier.
- `cognitum/spatial_temporal_consistency.py`: deterministic, bounded cross-capture timeline with contradiction, decay, change-point support, stale gating and predicted-only T2 output.
- `tests/test_c15_t3_p2s_temporal_consistency.py`: 21 focused adversarial/reference tests, including per-capture independent oracles, mixed capture contradictions, tampering, replay, deadline, history and T2 structural audits.
- `tools/run_c15_t3_p2s_demo.py`: synthetic repeatable timeline.
- Separate deferred validation backlog, documentation, and preserved source manifest.

## Key observation from **synthetic** timeline

| Scenario | Baseline P(occupied) | Adjusted P(occupied) | Outcome | Forwarded to T2? |
|---|---:|---:|---|---|
| same_occupied_capture_sequence | 0.9406 | 0.9406 | P2S_PREDICTED_OCCUPIED | Predicted-only |
| new_opposition_pending | 0.8695 | 0.8695 | P2S_CONTESTED | No |
| two_free_confirmed_not_forwarded | 0.7381 | 0.1747 | P2S_RECOVERED_FREE | No |
| three_free_recovered_hypothesis | 0.5453 | 0.0840 | P2S_RECOVERED_FREE | Predicted-only |
| recovered_occupied | 0.9225 | 0.9828 | P2S_RECOVERED_OCCUPIED | Predicted-only |

Values are deterministic outputs from *invented example sensor readings*, not observed camera performance, sensor calibration or real probabilities. P2R rho is caller-selected; P2S treats each P2R output as one frame event while acknowledging that different frames may remain correlated.

## Verification

- `PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2s_temporal_consistency.py`: **21 passed**.
- `PYTHONPATH=. python -m pytest -q tests/test_c13* tests/test_c14* tests/test_c15*`: **1,275 passed, 39 skipped, 567 subtests passed** (selected suite, not full repository).
- `PYTHONPATH=. python -m pytest -q tests/test_c07*`: **218 passed, 71 subtests passed**.
- `PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`: **68 / 68**.
- Clean extraction and manifest verification performed on final package separately.

## Design safeguards

Unknown Protobuf fields rejected; digest-bound replay; strict frame chronology; conversation, volume, grid and size enforcement; capacity bounds; explicit provenance. One contrary frame is contested. Confirmed streaks preserve prior evidence; recovered evidence needs an extra capture before hypothetical T2 handoff; stale or mixed evidence never leads to a physical claim. All T2 evidence is `VOLUME_PREDICTED_*`; its canonical classification remains `CELL_UNKNOWN`.

## Unresolved

No real depth sensor sequences were evaluated, camera and timestamps are caller-asserted, no proof of independent time frames, no learned motion segmentation or change-point validity. OctoMap/OpenVDB and held-out dynamic occupancy benchmarks are deferred. No Windows Lu host permission integration or real physical calibration was exercised. `P2S` **must not** be used for collision avoidance, navigation, or safety-critical decision-making.

## Repository integrity

Only additive P2S files and the schema registry are changed relative to archived P2R. Old P2R, T2, and R1/R2 performance code are untouched. No Lu or GitHub changes.