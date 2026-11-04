# C06/C07 → Lu ANSF integration audit (2026-11-04)

Source: `vjmichael/Lu-AI-GUI` main, reviewed without modifying Lu.

## Actual host APIs discovered

- `src-tauri/lu-core/src/ansf.rs`: `AnsfStore` owns a
  `Mutex<rusqlite::Connection>`, WAL+FULL durability and canonical
  `ansf_entries`/`ansf_entries_fts` with immutable source entries.
  Existing `search`, `read_entry`, `page_after`, `find_message`
  are the only approved integration starting points. Caller must
  authenticate conversation ownership before access.
- `src-tauri/lu-core/src/ansf_revisions.rs`: `current_message`,
  `append_edited_entry`, `revision_history` use an immutable
  `ansf_entry_edits` chain. Origins are `VerifiedUser` and
  `ImportObserved` and explicitly do not authorize tools.
- `src-tauri/lu-core/src/ansf_library.rs`: `AnsfLibrary` catalogs
  metadata references and FTS indexes, without duplicating source text.
  Its `search_books`/`search_chapters` are scoped, and its indexes
  are replayable across a crash but NOT atomically committed with source
  books. Host checks ownership and secure path resolution.
- The Rust host uses rusqlite, **not** Python `sqlite3.Connection`.
  Therefore the Python `host_event_adapter.py` cannot be attached to
  production Lu as-is. It is a concurrency/rollback reference, not
  an implemented Rust host connector.

## Correct next integration boundary

1. Lu authenticates owner/workspace and decides access to specific
   canonical ANSF book/session and revision.
2. Lu resolves effective `current_message` and host-index revision,
   retaining immutable original and correction chain. Detect and
   invalidate stale derived index entries after edits or deleted books.
3. Lu emits bounded, already-authorized Protobuf `MemoryEvidence`
   with opaque citation handles; no filesystem paths, bearer secrets,
   or raw permissions are accepted from Cognitum.
4. C06 recomputes search over the authorized snapshot and returns
   source IDs plus host citation handles, not privileged SQL access.
5. C07 state events require a new explicitly host-owned typed-claim
   sidecar/effect transaction defined by Lu; **do not reinterpret
   `ansf_entry_edits` as typed belief events** or store them inside
   unstructured chat text. Append and effect journal must share host
   transaction/cancellation semantics, or be crash-reconciled explicitly.
6. Actual host process restart, simultaneous edit and retrieval,
   workspace reassignment, deletion, stale index and adversarial source
   data tests are mandatory prior to approval.

## Existing guardrails and incompatibilities

- `AnsfStore::search` and `AnsfLibrary::search_books` already
  implement FTS5. Reuse them; no new canonical Python database.
- `AnsfStore` has `session_id` and `workspace_id` ownership, while
  C06's reference `access_scope` is a generic opaque value. Lu must
  bind these explicitly; matching a self-reported scope is insufficient.
- `AnsfLibrary` index changes are not cross-database atomic. Use
  source revision readback and staleness signals, never claim snapshot
  atomicity across book and catalog.
- A proposed Protobuf schema alone does not mean Lu's Tauri/Protobuf CE
  registry can dispatch it. Host enrollment, effect status and
  permission policy remain separately unimplemented.

This is an evidence-based integration specification, not a claim that
Cognitum is already linked to the Lu executable.
