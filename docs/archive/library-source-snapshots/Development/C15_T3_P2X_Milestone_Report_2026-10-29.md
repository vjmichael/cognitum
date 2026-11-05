# Cognitum C15 T3 P2X — incremental volumetric replay

**Status:** offline implementation and selected regression gate PASSED. **Real-world and host gate:** NOT PASSED / deferred.

## Changes

Starting from the saved P2W checkpoint, P2X adds a bounded session-local LRU over exact deterministic Protobuf inputs for P2T object-aware windows, P2S temporal windows and complete P2V results. The original P2U/P2V entrypoints remain independent full evaluators; protected evaluation callbacks allow P2X to reuse exact previously validated substage outputs without altering the P2W checkpoint or prediction semantics.

An HMAC (random per-process secret) detects cache and receipt tampering, and a chained receipt records request, P2V output, P2W checkpoint and prior receipt digests. The HMAC is a **process-local integrity defense, not persistent host authentication or sensor attestation**. Each `P2XSession` is limited to one conversation and volume. Previous checkpoint continuity, monotonic sequence and the complete caller-supplied source result are checked before merging.

## Tests

- **1,584 passed, 39 skipped, 638 passing subtests** in selected C07/C13/C14/C15 regression suite (Linux environment).
- **73/73** Protobuf schemas independently compiled and descriptor-verified.
- **15 focused P2X tests** including exact P2W byte parity, forged source-result rejection, HMAC corruption, cache eviction, policy invalidation, cross-session receipt refusal, scope and checkpoint-chain isolation, unknown-field rejection and prediction-only output.
- Independent full-replay parity was verified on all 20 synthetic profiled updates. Earlier R1 tracking baseline is unchanged.

## Local Linux CPU profile (synthetic verification workload)

Each of five measurement rounds consisted of four sequential updates using two, three, four and five overlapping object/volume windows. Source request and result construction was **excluded** from timings; the measured unit is P2W verification and state merge.

| Measure | Full P2W replay | P2X session cache |
|---|---:|---:|
| Median total for four updates | 169.887 ms | 44.646 ms |
| Median total for final three updates | 141.648 ms | 29.163 ms |

This is a 3.81× **verification-workload** speed ratio in this synthetic setup, not an end-to-end camera/depth performance claim. Exact parity was checked for every output in all rounds. Cache misses, evictions, restart and source-result computation still incur original work. Real scenes may behave differently.

## Preservation and deferred validation

- T3 P2W and preceding checkpoints preserved; tracking R1 remains performance baseline, R2 experiments unchanged.
- Original datasets, GitHub and Lu unchanged.
- Do not promote the research-only map into measured, physical or navigation authority.
- Deferred: host-anchored authenticated append-only capture journal; actual delta-level P2V evaluation; real 3D sensors; Windows resource p95/p99; independent occupancy engine.

See `P2X_START_HERE.md`, the source ZIP, `C15_T3_P2X_Local_Profile.json`, and `C15_T3_P2X_Benchmark_Backlog.json` for reproducible commands and experiments.