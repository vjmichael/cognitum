# C15 T3 P2Y — durable incremental journal / restart recovery

## Goal and boundary

P2Y is an **opt-in experimental persistent wrapper** around P2X/P2W. It does not certify cameras, object identities, scene geometry, the operating system, or any Lu host. It does not change P2S–P2X public evaluator outputs. It retains verified observation **requests and results**, not an untrusted serialized cache. Reusable P2X cache entries are rebuilt only after successful independent full replay.

A P2W checksum is an integrity checksum, not an authentication tag. P2Y requires a key and **current latest anchor external to its journal**, supplied by a host authority with two operations:

* `read() -> P2YHostAnchor`: read current committed anchor / revocation state; must be authenticated by the actual host.
* `compare_and_swap(expected, updated) -> bool`: atomically and durably persist a new anchor if and only if expected is still current, with a host authorization and revocation check. This is the external **commit point**.

The examples and tests use an **in-memory mock**. They are not Lu's actual trusted host. P2Y never stores the HMAC key or trusted host anchor alongside its journal and cannot replace a host trust store or secret manager.

## On-disk format

For each committed request, persist deterministic `P2YDurableRecord` at `0000000001.p2y`, etc. Each record binds: exact P2W update request bytes, exact independently verified P2W output bytes, conversation/volume, authority epoch, ordered sequence, previous record MAC, and the current HMAC-SHA256. Records are exclusive-create, fsync'd and directory fsync'd before requesting host anchor commit; no appending to or overwriting an existing journal entry. Unexpected files, symlinks, non-private POSIX permissions and unfinished temporary writes cause recovery rejection.

`P2YHostAnchor` lives *outside* this directory, including sequence, HMAC chain head, checkpoint hash, and authority epoch. On restart, P2Y enumerates all records, rejects unexpected/missing/extra items, validates each HMAC, checks external anchor parity, independently executes every saved request through `P2XSession.advance(validate_parity=True)`, and verifies exact P2W result bytes. The P2X cache is then warmed using reverified intermediate work; no persisted raw cache is trusted.

A disk write may succeed immediately before the host commit fails. In that case the file is an **unanchored tail**. P2Y freezes and recovery fails closed; operator-assisted reconciliation with the true host high-water mark is required. Automatic truncation is intentionally not included. This is a 2-phase protocol, **not** a filesystem+host distributed transaction. Genuine OS-crash durability and power-failure atomicity are unverified.

Revocation/epoch changes are read from the authority before each update. All earlier records stay pinned to their original epoch; an epoch mismatch fails instead of quietly assuming prior authority. Host key rotation and safe re-enrollment/migration are deferred.

## Bounded resources

* `MAX_RECORDS=256` and `MAX_RECORD_BYTES=16_000_000`; when capacity is reached, fail closed and require a separately designed authenticated compaction protocol.
* Files contain plaintext observation/request data (HMAC integrity but **no encryption**). Real deployments need host-managed keys, per-profile private storage, quota/retention policy, and privacy review.
* Restart validates every record from the beginning; this is O(history), not constant-time recovery.
* The wrapper invokes independent full replay per update; it should not be advertised as the P2X fast path. Real host and Windows p95/p99/durable fsync profiling are pending.

## Validation

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2y_durable_incremental_volume.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2y_profile.py --rounds 5 --out /tmp/p2y_profile.json
```

For broad regressions, run `PYTHONPATH=. python -m pytest -q tests/test_c07* tests/test_c13* tests/test_c14* tests/test_c15*`.

## Promotion gates

1. Connect to a genuine separate trusted host key/anchor store (with cross-process CAS and revocation), without modifying Lu from this research checkpoint.
2. Windows x86-64 file atomicity/fsync, ACL, power-loss and restart tests; test same-profile contention.
3. Multi-key rotation, revocation & recovery and safe compaction/retention, including unanchored-tail reconciliation.
4. Real calibrated sensor / 3D benchmark correctness under camera motion, occlusion, clock drift and provenance spoofing.
5. End-to-end latency, memory, disk throughput and privacy review with sustained real recordings; compare full P2W and P2X under matched settings.
