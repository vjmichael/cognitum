# Cognitum P4 — At most four prewarmed Python workers

**Date:** 2026-11-01  
**Scope:** Single Cognitum distribution, optional standalone runtime optimization. No Lu integration or modifications.  
**Decision:** Research engineering candidate; NOT automatically enabled in production, NOT a security sandbox.

## User-selected architecture

- Global hard maximum **4 warm-origin workers** across all P4 specialist pools, counting **starting + idle + executing**, not four per component.
- **Default 1 standby**, configurable `target_ready` from 1 through 4. The host may explicitly use 4 when throughput and memory budget justify it.
- Every prewarmed worker executes **one** trusted, deterministic, effect-free request, exits and is reaped. Replenishment is asynchronous; a fifth simultaneous request **starts cold immediately**, without waiting for a warm slot.
- Cold execution is the existing P2 disposable-worker API. Cold fallback concurrency has an independent **per-pool** limit (8 by default, 1–32 permitted); overload fails closed, rather than launching unlimited workers. A global *cold* process budget across several pools is a future production-hardening requirement.
- A shared process-wide warm reservation budget prevents HDC/KAN/SSM pools from each claiming four workers. Each component's standby also requires explicit trusted `start()`; the pool is OFF by default and the original runtime is unchanged.
- Initialization/ready handshake is out of the request clock. The standby has no user request until the Cognitum runtime has completed request validation and policy authorization.
- Bounded (64 KiB) JSON messages for the new warm path; no arbitrary pickle responses. The host still validates scientific/plugin result schemas. Failures, protocol mismatch and cancellation return no late result.

## Acceptance test results

| Test slice | Result | Notes |
|---|---:|---|
| New P4 four-worker and global-cap tests | **22 passed** | Includes four warm/one cold, 12-call burst, global cap across two pools, simultaneous starts, timeout, shutdown, cold-overload denial, TTL reap |
| Existing P3 warm worker + SSM/KAN/HDC specialist tests | **69 passed** | Unchanged previous implementation and numerical boundary tests |
| P2 batch + Cognitum core reference tests | **42 passed, 4 subtests** | Existing single-call and batch paths |
| **Total distinct selected pytest tests** | **133 passed + 4 subtests** | Executed in separate bounded commands, not a single all-targets run |

A combined long-running pytest invocation exceeded the tool's execution limit, so only completed component groups are counted. No full canonical source, installed Windows or real LLM test is claimed.

## Measured matched burst benchmark (Linux development host)

Each request invokes a trusted exact-schema `slow.wait` plugin which sleeps 400 ms. **Three repeated bursts** of four and eight simultaneous requests per condition; medians are full group wall-clock time. Startup/prewarm is measured separately, with each group beginning after requested standby readiness.

| Condition | 4 operations | 8 operations | Initial warmup | Sum of idle process RSS |
|---|---:|---:|---:|---:|
| All disposable/cold | **1,110 ms** | **1,782 ms** | none | none |
| One standby | **1,071 ms** | **1,822 ms** | 503 ms | 94.5 MiB |
| Four standbys | **415 ms** | **1,345 ms** | 703 ms | 378.0 MiB |

Four ready workers improve the four-request burst by **2.68×**, and the eight-request burst by **1.32×**. With eight operations, four run warm and four fall back cold in each repeat, producing 24 warm hits and 12 cold fallbacks across the (4+8) × 3 combined trial cases. A one-standby pool gives little advantage on synchronized bursts. Warm startup still costs CPU and memory outside request latency. Sum RSS counts shared pages more than once; it is not physical incremental memory. Numbers are descriptive, not stable p95/p99 or real-model workload statistics.

## Reliability and readiness constraints

1. **Not OS isolated:** Python `multiprocessing.spawn` inherits the user context, and terminating its direct PID does not prove descendant containment. Do not prewarm untrusted code. Windows restricted identities/Job Object, Linux isolation/descendant cleanup and process memory/CPU limits remain open.
2. **Standby strategy:** One worker default to save RAM; 4 is a **ceiling**, not an always-on requirement. Across multiple optional providers, the shared budget is currently first-come-first-served. Rebalance/adaptive scheduling and automated refill on a competing provider's release remain future work.
3. **Per-pool cold overload:** Cold overflow cap prevents unbounded fallback *within one pool*. A process-wide cold budget and adaptive queues are not yet implemented; don't call this globally admission-controlled.
4. **Test limitations:** No installed Windows acceptance, system-level stress/leak/fuzzing, real Cognitum HDC/KAN/SSM mixed-use load, LLM-with/without benefit, long-run restart or p99 metrics. Default runtime and older P3 single-use API unchanged.
5. **Engineering decision:** Keep this opt-in P4 candidate, using one pool for the most likely provider or a shared four-slot budget for multiple providers, before any production enablement.

## Reproduction

1. Start with the Cognitum P3 source of `cognitum/component-quality-p3-warm-standby-20261101`.
2. Overlay the three added files under `source_overlay/` into that same checkout; do not make a second Cognitum installation.
3. From repository root run `PYTHONPATH=.:tests python -m pytest -q tests/test_warm_pool_p4.py`.
4. Run `PYTHONPATH=.:tests python tools/benchmark_warm_pool_p4.py`; Python 3.11+ with the same dependencies and Linux /proc for RSS measurement.
5. Run the unchanged P3/P2/HDC/KAN/SSM test slices in the accompanying logs.

**Provenance:** The benchmark JSON, test outputs, source snapshots, source checksums and clean-extraction receipt are included in the companion source/evidence ZIP. GitHub is the source and milestone repository, not the build hub.
