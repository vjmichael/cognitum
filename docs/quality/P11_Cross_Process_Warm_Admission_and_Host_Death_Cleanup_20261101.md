# Cognitum P11 — Cross-process warm admission and host-death cleanup

**Engineering date:** 2026-11-01 America/Phoenix (test records 2026-11-02 UTC)  
**Base:** Cognitum P10 source snapshot, continuing P9 `cognitum/component-quality-p9-host-fleet-lifecycle-20261101` and P10 negative gates  
**Status:** **PASS within the bounded Linux P11 research-engineering scope; NOT a production/untrusted-code sandbox certification.**  
**Lu:** No Lu source, authority, or production algorithms modified.

## Resolved P10 negative results

1. **Two independent Linux Cognitum host processes previously admitted six warm workers.** New explicit `shared_admission=True` enables four cross-process cooperative advisory `flock` slots for processes running under the **same OS UID and canonical admission directory**. Each reservation precedes any warm launch. Admission failure leaves the warm request to the existing P7 cold namespace fallback. No shared-slot reservation is released simply because a host crashes.
2. **Host SIGKILL previously left private sandbox roots.** Every P11-admitted warm worker is now created by an **independent guardian process**, which holds an inherited open-file-description lock. Its authenticated control socket closes on host death, triggering a forced P7 namespace-group teardown, worker reaping, sandbox-root deletion, and only then lease release. The guardian, not the Cognitum host, creates the root and starts P7, preventing a host-crash launch-registration gap.
3. If the guardian crashes while the Cognitum host remains alive, a parent-death signal is installed on the guardian-launched P7 leader and a pinned `pidfd` lets the surviving host verify termination before independently removing the sandbox root and releasing the lease. A guardian/host simultaneous crash is **not covered** by this fallback; a privileged durable service or writable delegated cgroup is needed for a stronger kernel-enforced invariant.
4. An inherited P9 pool race removed prewarm threads from tracking before guardian teardown finished. P11 preserves the thread until cleanup and reservation release finish, and concurrent `close()` requests cancellation without double-owning guardian cleanup.

## Exact local acceptance evidence

| Gate | Actual result |
|---|---|
| Four shared admission slots, fifth rejected | PASS |
| Two actual Linux Cognitum hosts targeting three workers each | PASS: aggregate 4 live standbys, never 6 |
| Host SIGKILL on two idle guarded workers | PASS: both stopped, roots removed, leases reusable |
| Repeated host SIGKILL / immediate restart with three other hosts running | PASS: 3 cycles, observed admission capped at 4 |
| Guardian SIGKILL while Cognitum host survives | PASS: pidfd-verified worker termination, host fallback root removal |
| Host SIGKILL with worker blocked reading a partial request | PASS: worker terminated, root removed, shared lease freed |
| P11 guardian acceptance suite | **7/7 passed** |
| P8/P9/P11 combined regression including 120 mixed authorized HDC/SSM/calculator requests | **34 passed, 1 deselected**, 43.43s |
| 1,000 authorized HDC/SSM/calculator operations, 8 concurrent threads | **1,000/1,000 passed**, 79.94s pytest; measured 78.751s within fixture |
| Standby crash recycling and age expiry | PASS in both 120 and 1,000 request tests |
| Graceful shutdown leak check | PASS: 0 local warm reservations and 0 **new** `cognitum-isolate-*` roots |
| Wheel import/install and P11 guarded real contained calculation | PASS |
| Source patch apply to recovered P10 baseline | PASS: byte-exact match on five files |

The 1,000-request test comprised **334 calculator, 333 HDC, and 333 SSM** operations, all verified against expected results. Measured request latency: **p50 293.643 ms**, **p95 639.196 ms**, **p99 743.605 ms**, **max 996.735 ms**. Warm reservations never exceeded four. The test used actual Linux namespaces, full authorized `Runtime.call`, local machine load, adaptive standby changes, forced worker termination, and idle expiration. P10's unguarded comparable run was 34.869 s, so P11 guardian/process coordination has a real throughput and latency cost; avoid claiming P11 is a speed optimization.

The 120-request mixed test passed 40 calculator, 40 HDC, and 40 SSM operations in 10.467 s. It observed a process-local maximum of four warm reservations, a 683.912 ms pressure-settle interval, and zero reservations after shutdown. P11 warm admission slots were not claimed by two separate fresh test processes during the 1,000-request run; that denial was **expected** and confirms the exclusive shared slot mechanism, not a regression. Guardian tests were repeated with no conflicting test process after the soak completed (7/7 passed).

## Limits and residual production gates

- **Not machine-wide across different UIDs**, different admission paths, or hosts that still use P8/P9 with `shared_admission=False`. P11 is **opt-in and cooperative**: all participating hosts must use the same canonical lock path. For a hard multi-user machine-wide limit, use a privileged central service or cgroup-backed delegated admission.
- `flock` coordinates admission but is **not a process/resource isolation boundary**. There is no verified kernel `memory.max`, `pids.max`, `cgroup.kill`, or seccomp layer. The test machine's cgroup-v2 mount is read-only. These remain blocking production security gates.
- Loss of both Cognitum host and guardian at the same instant is not certified for durable root reclamation; `PR_SET_PDEATHSIG` reduces worker-liveness risk, but does not independently remove abandoned filesystem roots.
- Windows Job Objects and Windows installer/DLC integration were not tested; this module is Linux-only.
- Exactly one upstream KAN fixture test was **deselected** because recovered P10/P9 sources lack `test_research_optional.kan_artifact`. This is a missing fixture, not proof of KAN correctness.
- `tmp` root files from *earlier* interrupted P10 tests were not deleted by P11; its leak assertions compare before/after counts for new roots. Do not interpret zero **new** roots as cleanup of arbitrary historical directories.
- Development wheel uses the existing `cognitum_core-0.1.0` metadata and is for local testing, not a release artifact.

## Operational enablement

Host-selected Python API (never enabled by a model/tool payload):

```python
from cognitum.sandbox_linux import LinuxNamespaceExecutor
from cognitum.sandbox_warm_pool import LinuxSandboxWarmPool
from cognitum.contained_warm_fleet import ContainedWarmFleet
from cognitum.plugins.calculator import Calculator
from cognitum.plugins.specialists import Specialists

calculator = LinuxSandboxWarmPool(LinuxNamespaceExecutor(), Calculator,
                                  shared_admission=True)
specialists = LinuxSandboxWarmPool(LinuxNamespaceExecutor(), Specialists,
                                   shared_admission=True)
fleet = ContainedWarmFleet([calculator, specialists])
try:
    fleet.start()
    # Host integrates runtime authorization and calls fleet.maintain().
finally:
    fleet.close()
```

Keep the P7 cold fallback, explicitly authorized runtime paths, timeout validation and one-shot execution. Preserve the host-wide **two default / one minimum / four maximum** *within participating P11 workers*; do not claim that cold fallback workers count toward the warm quota.

**Next priorities:** (1) hard multi-UID host admission or an explicitly enforced single-UID deployment; (2) real writable-cgroup pids/memory and recursive kill tests; (3) Windows Job Object equivalent; (4) performance profiling of new guardian startup and IPC; (5) full canonical Cognitum suite/KAN fixture recovery.
