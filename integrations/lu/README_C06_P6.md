# C06 P6 — candidate native ANSF memory gate for Lu

**Status:** Rust source overlay prepared and Python/SQLite DDL contract tested. **Not compiled, not installed in Lu, not production-enabled.** This checkpoint is built in Cognitum Library, and GitHub is unchanged.

## Source baseline and provenance

- Lu repository: `vjmichael/jan_alt`, inspected at `bf2334a7d68f72265c37711de9bb5eda1f611d13` on `lu/ce-broker-revocation-fence` (2026-10-27 source pin). **Do not assume this remains the branch head.**
- Native crate target: `src-tauri/lu-core` (`Cargo.toml` contains `rusqlite=0.32`, `sha2=0.10`).
- Reviewed Lu APIs: `ansf::{AnsfStore, Entry}`, `ansf_revisions::revision_history`, `ansf_sync::reconcile_book_index`, `ansf_library::{AnsfLibrary,BookIndex}`, `ownership_store::OwnershipStore::require`, `host_resource_authority::{HostPrincipal,ResourceAction}`.
- Cognitum source baseline: `Cognitum_C06_P5_Library_Checkpoint_2026-10-27.zip` in `/Cognitum/Development`.

## Contents

- `src-tauri/lu-core/src/ansf_memory_gate.rs` — native Rust host-side read/revocation/recovery service and **seven unexecuted Rust tests**.
- `apply_overlay.py` — opt-in, clean-working-tree, **pinned-commit-only** copy into a local Lu checkout. Dry-run by default; never pushes GitHub.
- Python `tests/test_c06_lu_native_overlay.py` exercises **the actual SQLite schema string from the Rust module**, not an independently transcribed schema. This is useful limited verification and **not** a substitute for a Rust compile/test.

## Security assumptions and behavior

1. Lu host authenticates `HostPrincipal` from its own user/session state. **A model or webview must never construct this principal** or invoke the service directly. The Rust API cannot authenticate its caller on its own.
2. Host enrolls resource ownership in `OwnershipStore`, then calls `AnsfMemoryGate::enroll`. Policy DB path and book/catalog handles must be host-confined and not under model-provided paths.
3. `with_search` / `with_citation` acquire SQLite `BEGIN IMMEDIATE` on durable policy DB; host-supplied **synchronous** publication callback executes while that transaction is held. Reentrant calls from callback are rejected. Never enqueue or retain evidence beyond the read lease.
4. `revoke` permanently disables the session. `tombstone_root` irreversibly hides a canonical root and its revision history. These are **logical** deletions, not secure erasure or retention-policy compliance.
5. Before ANY Lu ANSF source mutation, the trusted host calls `begin_source_update` and commits a durable dirty marker. Readers fail closed while dirty. After the source and cross-book catalog are reconciled, `reconcile_source` clears dirty and bumps index epoch. A crash between steps leaves dirty set across restart. The host must not bypass these methods.
6. The current reference accesses `AnsfStore` APIs across multiple SQLite statements. It depends on routing all ANSF writers through Lu's host gate. It is **not** safe against arbitrary bypassing writers/processes, a compromised host, DB file replacement, or historical source physical erase/purge.
7. The gate is deliberately **not registered as a native tool, CE, webview IPC, or model endpoint**; it does not grant Cognitum access to real Lu data. Crossing into Cognitum requires a separate reviewed Protobuf-native broker adapter, mapping returned evidence to `proto/cognitum/memory/v1/evidence.proto` and enforcing frame bounds. No JSON internal contract is introduced.

## Validation to run in a real Lu checkout

The host developer should run the following in a secure test fixture, before integrating any desktop route:

```sh
python integrations/lu/apply_overlay.py --lu-root /path/to/jan_alt --apply
cd /path/to/jan_alt/src-tauri/lu-core
cargo test ansf_memory_gate -- --nocapture
cargo test
```

The `apply_overlay.py` path above is relative to this *Cognitum checkpoint*, not the Lu checkout; run it from the checkpoint source directory. The installer refuses a different Lu commit or a dirty checkout. Rust toolchain and native `protoc`/compiler are absent in this session; neither Rust test nor Windows build were run here.

## Remaining release gates

- Compile Rust patch against latest Lu APIs; fix any errors after tests execute.
- Move authorization and policy DB creation into a real authenticated Lu host lifecycle, including non-model reachability and user consent.
- Route **all ANSF mutators and imports** through durable dirty fencing; model/UI must have no bypass path.
- Test restart with WAL, multi-process file locks, concurrent source writes, cancellation during callback, file swaps, DB corruption, rollback, and backup/restore.
- Design safe physical deletion/retention and encrypted backup policies, independent of logical tombstones.
- Implement versioned Protobuf cross-boundary adapter and perform pairwise Lu+model benchmarks. Preserve C02/C04 host security gates.
