# C07 P4 — Explicit temporal corrections and deletion-safe derived replay

**2026-10-27 · Offline Python/SQLite reference only. NOT installed in Lu, not real-model evaluation.**

## Temporal correction contract

The versioned `cognitum.state.v1` Protobuf schema adds `TEMPORAL_CORRECT = 7`, `StateEvent.corrects_event_id = 15`, and `ClaimView.effective_at_ms = 12`. These field-number extensions preserve earlier source wire numbers and are independently verified against `protoc` output. Events remain strictly decoded, bounded and deterministically encoded. An explicit temporal correction:

- must point to **the immediately preceding event** of that claim and match the exact claim CAS revision;
- may adjust *only* effective time, not subject/predicate, value, or stored event chronology;
- must be USER_VERIFIED or HOST_OBSERVED, never IMPORT_OBSERVED/MODEL_HYPOTHESIS; a host observation cannot demote USER_VERIFIED provenance;
- must be admitted with Lu-owned authenticated authority and a verified **current** ANSF source; any external event fields claiming user origin are untrusted;
- appends a new event; it does **not** rewrite the old event. Confirm/challenge/terminal markers do not silently change the claim's effective time.

This is correction of a claim's **effective timestamp**. It is *not* a full bitemporal interval model, a historical as-of query API, or automated historical truth inference; future components must explicitly model time intervals, clock uncertainty, temporal overlap and later adjudication if needed.

## Host-fenced derived state invalidation after source deletion

`StateJournal.rebuild_after_host_deletion` receives candidate `SourceEvidence` references and an **externally held Lu deletion lease**. It requires `confirm_source_deleted` to return strictly `True` for every exact source, verifies the expected journal head and generation, removes **entire affected claim chains** from the derived log (so no orphaned corrections or retained dependent claims survive), checks all remaining historical/current ANSF evidence, and atomically rewrites the surviving derived SQLite events and hash chain. The operation increments a durable generation counter, preserving compare-and-swap behavior across rebuilds and restarts. Retired event IDs are hashed and remembered so invalidated IDs cannot be recycled. A receipt contains only counts, generation and digest—not claim contents or reusable authority.

A journal that still references deleted evidence already **fails closed on publication** (P2/P3 host evidence verification). An interrupted rebuild rolls back atomically: the old, still-ineligible projection remains blocked until the trusted host retries reconciliation. A completed rebuild can publish only surviving, freshly verified claims. Future changes to those sources require revalidation at the next publication. All access to ANSF and real deletion/revocation fencing must still occur in Lu Rust; a fabricated Python `HostDeletionLease` is **never** a permission to destroy or publish personal data.

**Deletion limitation:** SQLite transactional `DELETE` only removes rows from the live logical view. It does **not** establish forensic erasure from free pages, journal/WAL files, OS caches, backups, copies, snapshots, logs, or the canonical ANSF book. Derived values may be sensitive. The Lu host must enforce capability-confined directories, encrypted storage/backups and an explicit verified secure-purge policy for these data remnants. The disposable P4 Python tests do not demonstrate physical deletion and do not alter real user sessions.

## Tests and residual gates

`tests/test_c07_p4_temporal_deletion.py` tests exact chronological correction, multi-source and nested claim-chain deletion, cross-restart replay, hostile source denial, stale or revoked lease, retained survivor verification, transactional rollback, stale head/generation, retired ID denial and corrupt metadata. Original C07 P1–P3 and C06 regression tests remain in the complete source checkpoint. See `P4-test-evidence.json` for executed commands and precise results.

The independent `protoc` check validates source/binding parity; it does not establish the quality of the Lu bridge or Rust compilation. **Unfinished:** real host-authenticated correction/delete authority; Lu-native Rust compilation and Windows x86-64 test; all ANSF writer interception, source-storage physical purge; end-to-end real Lu+model comparisons; potential derived-cache cryptographic anti-rollback. Cognitum stays a rebuildable *derived* projection, and Lu ANSF remains canonical memory.

**Follow-on implementation:** C07 P5 now adds explicit bounded validity intervals and bitemporal as-of queries (see `P5-bitemporal-uncertainty.md`); P4 remains the original gate baseline.
