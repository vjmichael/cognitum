# Cognitum P13 → P14 → P16 — Linux engineering checkpoint

**Date:** 2026-11-01 (America/Phoenix; host logs are UTC).  
**Base:** Exact P12 handoff archive `Cognitum_P12_Kernel_Gated_Durable_Admission_2026-11-01.zip`.  
**Product boundary:** Cognitum only; no Lu source or release changes.  
**Disposition:** Linux development tests **PASS within tested scope**; live kernel cgroup-v2 acceptance **BLOCKED**; independent OS-managed recovery deployment **PENDING**. **NOT production certified.**

## User directive: Windows DEFERRED

P15 and **all Windows-specific Cognitum engineering, Job Object containment, integration, CI, acceptance and packaging tasks** are marked **DEFERRED indefinitely** pending explicit user reauthorization. They are excluded from the active P13 → P14 → P16 sequence, but not waived or considered passing. This does **not** modify independent Lu Windows alpha work. See `WINDOWS_DEFERRED_20261101.md`.

## P13 — kernel cgroup readiness and tests

- Added `cognitum/cgroup_preflight_p13.py`: read-only readiness inspection, explicit `ready_for_live_tests`, and **always** `kernel_enforcement_tested: false` until real testing is performed separately.
- Added 4 negative/static readiness tests; passed.
- Added 2 opt-in live kernel acceptance tests (`tests/test_cgroup_p13_live.py`) to exercise real controller readback, trusted blocked-child attachment and cgroup.kill when a writable delegated cgroup is supplied.
- The host has Linux 6.18.57 and cgroup2 (`memory`, `pids`), but the mount is `ro` and no delegated writable subtree exists. The P13 live tests both **skipped**. The P12 live tests also both **skipped**. No memory-pressure/OOM, pids-limit exhaustion or recursive cgroup.kill proof is asserted.
- Production requires a properly delegated non-root cgroup v2 subtree, live memory and pids enforcement/overload testing, descendant kill under host/guardian death, repeated OOM/recovery and boundary resistance to path tampering. Never pass the mount root as delegation and never synthesize fake cgroup control files as security proof.

## P14 — independently supervised Linux recovery

- New module `cognitum/recovery_watchkeeper_p14.py` with a dedicated `python -m cognitum.recovery_watchkeeper_p14` entry point. Runtime requires admin-selected absolute admission parent, writable delegated cgroup base, short bounded interval, and a single-instance OFD lock; missing/readonly kernel delegation **denies before durable mutation**.
- `--once` emits machine-readable JSON status and exits nonzero on denial/blocked recovery. Continuous mode is designed to be launched/restarted by a separate OS supervisor.
- Added **uninstalled** systemd example `deploy/cognitum-recovery-p14.service.example`; no systemd registration, installation, or production service supervision was performed in this environment.
- Added 7 focused tests including separate-process reconciliation of a crashed reservation, external subprocess SIGKILL/restart with **explicit simulated cgroup validation**, competing supervisor lock denial, active-owner exclusion, root-gap cleanup, and cross-nonce cgroup-selection denial.
- **Security repair:** P12 could create a sandbox root in the interval before `mark_active()` and lose its name if both processes died. P14 names that root with the durable nonce and recovers the exact root in the `reserved` state. Active recovery additionally requires the durable nonce to match the cgroup scope name. Live kernel cleanup under simultaneous host-and-guardian death remains unverified.
- P14 remains cooperative per-UID; not cross-UID machine authority, not arbitrary untrusted-Python or seccomp certification. The independent service cannot convert a missing actual kernel proof into success.

## P16 — Linux guard performance and reliability

- Updated the P11 guardian to use Linux `pidfd_open` readiness in `select()` instead of waking every 50 ms for an idle worker. When pidfds are unavailable it keeps the existing bounded poll. Host socket EOF is continuously watched; worker-exit status remains tracked and reaped.
- Added a real guardian idle-CPU/liveness/cleanup test.
- Before/after **120-request** runs (same local host, real Linux namespaces, *no required cgroup mode*) succeeded:
  - Baseline: duration 10.788 s; median 326.359 ms; p95 510.629 ms; p99 525.157 ms.
  - P16 pidfd: duration 10.687 s; median 314.318 ms; p95 491.416 ms; p99 551.635 ms. Different tail measurements; no statistically established latency improvement.
- **1,000-request** P16 soak: 1,000/1,000 expected results (calculator 334, HDC 333, SSM 333), duration **68.497 s**, p50 **291.602 ms**, p95 **586.854 ms**, p99 **656.970 ms**, max **737.924 ms**; peak warm reservations 4; no new sandbox roots; zero warm reservations after shutdown. The soak used namespace-only shared guarded workers, not P13 kernel-required mode. The later P14 root-gap fix affects only cgroup-required warm workers; the 1,000-run predates that small fix and does not certify it under load.
- These are measured on one non-isolated Linux host; thread scheduling and other loads vary. The improvement compared to the previous P11 79.9-second run is *suggestive* but not a controlled apples-to-apples optimization proof.

## Regression accounting

Final combined P8/P9/P11/P12/P13/P14/P16 source/test suite:

**62 passed, 4 skipped, 1 deselected; 44.39 s.** The four skips are the two P12 and two P13 live cgroup tests; one upstream KAN fixture test was deselected because its artifact was absent from the recovered source. P16's separate 1,000-request soak passed. Local source patch applied against P12 and verified byte-for-byte. New wheel built from exact P12 wheel metadata plus updated modules; isolated installation smoke passed and read-only cgroup rejected.

## Reproduce

```sh
PYTHONPATH=. pytest -q \
 tests/test_sandbox_warm_p8.py tests/test_contained_warm_p9.py \
 tests/test_warm_guardian_p11.py tests/test_cgroup_p12.py \
 tests/test_durable_admission_p12.py tests/test_cgroup_p12_live.py \
 tests/test_cgroup_p13_readiness.py tests/test_cgroup_p13_live.py \
 tests/test_recovery_watchkeeper_p14.py tests/test_guardian_pidfd_p16.py \
 -k 'not test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'
```

To run *live* P13 tests, independently provision a writable delegated cgroup-v2 subtree with `memory` and `pids` enabled, then use `COGNITUM_P13_DELEGATED_CGROUP=/sys/fs/cgroup/DELEGATED_SUBTREE PYTHONPATH=. pytest -q tests/test_cgroup_p13_live.py -vv`. The tests intentionally skip if unset. Do not claim OOM/pids stress certification from those two initial tests alone.

Run the real P14 service under a user-authorized, installed service manager only after verifying kernel delegation and the durable admission directory are correct; the example unit is not deploy-ready without configuration. The `--once` CLI cannot run successfully on this read-only test host; that denial is expected and safe.

## Open Linux production gates

1. Real P13 kernel memory/OOM, PID exhaustion, and recursive kill/descendant containment on a writable cgroup-v2 delegate.
2. Actual OS-supervised P14 repeated host+guardian+reconciler crash/restart with kernel cleanup and service-manager restart; persisting the admission directory across reboots.
3. P16 repeated multi-process/long-duration soak under **required-kernel** P13 mode, resource-pressure profiling and variance-controlled before/after benchmarks.
4. Investigate wider Cognitum component readiness, including causal confidence calibration and HDC/KAN/SSM broad correctness benchmarking, as separate tracks.

**Windows work remains entirely deferred.**
