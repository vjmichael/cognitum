# C06 P3: Lu ANSF read-path compatibility (offline, non-installable)

**Date:** 2026-10-27  
**Owner:** Cognitum engineering, Library-first development  
**Lu reference:** `vjmichael/jan_alt` commit `bf2334a7d68f72265c37711de9bb5eda1f611d13`, specifically `src-tauri/lu-core/src/ansf.rs`, `ansf_revisions.rs`, `ansf_library.rs`, `ownership_store.rs`, and `conversation_authority.rs`. These Lu sources were inspected read-only; neither repository nor the user's Lu databases were changed.

## Delivered and limitations

`cognitum/ansf_read_reference.py` adds a **schema-compatible, bounded, read-only Python SQLite reference**, not the eventual native Rust host adapter. It accepts *only* an already-open, host-supplied SQLite connection with `PRAGMA query_only=ON` and an active read transaction. It does not take paths, open source databases itself, authenticate the caller, grant scope, supply tombstone authority, update ANSF, or expose a CE/model tool. The host must explicitly inject tombstone state; omission fails closed. Injected Python objects are **not proof of host identity**.

`dispatch_host_fenced` adds two inert host-lease-only operations, `ansf_fts` and `ansf_citation`. The new read path constructs untrusted candidate refs and canonical snapshots inside a synchronized lease, delegates mandatory source/digest/revision/scope validation to P1/P2, rechecks host-owned generation/revocation/cancellation, and publishes the complete Protobuf result *synchronously while still fenced*. The `DeliveryReceipt` contains no evidence. An asynchronous output queue after unlocking violates the contract.

Native C06 Protobuf schemas remain unchanged from P2: no new authority-bearing fields or JSON internal wire format were introduced. The read path maps `SourceRef.entry_id` to the *original* immutable `ansf_entries.id`, `revision_id` to the precise source entry ID, `chapter_id` to the actual original chapter ID, and `current_revision_id` to the latest `ansf_entry_edits.revised_entry_id` (or the original ID if unedited). All are represented as canonical positive decimal strings. Session IDs must satisfy P1's bounded ASCII source grammar; arbitrary Lu IDs not representable under that contract are deliberately rejected, not silently mangled.

The existing ANSF FTS5 index and `bm25` rank hits. A bounded sanitized token query prevents untrusted MATCH syntax or SQL interpolation. The Python comparator uses token AND, not perfect byte-literal or identical search semantics to all future Lu queries. Its output is *source hints*, never authorization. It filters superseded FTS hits unless both a host grant and the query permit historical results, checks immutable edit-chain linkage, scopes to the host-selected session, rejects missing/corrupt source, and limits canonical text to 16 KiB. Source excerpts remain canonical UTF-8. An individual book's query may miss lower-ranked results beyond the fixed 64-hit scan; this is an explicitly bounded reference, **not a production exhaustive retrieval guarantee**.

Citation expansion accepts a non-secret locator, reopens the same source from a fresh host-fenced SQLite read, revalidates current revision and content hashes through P2, denies revoked/deleted histories, and rejects forged/obsolete citations. The existing Lu ANSF schema has **no deletion/tombstone or physical-purge protocol**: P3's tombstones are strictly synthetic host-injected fixture state, not evidence of erasure.

## Adversarial evidence

`tests/test_c06_ansf_reference.py` creates disposable, in-memory SQLite books using a subset of Lu's actual table, FTS5 and edit-link schema; it does not import or copy user conversations. Cases exercise cross-session isolation, current vs historical revision, stale original FTS hit, FTS operator neutralization, Unicode bytes, malformed schema/links, reference IDs, tombstones, change-before-publication revocation/index epochs/cancellation, citation editing/revocation/deletion, direct candidate injection denial, and mandatory host-controlled read transaction. Full preexisting suite continues to run.

## Unresolved *production* gates

1. Implement the **native Rust** `Lu::HostMemoryReadLease` in Lu's actual host/service graph and bind to an authenticated desktop principal, `OwnershipStore::require` and canonical conversation-to-book ownership/path. No request may provide an owner, book path, authorization scope or SQLite connection.
2. Specify host-approved, durable deletion/tombstones and retention/backup/WAL handling. Until finalized, a deleted ANSF entry is *not* safe to declare physically erased and may remain in original/FTS/revision storage.
3. Prevent revocation/retention/index changes from being acknowledged ahead of any in-flight publication; establish reliable lease synchronization across host/native model output. Fix disconnected/desynchronized callers; synthetic locks only prove local fixture behavior.
4. Add Lu-side native ABI/service calls for exactly scoped read/citation requests; P3 is not registered and no Protobuf bridge can authorize itself. Resolve C02/C04 gates before native CE/tool exposure.
5. Confirm Lu's actual FTS5, SQLite/Windows behavior, non-ASCII IDs, book path confinement, WAL/read locking, import mutations, and multi-session result pagination with real host integration tests. No installer, live user data, production security audit or Lu+model A/B/C/D trial has been run.
6. Independent `protoc` cross-compilation remains pending where toolchain is absent; the existing generated Protobuf descriptor and source parity tests still run.

**Promotion decision:** PASS for the disposable ANSF-schema conformance prototype; **BLOCKED** for production Lu authenticated ANSF adapter and model/CE registration.
