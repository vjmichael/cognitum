# Cognitum P5 — two-standby default, adaptive 1–4 warm capacity

**Date:** 2026-11-01  
**Source branch:** `cognitum/component-quality-p5-adaptive-two-standby-20261101`  
**Base:** `cognitum/component-quality-p4-four-warm-20261101`  
**Release:** opt-in **engineering candidate**; one independent Cognitum product, no Lu changes.

## Executive capacity decision

An explicitly enabled `WarmCappedPool` now starts with **2 ready workers**, has a **minimum of 1**, and can grow to a **maximum of 4**. This is a global per-host-process cap across specialist pools, counting *idle + warming + in-flight warm-origin processes*. A fifth concurrent request can still launch a cold disposable worker subject to a separate bounded cold-fallback admission limit. The total number of Python processes can therefore exceed four during overflow; **four is the warm-worker ceiling only**.

The pool is **not enabled by default in Cognitum's public Runtime**, because generic Python workers still lack OS-enforced sandboxing. When a trusted embedding opts in, the *pool's* default capacity is two.

- On sustained contention, an authorized request missing all standbys raises the warm target by one, at most four, and uses cold overflow immediately.
- `maintain()`, called by a trusted host on an idle maintenance schedule, drops the target one step after each configured 60-second quiet interval, down to one. Ordinary work returns a dormant pool to its baseline of two.
- `set_target_ready(n)` permits host-managed memory-pressure reductions or reviewed capacity adjustments; it cannot exceed 1–4 and does not grant task or plugin authority.
- Rejected/failed warmup processes **retain their global reservation until actually reaped**, closing a transient oversubscription race.
- All admitted warm workers remain **single-use** and are replaced asynchronously. Previous P2 batching and the original disposable worker fallback stay intact.

## Completed Linux verification

| Gate | Result |
|---|---:|
| Original P4 pool + new P5 adaptive suite | **37/37** |
| Previous P2/P3 + HDC/KAN/SSM + calculator and core sample | **132/132, plus 214 subtests** |
| Total selected nonoverlapping tests | **169 passing tests, 214 subtests** |
| Bytecode compilation of changed modules | Pass |
| Build `cognitum-core` wheel; fresh isolated-prefix import; no eager spawn | Pass |
| Verified ZIP payload SHA-256 checks | **12/12** |
| Windows physical install, complete current-repo test suite and OS containment | **OPEN** |

The first broad regression attempt had a fixture import error from missing `PYTHONPATH=.:tests`; after supplying the historical test layout, the recorded suite passed. This was not a source regression.

## Measured Linux performance — fixed capacity

Two trials per configuration, 400 ms synthetic work per operation, no AI model time. **Adaptive scaling off for these controlled fixed-capacity comparisons.** Figures are median total wall-clock time for the batch.

| Prepared standbys | Four concurrent | Eight concurrent | Approximate summed idle RSS |
|---|---:|---:|---:|
| 0 (all cold) | 1,210 ms | 1,799 ms | 0 |
| 1 | 1,187 ms | 1,954 ms | 94 MiB |
| **2 (default)** | **1,122 ms** | **1,873 ms** | **189 MiB** |
| 4 | 415 ms | 1,570 ms | 378 MiB |

Two standbys are a memory/performance compromise, **not universally faster under large bursts**: at eight concurrent requests they were slightly slower than all-cold in this small sample. Summed RSS double-counts some shared pages.

## Measured adaptive behavior

The same default-two pool processed three successive bursts of four synthetic 400 ms operations, allowing replacement to reach the target before the next timed burst.

| Burst | Target before → after | Total wall time | Warm vs cold |
|---|---|---:|---|
| 1 | 2 → 4 | 1,217 ms | 2 warm / 2 cold |
| 2 | 4 → 4 | 408 ms | 4 warm / 0 cold |
| 3 | 4 → 4 | 411 ms | 4 warm / 0 cold |

Global warm reservation after shutdown was **zero**, and peak was **four**. Interpreter prewarm/replacement happens outside the timed request; it has not become free.

## Next production-hardening gates

1. Attach the trusted-host periodic `maintain()` lifecycle and memory-pressure inputs. No implicit background poller is installed by this patch.
2. Implement and verify a **cross-specialist cold-fallback budget**; current cold concurrency bounds are local to each pool.
3. Provide OS process isolation: Linux supervisor/namespace/cgroup strategy, Windows restricted-token/Job Object process-tree containment. `multiprocessing.spawn` **does not provide an OS sandbox**.
4. Long-running mixed-workload p95/p99, RSS/PSS, CPU/energy, crash/restart/timeout stress with actual HDC/KAN/SSM imports and real LLM requests.
5. Test one exact canonical complete repository SHA and an installed Windows Cognitum distribution. No claim of production readiness.

The full patch, exact source snapshots, both benchmark JSON datasets, 169-test logs and SHA256SUMS are in the companion `Cognitum_Component_Quality_P5_Two_Default_Adaptive_2026-11-01.zip` archive.

**Decision:** 2 default / 1 minimum / 4 maximum accepted as the next **candidate** policy. Cognitum remains one product; Lu is untouched.
