# Cognitum C15 T3 P2Y — durable journal and restart recovery

**Status:** offline engineering verification passed; trusted host integration and production recovery acceptance **NOT** passed.

## Implementation

Adds a research-only, append-only exact-Protobuf P2W request/output journal, HMAC-chain over records, fsynced exclusive record creation and externally anchored authority CAS. The host must keep the secret and latest anchor separately and durably. Restart rejects missing, extra, changed, unanchored or revoked history and independently full-replays each saved record; it never trusts persisted P2X cache bytes. A commit failure after file creation leaves an unanchored tail and blocks continued use until trusted external reconciliation.

A 74th Protobuf schema defines `P2YHostAnchor` / `P2YDurableRecord`. New `P2YDurableSession` and 16 focused tests cover restart parity, tampering, deletion/rollback, wrong key, anchor drift, revocation, epoch mismatch, concurrent session writer, uncommitted tail, hostile extra entries, unknown wire fields, symlinks, file permissions and bad inputs.

## Verification

- P2Y focused tests: **16 passed**.
- Independent schemas: **74/74 compiled and descriptors matched**.
- Broad C07/C13/C14/C15 suite: **1,600 passed, 39 skipped, 638 subtests passed** (5 warnings). Clean-extracted P2X/P2Y integration: **31 passed**. Source ZIP integrity: **814/814 hashes verified**.
- Exact saved/rehydrated P2W lifecycle parity: passed across a two-update synthetic sequence. Full-replay validation enforced on every update and each recovered record.
- Parent P2X checkpoint unchanged apart from schema registry extending compilation coverage.

## Synthetic local Linux CPU profile, 5 rounds

| Operation | Median |
|---|---:|
| P2X, direct full replay of two sequential updates | 97.408 ms |
| P2Y, two durable commits with fsync and mocked anchor CAS | 109.511 ms |
| P2Y, revalidate and recover the two-record journal | 93.481 ms |
| On-disk journal size | 20,490 bytes |

These are narrow Linux synthetic measurements and do not include real host persistence, OS power-failure testing, upstream capture processing, Windows filesystem semantics, or real 3D sensors. P2Y is **not faster** than P2X on this comparison. Restart recovery is deliberately O(history) and caches are rebuilt only after replay.

## Security and scientific limitations

- Mock authority is not Lu. Host-issued key, protected external high-water anchor and atomic cross-process CAS are required for protection against rollback; neither is provided by this standalone checkpoint.
- HMAC provides integrity, **not encryption**. Captured observations and requests are plaintext; private directory and file permissions are checked on POSIX. Windows ACL and key management are untested.
- A bad or incomplete disk/host commit fails closed; host crash-reconciliation and journal compaction are deferred.
- No new map/camera/identity claim gains measured, physical, or navigation authority. R1 is the unchanged tracking-performance baseline; no changes to Lu, GitHub, or original user datasets.
- Real-sensor correctness, long-duration disk/memory/p95/p99 validation, Windows testing and host integration remain in the deferred benchmark backlog.

## Reproduction

```bash
PYTHONPATH=. python -m pytest -q tests/test_c15_t3_p2y_durable_incremental_volume.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c15_t3_p2y_profile.py --rounds 5 --out /tmp/p2y-profile.json
```

See `P2Y_START_HERE.md` and `docs/components/spatial/P2Y-durable-restart-journal.md` for the external authority requirements and restore model.