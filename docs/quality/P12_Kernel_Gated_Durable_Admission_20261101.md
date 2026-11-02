# Cognitum P12 — Kernel-gated admission and durable recovery

**Engineering date:** November 1, 2026 (America/Phoenix); test logs November 2 UTC  
**Baseline:** P11 — shared Linux worker admission and guardian cleanup  
**Disposition:** **PASS for implemented local software and denial/negative tests; live writable-cgroup-v2 acceptance BLOCKED; NOT production-certified.**  
**Separation:** Cognitum only; no Lu source or authority changed.

## What changed

1. **Mandatory kernel containment is host-selected, opt-in.** `LinuxSandboxWarmPool(..., shared_admission=True, cgroup_base=<trusted delegated cgroup>, cgroup_memory_bytes=268435456, cgroup_max_pids=32)` validates a real cgroup-v2 mount and writable delegated subtree with memory+pids controllers. It refuses read-only roots. No request payload can select the path.
2. **Execution gate:** the independent guardian creates a dedicated cgroup, applies and reads back `memory.max`, `pids.max`, `memory.oom.group=1`, then launches a fixed trusted Python gate. The guardian attaches that still-blocked process to `cgroup.procs` and verifies membership **before** sending its one-byte release token. Only then can the gate `execve('/usr/bin/unshare',...)` and start the existing P7 sandboxed worker. A failed attach never releases the token; the process is killed and reaped.
3. **Kernel-level shutdown path:** the scope writes `cgroup.kill=1`, checks `cgroup.events populated=0` by a bounded deadline, and removes its cgroup. A failed empty proof denies cleanup completion. The guardian removes the sandbox filesystem root and marks the durable record closed only after the kernel cleanup succeeds. On guardian death while the Cognitum host survives, the host attempts exact-scope kernel kill *before* waiting for the pinned launcher pidfd.
4. **Durable four-slot ledger:** P12 uses a separate owner-only admission directory with four OFD-locked slots. An fsynced and atomically replaced marker records `reserved → active → closed`. On abrupt termination, the lock may disappear but the marker remains **poisoned**, preventing admission reuse. The cgroup name derives from the marker's random 128-bit nonce, permitting an independent reconciler to handle even the scope-created / pre-launch-record gap. Never infer success from a stale PID or a free file lock.
5. **Recovery capability:** `DurableWarmAdmission(...).reconcile_once(cgroup_base)` touches only unheld exact P12 slots. For an active record it validates the fixed cgroup path, invokes kernel kill/empty/removal, validates/removes the exact worker root, then durably closes the marker; uncertain cleanup remains blocked. This function is **not installed or running as a service**. Simultaneous host-and-guardian death is fenced for admission, but cleanup is not automatic until an independently supervised reconciler is deployed.
6. **No downgrade:** when a worker is requested in `cgroup_base` mode and no eligible warm worker is available, the pool returns `overloaded` rather than starting an ungrouped P7 cold worker; stale warm workers return unavailable. Existing P11 namespace-only cold fallback remains available for hosts that did not require a kernel cgroup.

## Actual local tests

| Test group | Result | Interpretation |
|---|---:|---|
| P12 cgroup gate/control-flow and hostile input tests | 11 passed | Includes real Linux namespace launch with **simulated** cgroup attach, failed-attach denial, no ungated fallback, fake kernel readback and destroy tests |
| P12 durable admission tests | 5 passed | Owner-process death, poisoned lease, fifth-slot rejection, malformed durable record, live-lock exclusion; independent reconciler simulated/negative checks |
| P11 real Linux guardian/cross-process/host-SIGKILL tests | 7 passed | Existing P11 behavior preserved |
| P9 real Linux lifecycle/mixed workload tests | 9 passed | Existing HDC/SSM/calculator behavior preserved |
| P8 namespace worker tests | 18 passed | One upstream KAN artifact test excluded because fixture is absent |
| **Total combined** | **50 passed, 2 skipped, 1 deselected** | 35.78 s final run; two P12 kernel-live tests **skipped**, not passed |
| New wheel installation smoke | **PASS** | Isolated install, P7 real contained calculator result 5, P12 read-only cgroup denied |

The host has a working Linux 6.18.57 and cgroup-v2 with `memory` and `pids` controllers, **but `/sys/fs/cgroup` is mounted read-only**. No delegated writable subtree was supplied. Therefore **no live `memory.max`, `pids.max`, cgroup.kill descendant or OOM containment claim is established here**. The P11 1,000-request soak evidence remains valid for P11; P12 was not subjected to a new 1,000-request test in required-kernel mode.

## Deployment constraints and remaining gates

- P12 is **single-UID/cooperative**, not a hard machine-wide limit across arbitrary OS users, admission directories, or legacy P8/P9/P11 hosts running simultaneously. All candidate processes need the same P12 admission directory. Require a machine authority service for cross-UID enforcement.
- The helper/gate is a fixed trusted launch component briefly outside the cgroup while blocked; no arbitrary Cognitum plugin code executes until after attach. This is **not** an arbitrary-untrusted-Python sandbox or seccomp certification.
- A durable marker fences uncertain leases; **an independent OS-supervised recovery process must still be deployed** and tested for simultaneous host + guardian death. `reconcile_once` is not equivalent to installing a service.
- Live kernel tests require a correctly writable delegated cgroup-v2 subtree. Do **not** invoke them on the cgroup mount root or bypass the fail-closed checks.
- Windows Job Object equivalent and physical Windows execution were not implemented/tested in P12. Keep Windows admission disabled for this path until proper suspended-process-to-Job-Object-before-resume and descendant cleanup are tested.
- The missing `test_research_optional.kan_artifact` fixture prevents the upstream KAN case from being rerun; do not call it a passing KAN test.
- This is a locally rebuilt `cognitum_core-0.1.0` **development wheel**, not a production release.

## Reproduce

```bash
PYTHONPATH=. pytest -q tests/test_cgroup_p12.py tests/test_durable_admission_p12.py tests/test_cgroup_p12_live.py tests/test_warm_guardian_p11.py tests/test_contained_warm_p9.py tests/test_sandbox_warm_p8.py -k 'not test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'
```

For an independently provisioned, **writable, non-root delegated** cgroup with `memory` and `pids` enabled (only on an appropriate Linux test host):

```bash
COGNITUM_P12_DELEGATED_CGROUP=/sys/fs/cgroup/<trusted-delegated-subtree> PYTHONPATH=. pytest -q tests/test_cgroup_p12_live.py -vv
```

If that test passes, follow with an external-supervisor crash matrix: host/guardian simultaneous SIGKILL, restarted reconciler `reconcile_once`, surviving descendants, repeated exhaustion, cross-UID interference, memory/pids pressure and filesystem poisoning.

## Next decision

P12 is ready for a **writable-cgroup test host**, not production promotion. The next acceptance gates are live kernel containment, externally supervised crash recovery and Windows Job Object parity, without modifying Lu.
