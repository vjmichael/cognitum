# Cognitum P46R7 — Lu-Linux test-host overlay recovered

**October 31, 2026 | Gate 3 amendment to P46R7 / PR #45.**

**Disposition:** SOURCE OVERLAY VERIFIED LOCALLY; NO AUTHENTICATED LIVE LU HOST / COGNITUM DISPATCH PROVEN.

## Newly recovered Library artifacts

The first Library content search failed to find the named Lu source archives, but a subsequent top-level Library inventory revealed:

- `Lu_Linux_Native_Test_Host_P0_Overlay_2026-10-31.zip` (29,680 bytes).
- `Lu_Linux_L16_Preview7_Source_And_Evidence.zip` (380,112 bytes).

Both were copied into an isolated development workspace. Neither normal Lu GitHub `main` nor the existing Windows/Linux releases nor user profile files were modified.

## Locally measured source reconciliation

1. The L16 ZIP is **partial source**, not a runnable Lu repository checkout.
2. L16's `src-tauri/Cargo.toml` and `src-tauri/src/lib.rs` matched the P0 overlay manifest's old SHA-256 values exactly.
3. `src-tauri/src/core/mod.rs` was absent from the partial L16 archive; fetched its exact content from pinned Lu commit `68eab79e2799c02cec8949993cebd64215f00559`. Its SHA-256 matched the overlay's required old digest `0a2a7f942e65d96c4f7135efbf7a0510153d3501671450e5917af8011766b0d3`.
4. The overlay's `apply_overlay.py` dry-run accepted all four preimages. Applied exactly four Rust source files; each matched its declared **new** SHA-256.
5. Lu Python native socket client/security protocol tests passed **13/13** (mock test server only). No live Tauri Lu native socket was started.
6. Cognitum's P46R7 readiness probe of the reconstructed partial source now finds both required feature/module files, with **only** `LU_SOCKET_UNAVAILABLE` remaining in its preflight result. That is not authenticated host admission.

## Remaining P46R7 gates

- **Gate 1 blocked:** Linux cgroup2 in this runtime is read-only. No actual escaped descendant was killed with `cgroup.kill`.
- **Gate 2 partial:** An external `supervisord` process restarted the recovery-service interpreter after two SIGKILL events, and three instances inspected the same durable record. This was **inspection-only**; genuine cgroup kill and installed systemd service remain unverified.
- **Gate 3 partial:** The source overlay is now available and SHA-verified, but the L16 archive is not a complete Lu checkout, Rust/Cargo is unavailable in this runtime, and the feature-enabled Tauri server has never been compiled or launched here. No authenticated Lu model→Cognitum Protobuf tool→feedback round trip has occurred.

The preexisting `lu/linux-native-test-host` GitHub branch remains unsynchronized to L16; do **not** overwrite that branch with this partial source. The isolated checkpoint ZIP contains the verified partial source, original test client, tests and logs, and provenance report.

**No production/native-worker authorization is granted. No Lu general JSON repair or permission engine is moved into Cognitum.**
