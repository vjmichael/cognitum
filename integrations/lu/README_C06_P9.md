# Cognitum C06 P9 — local Lu native-test workspace (Windows first)

Status: **implemented and locally tested orchestration; Rust compilation NOT yet performed**.

P9 operates on an existing **local** Lu Git checkout with commit
`bf2334a7d68f72265c37711de9bb5eda1f611d13` already in its object store.
It does **not** use GitHub as a development environment, clone over the
network, install the overlay into an existing Lu source tree, or enable any
model-visible memory capability. It creates a temporary offline sparse clone,
checks out the pinned commit, overlays five files only in that clone, runs P8's
native Rust test gate, writes a JSON report, and deletes the disposable clone.

## Windows x86-64 usage

The machine needs Python 3.11+, Git for Windows and Rust (`cargo` and `rustc`)
version 1.88 or newer; its Cargo cache must already contain required crates
for the default offline run. Start in the unpacked Cognitum checkpoint:

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\lu\p9\run_windows_native_gate.ps1 `
  -LuSource 'D:\work\Lu' `
  -Report 'D:\CognitumTestEvidence\c06-p9-native.json' `
  -Mode all
```

Use `-Mode preflight` to check the overlay without invoking Cargo, or
`-Mode scoped` for only the two native C06 module test filters. `-Mode all`
additionally runs the full `lu-core` Rust tests. Only if you explicitly want
Cargo to download dependencies, add `-AllowCargoDependencyDownloads` (Lu source
is still cloned locally; only Cargo dependencies may be fetched). The Python
CLI offers the same options:

```powershell
python integrations/lu/p9/native_test_workspace.py --lu-source 'D:\work\Lu' --report 'D:\CognitumTestEvidence\c06-p9-native.json' --mode all
```

The report lives outside both source trees. Exit 0 with `native_gate=PASS`
means **native tests executed and reported nonzero passes**. Exit 0 with
`PREFLIGHT_ONLY` does *not* count as a compile or runtime pass. Exit 2 with
`BLOCKED` means a dependency, source-pin, overlay, compile or test gate failed.
P8 writes command exit status, extracted test pass counts and SHA-256 of log
content. Fake Cargo responses used in unit tests do not constitute real Rust
evidence.

## Boundaries and outstanding gates

- The original Lu worktree is never rewritten, cleaned, reset or deleted.
- The temporary clone is removed even when validation fails; no GitHub push.
- The overlay is not wired into a real authenticated Lu desktop host.
- All ANSF mutators and importers still require host-level interception;
  unaudited direct `AnsfStore` access is a security bypass.
- No deletion/purge of ANSF, WAL, FTS, backup, or historical revision bytes is
  implemented by this test harness.
- Real Win x86-64 Rust compilation, source-integrity and model benchmarks
  remain **pending** until a user-run Cargo-capable test report is available.

The test script is a *verification tool*, not a Lu installer and not permission
to grant an AI access to user memories.
