# Cognitum P8 — OS-contained prewarmed workers

**Date:** November 1, 2026 (development milestone)  
**Product:** One `cognitum-core` distribution including HDC, KAN, SSM and the existing components  
**Status:** Linux engineering acceptance **PASS** within tested scope; **not production-enabled**

## Implementation

- `LinuxSandboxWarmPool` runs the 1-minimum / 2-default / 4-maximum bounded standby policy *inside* the existing P7 Linux user/mount/PID/network/IPC/UTS namespace and read-only chroot boundary. The same global four-worker reservation object applies to all participating warm pools; busy, idle and spawning workers count. No per-specialist bypass.
- Warm launch follows P7's own `unshare --kill-child` + private rootfs, stripped environment, read-only source/runtime mount, no home or `/etc`, dropped capabilities, `no_new_privs`, and CPU/address-space/file-descriptor rlimits. It is not an OS security claim for arbitrary hostile Python plugin code.
- A fixed, reviewed provider is selected before the child starts. The child completes P7's kernel-backed self-check before emitting its bounded readiness receipt. No model request or user task data crosses before authorization. Each sandbox serves *exactly one* framed request then exits.
- Cognitum `Runtime.call` still validates request, scope, schema, permission and output. The pool can be attached to sandbox mode only when bound to the **same exact** `LinuxNamespaceExecutor`. The old unsandboxed `WarmCappedPool` remains forbidden in sandbox mode.
- If ready capacity is absent, the request runs through P7's **sandboxed** cold executor and its existing shared eight-worker cold admission budget; it never falls back to unrestricted multiprocessing.
- Timeout, shutdown and worker crash paths terminate the P7 namespace process tree. Global warm reservations are released only after reaping. A failed prewarm never enters a spin-restart loop. The trusted maintenance service can shrink/replenish slots without blocking the tool path. Stale ready workers are not reused.
- HDC, SSM and host-hash-approved KAN execute in the same Cognitum wheel. Unapproved KAN is refused. Test-only probes do not register as Cognitum operations.

## Linux acceptance evidence

| Group | Result |
|---|---:|
| Dedicated P8 sandboxed warm tests including KAN parity, cross-pool cap, cold overflow, timeout/descendant and shutdown | **19/19 PASS** |
| Unmodified P7 Linux namespace/isolation suite | **27/27 PASS** |
| P4 legacy warm-pool suite (separate completed invocation) | **22/22 PASS** |
| P5 + P6 maintenance suites (separate invocation) | **25/25 PASS** |
| P6 cold budget + P2 batch suites (separate invocation) | **25/25 PASS** |
| Selected unified specialists / SSM / KAN / trace suites | **63/63 + 15 subtests PASS** |
| P2/P3 combined legacy process suite | **INCOMPLETE / NOT COUNTED**; hung under local execution limit |
| Single wheel build; isolated installed-wheel P8 namespace smoke | **PASS** |

**Total completed:** 181 pytest test cases plus 15 unittest subtests, from distinct completed commands. The interrupted P2/P3 group is excluded; some other Cognitum cross-domain suites were not run in this milestone. This is **not** a full current canonical repository acceptance and is **not** Windows acceptance.

## Matched latency (Linux development host; 12 requests each)

| Metric | Cold P7 namespace | Ready P8 namespace |
|---|---:|---:|
| Median `Runtime.call` | **77.818 ms** | **8.354 ms** |
| p95 (interpolated, small sample) | **82.791 ms** | **10.070 ms** |
| Relative median | -- | **9.32× lower latency** |

P8 initial two-worker prewarm took **74.273 ms** outside the tool request; replacement readiness wait p50 was **65.887 ms**. The measured warm hits were 12, misses 0, peak reserved count 3. The earlier ~5 ms *uncontained* warm benchmark is **not** comparable to this OS-contained P8 policy; the relevant baseline is the P7 cold **namespace** executor. No model prefill/generation or LLM routing time is included. No product p99/performance SLO is established.

## Artifact and provenance

A single `cognitum_core-0.1.0-py3-none-any.whl` was built via `pip wheel --no-deps --no-build-isolation`, independently installed outside the source directory, and used to start contained standby workers and compute the expected calculator result. The wheel includes `sandbox_entry_linux.sh`, `sandbox_warm_child.py`, `sandbox_linux.py`, and `sandbox_warm_pool.py`. It is a **development candidate** with current project version unchanged, not a second Cognitum product.

## Release gates still open

- Linux kernel cgroup v2 memory/pids enforcement is unavailable in this environment; rlimits alone are not equivalent. No seccomp policy or independent arbitrary-hostile-code sandbox certification.
- Windows restricted-token/AppContainer/Job Object containment, prewarming and installed wheel acceptance are not established.
- Broad current-source regression and continuous mixed HDC/KAN/SSM / CPU memory-pressure and worker crash soak remain necessary.
- Global four is enforced, but with multiple explicitly enabled provider pools, each pool's default target is two **subject to the shared maximum**. Long-term host-wide reservation selection, per-provider priority, warm memory accounting and p95/p99 need tuning.
- Cognitum scientific model validity and confidence calibration remain separate release gates. No change to frozen G25 estimator or production algorithm.

**Decision:** preserve P8 as an explicit, opt-in Linux research engineering path; do not promote to general-purpose production worker security. No Lu changes and no Cognitum-to-Lu integration.
