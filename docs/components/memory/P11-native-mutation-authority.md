# C06 P11 — Native mutation-authority candidate (Lu overlay; NOT DEPLOYED)

Date: 2026-10-27. Active source: `integrations/lu/src-tauri/lu-core/src/ansf_memory_gate.rs`.

## Work completed locally

* Added `MemoryMutationKind` action scope and `TrustedMemoryMutationAuthorizer` host trait. C06 writes, imports, topic operations, source reconciliation, logical deletion and terminal revocation require an independent host decision, not merely Lu's `OwnershipStore.require(..., Read)`.
* `ScopedAnsfMutation` rejects effect escalation: a revision-authorized scoped mutation cannot append, and an append-authorized mutation cannot edit/import.
* `begin_source_update` is no longer public. Host-admitted mutations commit a durable `c06_mutation_operations` PENDING entry and `source_dirty=1` before touching ANSF. A successful source/catalog reconcile marks the operation COMMITTED and bumps index epoch. Failure or crash leaves the source dirty; an independently authorized Recover event may reconcile and mark pending operations RECOVERED.
* SQLite DDL enforces unique operation IDs, immutable operation identities, and terminal COMMITTED/RECOVERED states. Duplicate IDs reject without source replay.
* Protected delete/revoke now require distinct Delete/Revoke admission. Authenticated principals are constructed by Lu; fake test verifier is confined to Rust tests.
* Added Rust tests for deny-by-default, explicit action binding, idempotency and untrusted-event rejection; added executable SQLite/DDL and source-contract Python tests.

## Production security gates still OPEN

1. **No native Rust compilation occurred** in this container. `cargo` and `rustc` are unavailable. The test module must run on Windows x86-64 against the pinned `lu-core` in a disposable checkout, with compile errors fixed and additional native concurrency/fault-injection scenarios added.
2. **No authenticated Lu host adapter exists yet.** The trait is a seam, *not* credential issuance: Lu must implement it using its own persisted authenticated event/origin, distinguish human user edits and approved host ingestion, bind scope/effect/grant epochs and origin to memory update, and synchronize revocation with the same read/write policy fence.
3. **No all-writer enforcement yet.** Lu's public `AnsfStore` mutators/import path can bypass this overlay until all desktop persistence paths have been audited and routed through a single native broker, including trusted import and maintenance flows.
4. **No physical deletion yet.** ANSF revisions, FTS5, WAL, backups and external replicas need a separate retention/erasure design. Tombstone is immediate logical exclusion only.
5. **No native Windows ACL certification, worker permission/grant proof, actual Lu+model P3 benchmark, or installation.** `HostPrincipal` by itself is not authenticated proof.

## Production acceptance scenario to run next

Authenticated Lu user edits message -> host verifies persisted user turn and permission for `Revise` -> P11 fenced operation writes dirty/journal marker -> ANSF append-only revision -> index reconciliation -> commit operation and epoch -> C06 retrieval produces only current revision and invalidates prior citation. Test denials for model-origin event, read-only caller, other session, expired/revoked grant, duplicate operation, process crash before/after ANSF write, and another connection's in-flight read. The verified host must own both admission and coordinated revocation.

No GitHub repositories, Lu runtime, installer or user data were modified in this Library-only implementation.
