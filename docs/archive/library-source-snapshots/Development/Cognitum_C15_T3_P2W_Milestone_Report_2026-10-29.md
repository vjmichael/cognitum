# Cognitum C15 T3 P2W — Volumetric Lifecycle and Resource Efficiency

**Date:** 2026-10-29. **Status:** offline engineering checkpoint PASSED; real-sensor validation DEFERRED. The preserved input is the Library P2V source checkpoint; Lu, GitHub, R1 and original datasets are unchanged.

## What is implemented

- Opt-in Protobuf-native bounded lifecycle and deterministic eviction for per-voxel and per-object research metadata, with explicit idle and capacity evictions.
- P2V source request is **fully replay-verified** before every public update; the newer checkpoint must bind to the same conversation and volume, have `sequence = prior.sequence + 1`, strictly later evaluation time, and newly advanced maximum capture timestamp.
- Tamper-evident serialized snapshot with previous hash, bounded state size, canonical ordered records and exact replay. **Hashes are not signatures**, host authority or proof that historical snapshots were valid. Durable anchoring and host authorization remain deferred.
- Only *current* verified retained P2V predicted voxels may be forwarded to the research-only stationary map. Historical cache entries do not silently remain eligible. T2 still classifies these as `INDETERMINATE` for structural claims.
- Resident cell policy: 1–4096; object policy: 1–128; idle TTL 1–10,000,000 ticks; input 15 MB and checkpoint 3 MB hard limits. Capacity exhaustion explicitly loses hypotheses rather than hiding eviction.

## Test evidence

- Selected C13/C14/C15 tests: **1,351 passed, 39 skipped**, plus **567 passing subtests**, 5 dependency/test warnings. The unrestricted all-repository suite was not run.
- C07 tests: **218 passed**, 71 subtests (earlier run following this source branch, unchanged C07 files).
- Focused P2W tests: **19 passed** (includes deterministic recovery, forged previous/next scope, replay, TTL/capacity eviction, unknown fields, mismatch of source P2V result, static-volume tampering, T2 indeterminacy).
- Protobuf compiler/bindings: **72/72 schemas** independently checked with Torch-vendored `protoc`.

## Local synthetic CPU profile (30 samples, x86-64 Linux Python 3.13)

| Operation | Median (ms) | p95 (ms) |
|---|---:|---:|
| Verified P2V replay | 32.1431 | 33.5511 |
| Private preverified P2W metadata merge (benchmark instrument only) | 0.4059 | 0.4973 |
| Public verified P2W update | 35.3611 | 40.2170 |

Benchmark input: 15 synthetic captures, 18 P2V cells and 1 tracked object. This is not a significant long-horizon workload, real-sensor measurement or representative Windows memory benchmark. `tracemalloc` excludes native allocations; it is not peak RSS. Full P2Q/P2S/P2V inference remains recomputed, so no verified end-to-end speedup is claimed. Results from profiling must not be treated as evidence of production real-time capability.

## Outstanding validation

- Real calibrated sensor depth, motion, map change and object labels are required for accuracy/recovery under real distribution shift.
- External OctoMap / OpenVDB parity, Windows native resource testing, durable host checkpoint anchoring and independent trust-source authorization have not been executed.
- True incremental upstream recomputation remains an explicit future research gate; never expose the private profiling helper as a public or host execution endpoint.
- R1 remains the frozen T1 performance baseline; P2V and earlier T3 contracts are unchanged except the optional schema registry addition.