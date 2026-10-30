# C06 P7 — Native Rust memory mutation fence and Protobuf host bridge

**Status: offline CANDIDATE implementation, not compiled or deployed to Lu.**
Library development date: 2026-10-27. Source pins: Cognitum P6 checkpoint and Lu `vjmichael/jan_alt` commit `bf2334a7d68f72265c37711de9bb5eda1f611d13` on branch `lu/ce-broker-revocation-fence` (read-only audit). The Lu branch ref was reconfirmed against this SHA; no checkout, branch, AppData, or GitHub contents were modified.

## P7 source changes

- `src-tauri/lu-core/src/ansf_memory_gate.rs` extends P6 with **`with_source_mutation`**: commit dirty marker before touching source, re-acquire policy `BEGIN IMMEDIATE`, re-check host ownership/revocation, execute a synchronous host mutation, reconcile ANSF catalog, atomically clear dirty/increment index epoch. If a source operation fails, the durable dirty marker remains through restart. Reader/revoker second connections wait for the mutation lease (after the dirty write and recheck). Original `begin_source_update` and `reconcile_source` are retained for explicit crash recovery.
- `src-tauri/lu-core/src/ansf_memory_proto.rs` adds **`HostMemoryFrameAdapter`**, converting bounded canonical `cognitum.memory.v1` request frames into host-verified ANSF evidence and source-rechecked citations under a synchronous SQLite read lease. Malformed/duplicate/unknown-field requests, non-canonical frames, unsupported exact-source filters, unsafe sizes, stale citations and authorization denial fail closed. It has no grant token, file path, model tool, webview IPC, or user-provided `HostPrincipal` field.
- `src-tauri/lu-core/proto/cognitum/memory/v1/evidence.proto` is an **exact copy** of the checked-in Cognitum C06 schema. The installer augments Lu's existing `prost-build` step to compile both Lu's existing proto and this separate package with its existing vendored compiler; no JSON data plane introduced.
- `apply_overlay.py` is a dry-run-first, pinned-commit installer checking a **clean** Lu Git tree, module/build anchors, Rust dependencies, and absence of collisions. With explicit `--apply` it writes **five scoped Lu paths** only: two Rust files, one Protobuf schema, and minimal edits to `src/lib.rs` and `build.rs`. It neither starts a Lu runtime nor pushes to GitHub.
- Added Rust unit/integration tests for native host mutation success/failure/reentrancy, canonical Protobuf, search → citation, and evidence-free denial after revocation. **Not executed** without Rust toolchain.

## Verified with available local tools

- Python 3.13 Linux: **339/339** Cognitum unit tests, **12/12** synthetic replay cases, **10/10** C03 arithmetic component smoke cases, Python compilation passed.
- Independent `protoc` v3.13.0 (vendored with installed Torch, with proto3 optional flag) compiled **all nine** Cognitum schemas; descriptor wire shapes matched all checked-in Python `*_pb2` bindings. This closes the *Python schema-source parity* check. It does **not** generate, compile, or test Lu's native Prost binding.
- Safe-overlay installer tests, Rust source SQL DDL executed in Python SQLite, and host-frame source/Protobuf wire shape tests pass. These are not a substitute for compiling Rust.

## Integration and authority boundaries

1. The **native Lu host** must authenticate its current profile/project/user turn independently and construct `HostPrincipal` out-of-band. The public Rust struct does not authenticate itself. Never take principal, paths, or SQL handles from frame/model/webview data.
2. The host must constrain the policy DB and ANSF book/catalog to app-owned, OS-protected paths. P7 overlay does not itself establish Windows ACLs, and does not register a CE, native tool, model API, or webview command.
3. `HostMemoryFrameAdapter::search_frame` and `citation_frame` publish **synchronously inside** the policy transaction via a trusted host callback. There is no safe automatic asynchronous queuing of borrowed evidence. Citation handles and snapshot IDs are *locators*, never grants.
4. **All ANSF mutations/imports** must pass through the new `with_source_mutation` / explicit dirty/reconcile protocol. Existing Lu `AnsfStore` methods still exist publicly; the overlay does **not** automatically prevent out-of-band callers, imports, maintenance code, or direct SQLite writers from bypassing the gate. Real routing remains a Lu integration task.
5. Reconciliation across source and catalog SQLite DBs is **not atomic**, and reads are protected only if every writer honors the policy DB gate. The source update creates a durable dirty phase for crash repair; it does not establish distributed consensus.
6. Revocation and logical tombstones prevent reads but do **not** physically delete ANSF entries, revisions, SQLite FTS5 shadow tables, WAL files, exports or backups; secure deletion/purge policy is unresolved.
7. C02 native worker isolation/C04 host approval and actual model benchmarks are not complete. Do not enable a model-callable memory CE on this evidence.

## Native test sequence required on a Rust-equipped **isolated test checkout**

```sh
# From the unpacked Cognitum P7 checkpoint:
python integrations/lu/apply_overlay.py --lu-root /path/to/clean/jan_alt
python integrations/lu/apply_overlay.py --lu-root /path/to/clean/jan_alt --apply
cd /path/to/clean/jan_alt/src-tauri/lu-core
cargo test ansf_memory_gate -- --nocapture
cargo test ansf_memory_proto -- --nocapture
cargo test
```

Next: review/merge host ownership of every ANSF ingress/egress path, add a **real authenticated Lu desktop broker lifecycle** without model exposure, verify Rust compilation and Windows host tests, and run C06 benchmark cases under the C03 Lu+model capture contract before a promotion claim.
