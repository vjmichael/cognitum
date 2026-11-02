# Cognitum P9 — Host-wide contained standby allocation and lifecycle repair

**Date:** November 1, 2026
**Base:** P8 branch `cognitum/component-quality-p8-contained-standby-20261101`, commit `b9fbe52d7ccbffa87cbd7869358ceb7f3289acd5`
**New branch:** `cognitum/component-quality-p9-host-fleet-lifecycle-20261101`
**Status:** Local Linux engineering regression **PASS** in tested scope; opt-in research path only, **not production certified**.

## What changed

1. **Fix two lifecycle deficits in the actual P8 worker pool:** `maintain()` now reaps expired or unexpectedly dead *idle* namespaces proactively and starts replacement workers, instead of allowing stale standbys to occupy reservations indefinitely. The pool's host-controlled target adjustment now performs an additional refill check **after** exited processes are reaped and global capacity is released. Global warm reservations are never released before process cleanup. `expired_reaped` and `crashed_reaped` counters expose both paths.
2. **Host-wide two-by-default allocation:** New `ContainedWarmFleet` distributes two total standby reservations among one or both **reviewed** P7-contained calculator/specialist pools, rather than each provider independently defaulting to two. A dual-provider host starts **one calculator + one specialist**. A single-provider host starts **two**. Actual admission misses permit a trusted host maintenance tick to expand the requesting provider up to the **shared four** cap, with at least one per enabled provider. This keeps the exact original 1-minimum / 2-default / 4-maximum policy meaningful across the host.
3. **Pressure and quiet handling:** Trusted code can pass a boolean pressure signal to maintenance, reclaiming idle above one per provider; an unpressured single-provider host returns to two by default. Extended quiet trims surplus above the normal two-standby baseline. Busy workers are not killed to satisfy a soft resize; their reservations continue counting until process exit. The host must call `maintain()` (or use a trusted host-owned periodic service); no model-invoked tuning control exists.
4. **No bypass:** All warm workers continue to launch through the same P7 Linux user/mount/PID/net/IPC/UTS namespace and read-only filesystem path. When a standby is absent, execution remains the bounded P7 cold sandbox path. Runtime authorization/schema/permission checks remain prior to dispatch. No Lu changes. HDC, KAN and SSM remain in one Cognitum package, with KAN still hash-gated.

## Executed local acceptance

- `pytest -q ... -k 'not kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'`: **27 passed, 1 deselected** in **14.88 s** (18 P8 regression cases + 9 newly authored P9 cases). The deselected P8 KAN fixture imports another upstream test module not included in the preserved P8 handoff ZIP. It previously passed in P8, but **was not rerun here**.
- Real Linux namespace/isolation preflight: PASS; P7 probe proved PID namespace root PID=1, read-only code, no host `/etc`, no host mount and restricted network from previous acceptance. This turn also exercised the P7 isolation probe via P9 tests.
- New tests: 2-global-standby split, proactive TTL recycling, dead worker repair, demand growth bounded by four, host pressure reclamation, one-provider minimum, quiet surplus reclamation, malformed fleet admission and **36 authorized mixed `Runtime.call` executions** spanning calculator/HDC/SSM under bounded concurrency and pressure changes. No worker reservations leaked after teardown.
- P9 wheel: P8 metadata/extras preserved, replaced revised module and added `contained_warm_fleet.py`, rebuilt valid PEP 427 RECORD, installed with `pip --no-deps --target` in an isolated directory. The installed package successfully launched contained standbys and executed rational arithmetic. **Installed-wheel smoke PASS**.

## Honest scope limits

- Tests ran on the current Linux container with working `unshare`, but its cgroup v2 mount is **read-only**. Host pressure is a trusted flag, not kernel-enforced memory/pids isolation. Seccomp and arbitrary hostile-code acceptance are not provided.
- Windows restricted token / AppContainer / Job Object standby construction and verified termination remain open. No Windows production or Linux general-untrusted-code certification.
- The 27 passing tests are a **selected regression**, not the full canonical Cognitum suite or a long-run stress/memory soak. The P8 19/19 and 181-case results are earlier evidence, not duplicated in this P9 run.
- Fleet allocation is process-wide, not interprocess; separate Cognitum host processes could each allocate their own four. A deployment-wide allocator would require explicit host coordination.
- There is no claim of lower LLM inference latency, improved causal estimation calibration, verified arbitrary KAN checkpoint code safety, or changes to C14/G25. Cognitum remains an add-on distinct from Lu.

## Next gates

1. Repeat full canonical Cognitum regression and sustained mixed-load soak with peak RSS/p95/p99, fault injection and no descendants/zombies.
2. Add authoritative host-pressure sensing and prevent cross-process excess reservations if multiple Cognitum hosts are supported.
3. Obtain writable delegated cgroup-v2 test host, and separately verify actual cgroup memory/pids limits, cleanup and descendant containment.
4. Windows Job Object / restricted-token or AppContainer P9 equivalent; independently smoke installed wheel.
5. Keep scientific validity/calibration tests separate from worker infrastructure optimization.

**Decision:** P9 is a reviewed local development patch against P8 and a preserved unified development wheel. Do not auto-enable, merge to `main`, or claim production worker security.
