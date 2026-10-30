# C06 P9 — isolated native Lu test gate (Library-only)

**Date:** 2026-10-27  
**Outcome:** test harness implemented; **native Rust gate BLOCKED** until Cargo/rustc are available. This milestone does not change either GitHub repository or the Lu application.

## Scope

The Cognitum P7 Protobuf+ANSF Rust overlay is still an uncompiled candidate. The P8 test runner required users to prepare an exact, clean, already-overlaid Lu checkout; this was a manual and destructive-looking barrier. P9 adds an optional `integrations/lu/p9/native_test_workspace.py` and Windows PowerShell wrapper. Given an existing **local** Lu Git clone containing commit `bf2334a7d68f72265c37711de9bb5eda1f611d13`, the tool:

1. Verifies the exact commit exists in local Git history and records the original worktree status.
2. Creates a temporary, sparse, offline `git clone --shared --no-checkout` and checks out the pinned commit without changing the user's checkout.
3. Performs P7's fail-closed source/anchor checks and writes the three new overlay sources and the two exact modifications **only to the temporary clone**.
4. Performs P8's native preflight, optionally executes Cargo tests, reports nonzero test counts, status, and logs fingerprints. Cargo defaults to offline mode; dependency downloads require explicit opt-in.
5. Deletes the temporary clone on pass, block, or failure, and writes the status and potential Cargo.lock digest to a JSON file **outside** either code tree.

It does not install Rust, connect to Lu's process, enable a CE, read personal memory, authenticate Lu callers, grant permissions, or physically purge records. The original Lu worktree is not reset/cleaned/touched.

## Test evidence

On the current container: `cargo` and `rustc` were absent; remote Git hostname resolution was unavailable. Consequently, there is **no native Rust compilation evidence**. Offline tests exercised an actual Git sparse-clone fixture using a temporary synthetic SHA (never represented as the real Lu SHA), verified that overlay preflight passes, that source worktrees are preserved, that wrong pins and unexpected edits fail closed, and that missing Cargo produces a blocked report. The full Cognitum suite passed **360/360**, replay **12/12**, C03 smoke **10/10**, and independent compiler verification of **9/9** Protobuf schemas passed. All are *Python/schema-side*, not Lu production acceptance evidence.

## Next gate

Run `-Mode all` on a trusted Windows x86-64 machine with Rust >=1.88, Python 3.11+, Git for Windows, and the local Lu checkout. Capture the resulting JSON and Cargo.lock hash; review/fix actual Rust compile/test failures. Then verify the desktop's caller authentication and that all ANSF storage mutations go through the host gate. Only after this can C06 consider model-facing capabilities and real Lu+model P3 measurements. See `integrations/lu/README_C06_P9.md`.
