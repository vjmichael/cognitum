# Cognitum P46R8 — Recovery result integrity and isolated Lu-Linux build

**October 31, 2026.** Local-first Cognitum development. GitHub is source and milestone storage; no Lu release or main-branch changes.

## Security issue corrected

The P46R6 `host_recovery --execute` CLI could exit successfully for a host-written `HOST_REPORTED_CLOSED_UNATTESTED` marker and for an empty job ledger even when the delegated root was **not** a writable kernel cgroup2 filesystem. The first case conflated host-reported closure with independent kernel cleanup; the second relied on vacuous `all([])`.

P46R8 checks the kernel root and writable mount **before** execute-mode reconciliation (including an empty ledger). Only a result with exact status `KERNEL_TREE_CLEARED_UNATTESTED` can receive a successful *cleanup CLI exit*; this still does not authorize worker execution or independently attest security.

A separate long-running `recovery_service` issue accumulated all response objects forever. Continuous operation now streams records without retaining them in an ever-growing array; explicitly bounded tests retain their requested history.

Two historical tests were adjusted to expect rejection of an unauthenticated fake cgroup root.

## Reproduced local tests

- **120/120 passing** across 11 bounded Cognitum suites: 7 new P46R8 tests, 23 durable recovery, 11 recovery service, 14 alpha worker, 4 actual-worker fault tests, 5 Lu readiness, 7 parent-lifetime, 7 P46R4, 17 P46R3, 19 P47 evidence, 6 P46 archive-audit.
- Baseline P46R7 run of the seven new tests: **2 assertion failures and 3 errors** (expected negative control). P46R8: **7/7 pass**.
- Lu native test client: **13/13 passed independently** using its protocol/security fixtures; no live Lu server was contacted.
- No full repo suite is asserted. Linux cgroup v2 remains read-only; real `cgroup.kill` containment has not been demonstrated.

## Isolated Lu-Linux build development

A complete Lu source snapshot at `68eab79e2799c02cec8949993cebd64215f00559` was recovered from the Library. Eight original L16 overlay files and four SHA-guarded P0 native test-host overlay files were applied and verified in a disposable workspace.

Recovered offline build prerequisites: Rust/Cargo 1.98.0, 989 vendored Cargo crates, pinned `fix-path-env`, and 438 Debian 13 dependency packages extracted to an isolated sysroot. Full Cargo metadata resolves offline. A development-only Tauri config omits **bundle resources** for type-checking (not for package acceptance); its icons were derived from existing Lu artwork.

The GUI feature-enabled offline `cargo check` progressed through system libraries and Lu Core, then **failed in Lu's Rust source with two specific errors**:

- `E0432`: missing `lu_core::persistent_llama_backend::LinuxModelProtectionPolicy`
- `E0599`: missing `PersistentLlamaBackend::set_linux_model_policy`

These APIs are used by the L16 Linux inference adapter but absent from the pinned Lu Core source and checked Lu development branches. **Do not remove or bypass the security policy to get a green compile.** Restore/rebuild it with explicit tests before attempting the real native test-host model/tool turn. This work has NOT produced a running Lu socket or alpha binary, nor has any Cognitum native worker been dispatched by Lu.

## Gate disposition

1. Cgroup kernel descendant cleanup: **BLOCKED** on read-only mount.
2. Independent recovery: **HARDENED** with 120 focused passing tests; still no production cgroup kill.
3. Lu-Linux test-host: **offline source and toolchain recovered; full compile BLOCKED** by missing Linux model-protection API. Release packaging and authenticated model/tool/Cognitum integration **NOT ACCEPTED**.

Native extension admission remains denied.
