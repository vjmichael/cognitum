# C06 P8 — Native Lu Rust test gate (blocked, with reproducible evidence)

**2026-10-27 · Library-only milestone · No GitHub mutation · NOT a compiled Lu build**

This checkpoint begins the native Lu validation phase without implying that a
Python simulation is equivalent to native Rust execution or host authentication.

## Source audit and the blocker

- Cognitum source baseline: Library C06 P7 checkpoint (146 approved source files).
- Pinned Lu branch `lu/ce-broker-revocation-fence`: `bf2334a7d68f72265c37711de9bb5eda1f611d13`, rechecked read-only.
- Independent connected GitHub reads of `ansf.rs`, `ansf_revisions.rs`, `ansf_sync.rs`, `ownership_store.rs`, `host_resource_authority.rs`, `lib.rs`, `build.rs` confirmed the source APIs and anchors referenced by the overlay. Their file blob SHAs are recorded in `docs/components/memory/P8-pinned-source-audit.json`.
- This container has **no `cargo`, `rustc` or network access to the Rust distribution**, and there is **no mounted full Lu checkout**. The native Rust compile/test gate remains **BLOCKED**, not passed.
- A successful offline P8 run does not imply the Lu desktop host is wired, Windows ACLs are correct, all ANSF mutation/import paths are fenced, or physical source/history erasure is available.

## Executable work completed

The new **opt-in native test runner** is `integrations/lu/p8/native_gate.py`. It performs a fail-closed preflight and then, only when explicitly executed on an isolated Lu checkout with Rust installed, runs Cargo tests:

1. Confirms exact pinned Lu Git commit, that the worktree differs by only the five expected P7 overlay paths, and that those paths have precisely the expected bytes. No other local edits are accepted.
2. Compares `src/lib.rs` and `build.rs` against deterministic changes to their original pinned Git versions, ensures `Cargo.toml` is unmodified, and compares the 3 added source/schema files byte-for-byte.
3. Requires both `cargo` and `rustc`. Runs `cargo test ansf_memory_gate`, `cargo test ansf_memory_proto`, then `cargo test`. Distinct scopes are needed because an unexecuted filtered test can otherwise return a false success.
4. Refuses Cargo's exit-zero/zero-matching-test results; a command needs an actual `test result: ok. N passed` with N>0. Any failure is reported, not reclassified as a pass.
5. Emits a machine-readable JSON report **outside** the Lu checkout; it never initializes a live model, grants authority, installs a CE, changes Windows AppData, or pushes to GitHub.

Additional eleven regression tests exercise the runner's positive preflight, wrong Lu commit, unexpected source changes, byte drift, mutated anchors, missing compiler, mock-only command flow, compile failure, zero-matched-tests fail-safe and safe report output. The mocked command tests prove the test runner's control flow **only**, not Rust functionality.

## Local P8 evidence

- **350/350 Cognitum Python tests passed**, including eleven new P8 orchestrator tests.
- **12/12 synthetic arithmetic replay**; promotion evidence `false`.
- **10/10 C03 component smoke**; no Lu/model test arms executed.
- **9/9 Cognitum Protobuf schemas** independently compiled with vendored `protoc`; bindings matched. This still does not compile Lu's Prost Rust bindings.
- The existing Rust overlay was not changed in P8; the previous 5-path installer remains an opt-in candidate.

## Steps on an *isolated, disposable* Lu checkout with Cargo

Unpack this P8 archive and supply a separate clean Lu checkout pinned at the exact SHA. Do not run these against an active working tree with uncommitted edits. From the extracted **Cognitum** root:

```powershell
# Dry-run the existing five-path overlay first
python integrations/lu/apply_overlay.py --lu-root "C:\path\to\disposable\jan_alt"
# Only for the disposable, confirmed pinned checkout
python integrations/lu/apply_overlay.py --lu-root "C:\path\to\disposable\jan_alt" --apply
# Verify full exact overlay and execute the Rust native tests
python integrations/lu/p8/native_gate.py --lu-root "C:\path\to\disposable\jan_alt" --mode all --report "C:\path\outside\jan_alt\c06-p8-native-report.json"
```

Native pass is necessary, not sufficient. The next engineering activity is to wire the memory gate to **host-authenticated, trusted Lu lifecycle handlers** and run Windows host/concurrency/mutation audits, ensuring every ingress path uses the fence. No model-facing retrieval should be enabled until that succeeds.
