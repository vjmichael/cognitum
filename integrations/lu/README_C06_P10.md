# Cognitum C06 P10 — session-scoped ANSF writes and private policy storage

**Status:** Candidate Lu Rust source overlay; **not compiled, installed or authorized**.

Source baseline: Cognitum Library P9 (`Cognitum_C06_P9_Windows_Native_Test_Preparation_2026-10-27.zip`). Overlay target: Lu `vjmichael/jan_alt` commit `bf2334a7d68f72265c37711de9bb5eda1f611d13`. Neither GitHub repo was modified.

## Concrete correctness/security changes

1. The fence callback in `AnsfMemoryGate::with_source_mutation` now receives `&ScopedAnsfMutation` rather than raw `&AnsfStore`. The scoped interface binds every append, edit, topic and import operation to `self.index.session_id` and exposes no unrestricted store handle or caller-selected session parameter. The policy dirty marker still persists before mutation, and reconciliation and epoch update are still fenced.
2. `check_policy_storage` rejects missing/non-directory policy parents, existing symlinks or non-file database targets. On Unix, the parent must have no group/other access and the policy file must have no group/other access; new DB files are opened using mode `0600`. The Unix test fixture uses a private `0700` directory. **Windows filesystem ACL verification remains a requirement of the authenticated Lu host and is not supplied by this module.**
3. Added three native Rust tests (session isolation, rejected cross-session import that remains dirty, and insecure-path/symlink/file permissions on Unix), plus four Python source-level contract tests. Updated the existing source-contract assertion to the new scoped API.

## Locally executed verification (2026-10-27)

- Python 3.13: **364/364** unit tests passed with `PYTHONPATH` set to this source directory.
- Synthetic calculator replay: **12/12** (component fixture, not a model benchmark).
- C03 typed Protobuf smoke: **10/10** (no Lu/model arms).
- Independent `protoc` compilation and Python descriptor checks: **9/9**.
- **Native Rust: 0 executed.** This runtime lacks `cargo` and `rustc`, and has no package-network access. The added native tests were inspected, not executed; the source/API review is not a compile gate.

## Remaining security and integration gates

- Run the existing `integrations/lu/p9/run_windows_native_gate.ps1` against a disposable copy of the **exact pinned Lu commit** with Rust 1.88+. The overlay includes the P10 Rust sources automatically when unpacked. Fix compiler/test failures before any Lu host deployment.
- Connect the gate to a trusted, immutable Lu host identity and explicit mutation/deletion authorization. `HostPrincipal` is host-supplied context, **not itself an unforgeable credential**. In particular, the native Rust API still maps mutation authorization through `ResourceAction::Read`; this is not an approved production write authorization decision.
- Intercept every existing Lu ANSF mutator and Jan import path; direct `AnsfStore` calls bypass the memory gate. Ensure source update / reconciliation, cancellation and revocation are atomic at the permitted boundaries.
- Implement Windows private profile ACLs, physical erasure / retention (including WAL and backup handling), and Win x86-64 integration tests before enabling real user memory.
- No CE/model-facing memory permission, benchmark gain, Rust compilation pass or deletion/purge guarantee is claimed by this checkpoint.

## Preservation

Store this source snapshot as a new immutable ZIP in ChatGPT Library `/Cognitum/Development`. `CHECKPOINT_INFO.json` records per-file hashes and exact validation status; verify with `python tools/build_library_checkpoint.py verify <zip>`. Keep P9 and earlier checkpoints intact. GitHub is a future milestone publication target, not today's development workspace.
