# C15 T3 P2X — incremental volumetric replay

## Architecture

P2X is a **session-local reuse layer** for the P2W verification workload, rather than a new estimator. It introduces bounded LRU exact-Protobuf-request memoization at P2T and P2S, and for complete P2V results. All cache values are generated internally from previous requests within the same scope. They carry per-entry HMAC integrity tags; an unmodified request SHA-256 digest must match for reuse. An integrity mismatch immediately rejects and clears the cache.

P2V still performs full P2U cross-window aggregation, per-cell camera and object checks, and stationary-map filtering on cache misses. P2W still recomputes its bounded latest-state merge on every update. Caller supplied P2V result is compared byte-for-byte to the internally evaluated/cached expected output before any P2W merge. A `validate_parity=True` QA option performs an independent full P2W replay and compares exact output bytes.

Sequence continuity is enforced with the previous P2W checkpoint hash, increasing request sequence number, and one conversation/volume scope per session. The HMAC receipt binds full input request, P2V result, P2W checkpoint, sequence, scope and prior receipt. The key exists only in memory. This makes local receipts detectable against accidental corruption or a caller who does not possess the key; it does **not** prove that the sensor or host was authentic and cannot be used to certify a checkpoint after restart.

## Scientific and security limitations

* SHA-256 hashes of caller-provided frame and 3D object observations do not attest sensor truth or object identity.
* An in-process cache is not a durable authenticated observation journal, and does not survive process death.
* No re-use on changed P2T/P2S request content; policies and capture changes cause cache misses.
* Current public API still includes the complete P2V request/result. It is not append-only delta validation of new observations.
* Synthetic Linux CPU timings are **verification workload only**. They exclude upstream source-result generation and real-sensor inference costs. Windows real-time p95/p99 and memory must be separately tested.
* All T2 stationary-map outputs remain `predicted` and the existing static safety gate remains intact.

## Commands

```
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2x_incremental_volume.py
PYTHONPATH=. python -m pytest -q tests/test_c07* tests/test_c13* tests/test_c14* tests/test_c15*
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2x_profile.py --rounds 5 --out /tmp/p2x-profile.json
```
