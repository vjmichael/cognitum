# C15 T3 P2W — bounded volumetric lifecycle (offline research)

**Decision:** P2V remains the complete scene-robustness evaluator. P2W is an optional, read-only incremental **metadata and cache-state merge** over a *fully replay-verified P2V snapshot*. Nothing in P2W is a production navigation map, an authenticated observation, or a Lu worker.

## Contract and entrypoints

- `proto/cognitum/spatial/v1/map_lifecycle.proto`
- `cognitum/proto/spatial_map_lifecycle_pb2.py` — generated from independently compiled descriptors.
- `cognitum/spatial_map_lifecycle.py`: public `advance(request)` and `verify(request,result)`, `checkpoint_digest(state)`.
- `tests/test_c15_t3_p2w_map_lifecycle.py`: boundedness, replay, scope, wire, tampering, T2 integration.
- `tools/run_c15_t3_p2w_profile.py`: local synthetic timing of full P2V verification, the **private preverified merge**, and public complete request. Private merge MUST NOT be offered to external or host callers without independent verification.

## State transitions and failure behavior

1. Reject unknown fields, non-research requests, authority flags, oversized inputs, invalid resource quotas.
2. Re-evaluate the exact supplied P2V request, require deterministic byte-equality with the supplied P2V result. **This is NOT incremental P2V recomputation.**
3. Validate previous checkpoint scope, schema, deterministic checksum, sorting/uniqueness, budget, predicted-only evidence. Check previous `sequence + 1`, strict `evaluation_tick` increase and new maximum capture tick.
4. Merge current P2V voxel and object records with bounded prior memory; keep historical cells but mark them **not eligible** if the latest P2V result does not independently retain them. Never carry forward stationary-map authority.
5. Evict idle cells/objects; deterministically cap resident cells and objects. Report both TTL and capacity evictions explicitly. Quota exhaustion can reduce recall; this is not a zero-loss map cache.
6. Rebuild the **current** predicted-only volume only from eligible surviving P2V evidence, and independently validate it with the existing classifier (result must remain `CELL_UNKNOWN`).
7. Compute a deterministic SHA-256 hash chain (`prior_checkpoint_sha256`, `checkpoint_sha256`). Replaying the same update gives byte-identical output.

## Security and continuity limitations

- A SHA-256 of protobuf bytes detects accidental or unsophisticated mutation. It does **not authenticate** a caller, a depth camera, original evidence, or a prior checkpoint; a hostile caller can recompute it. A production host must anchor the latest digest in a separately trusted durable journal and authenticate the conversation and publisher before accepting a checkpoint.
- A later update must include new capture timestamps, but that is only a freshness assertion from the caller, not proof of real sensor capture.
- Memory budgets are `1..4096` cells and `1..128` objects; source request capped at 15 MB; checkpoint cap 3 MB. These values are *research contracts*, not resource reservations in a Windows host.
- Only P2W state metadata is incrementally merged; the full P2Q→P2V path still recomputes and verifies its complete bounded source window. Test platform is a Linux container and no real sensor, Windows host, OctoMap or OpenVDB was executed here.
- The private `_merge_preverified` routine is **benchmark instrumentation**, not an alternative public API. Public `advance` always verifies P2V.
- The object identity remains a caller assertion; no navigation or measured structural facts are generated. Static forecasts are not collision-clearance decisions.

## Follow-up

Investigate structural sharing / incremental validation of P2Q/P2S/P2V from a trusted authenticated host journal, compare against a pinned volumetric engine under matched voxel resolutions and depth streams, test eviction policy under adversarial density, run long-horizon crash/restart and Windows memory profiling. All are deferred; see the companion backlog.
