# Cognitum Linux P13 → P14 → P16 local handoff

P15 and all Windows-specific Cognitum work are **DEFERRED** by user direction. This handoff contains P13 kernel readiness and opt-in live tests, P14 independent recovery service + simulator-identified crash tests, and P16 pidfd event-driven guardian + 120/1,000 request soak evidence. Lu is unchanged.

**Engineering pass:** 62 tests pass with 4 live-kernel tests skipped and 1 KAN fixture deselected; P16 1,000/1,000 completed, 68.497 s. **Not production-certified:** the local cgroup-v2 mount is read-only, and no OS supervisor is installed.

The `patches/Cognitum_P13_P14_P16_from_P12.patch` applies to the exact P12 archive; 11 patched source/test/deployment files were byte-verified. The complete source tree is provided directly in this package. The development wheel is a local build; do not promote it to release without the outstanding kernel and recovery acceptance.

See `Engineering_Report_P13_P14_P16_20261101.md`, `WINDOWS_DEFERRED_20261101.md`, `evidence/p16/*.log`, and `evidence/p16/*.json` for details. The sample service unit is under `deploy/` and is not installed.
