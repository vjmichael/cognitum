# Cognitum P10 — Sustained contained-worker soak, pressure and deployment negative controls

**Date:** 2026-11-01 (America/Phoenix; evidence captured 2026-11-02 UTC)

**Base:** Cognitum P9 contained warm fleet, branch `cognitum/component-quality-p9-host-fleet-lifecycle-20261101`.

**Scope:** Local Linux trusted pure Cognitum operations, P7 namespace isolation and P9 warm-worker lifecycle. No production code modified. This milestone tests current behavior; it is **NOT a production acceptance or a general untrusted-code sandbox certification**.

## Executed tests

### Stable sustained workload — PASS

- **1,000/1,000 operations completed**: 334 calculator, 333 HDC, 333 SSM, all expected results checked via authorized `Runtime.call`.
- 125 bursts of eight operations, `ThreadPoolExecutor(max_workers=8)`, actual P7 namespace warm and cold execution. **34.869s elapsed**, median **204.277ms**, p95 **314.797ms**, p99 **366.134ms**, max **408.290ms**.
- Real idle worker `SIGKILL` induced replacement; an expired worker was recycled; expected outputs remained stable.
- A controlled 128 MiB page-touched memory allocation moved the real cgroup `memory.current` reading enough to trigger the trusted-host pressure flag. The allocator returned to one standby per enabled provider, accounting for any in-progress preparations before requiring the global reservation to settle. This is a **load-signal exercise, not memory.max enforcement**.
- Observed process-local global warm reservations **never exceeded four**; **zero reservations after graceful shutdown**. No new `cognitum-isolate-*` roots after successful teardown. No cgroup OOM events recorded.
- `memory.current` was about 705 MB at the first sampled point, reached about 871 MB, and is a whole-cgroup reading (NOT individual worker RSS). Throughput/latency reflect this container and do not establish model inference speed.
- Detailed machine-readable record: `evidence/soak_1000.json`.

### Scoped P8/P9 + P10 regression — PASS within scope

- **28 passed, 1 deselected in 19.27 seconds**.
- One upstream KAN fixture test (`test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold`) was **not rerun** because the P9 handoff lacked its `test_research_optional` fixture module. This is a coverage gap, not a reported KAN defect.
- Evidence: `evidence/regression.log` and `evidence/soak_120_regression.json`.

### Host SIGKILL while standby is idle — PARTIAL

- Three real host SIGKILL trials: the observed worker process became **gone or zombie/non-executing** shortly after host exit. This narrowly confirms it did not continue executing in those cases; it is not a proof of recursive cleanup under all fault modes.
- All three trials left a private sandbox root directory after host death. The independent harness explicitly removed those roots. Root cleanup/reconciliation after an ungraceful host exit remains **OPEN**.
- Evidence: `evidence/host_sigkill_3_trials.json`.

### Two independent Cognitum host processes — NEGATIVE / DEPLOYMENT GATE FAIL

- Two independent processes each reserved **three actual P7 contained standbys**, yielding **six live workers** on one machine.
- Each process remained under its *local* four cap. P9's `_GLOBAL_WARM_BUDGET` is not coordinated across processes, so **machine-wide maximum-four cannot be claimed** when multiple Cognitum hosts are supported.
- Evidence: `evidence/multi_host_cap.json`. Requires an explicit cross-process host-owned lease/coordinator with crash recovery or a supported single-host deployment policy.

### Kernel cgroup / Windows security gates — NOT RUN / BLOCKED

- Linux host uses cgroup-v2 on `/sys/fs/cgroup` **read-only**. `memory.max` shows **4 GiB**, `pids.max=max`. No delegated writable test cgroup was available for safe kernel `memory.max`, `pids.max`, `cgroup.kill`, descendant or OOM containment acceptance.
- Real Linux namespaces run, but user/mount/PID/net/IPC/UTS isolation alone is not proof of resource- or hostile-code confinement. Seccomp is not certified.
- This execution environment is Linux, not Windows. No Windows restricted-token/AppContainer/Job Object acceptance or installer wheel runtime smoke is claimed.

## Regression investigation

The first draft P10 pressure test incorrectly required reservations to drop instantaneously on a pressure signal. P9 intentionally keeps a reservation until a worker that was already warming has been reaped. The test now checks **bounded settling** rather than violating this cleanup ordering; no production code was changed.

Early 1,000-request attempts were interrupted by outer command-execution time limits after near-complete progress, leaving abandoned test-only root directories. Those were inventoried and cleaned after confirming there were no live workers. The successful 1,000-request trial used independently supervised local execution and graceful teardown; its evidence is authoritative for the PASS claim.

## Decision and next work

**P10 sustained operational behavior: PASS within tested Linux scope. P10 multi-host production admission: FAIL. Full production worker containment: NOT CERTIFIED.**

Next engineering tasks: (1) host-wide leases and cross-process admission with crash recovery; (2) rootfs scavenger / durable supervisor after host SIGKILL; (3) writable delegated cgroup2 acceptance with real memory/pids/process-tree kill limits; (4) Windows Job Object/restricted-token worker parity; (5) full canonical Cognitum suite including KAN fixture and distinct scientific validity gates. Preserve independent Lu ownership and keep Cognitum add-on only. GitHub is the source/documentation ledger, not the development execution environment.
