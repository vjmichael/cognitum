# Cognitum P3 — prewarmed single-use worker performance experiment

**Date:** 2026-11-01. **Status:** engineering candidate, **not a production release**.

**Project boundary:** one Cognitum distribution, including HDC/KAN/SSM; Cognitum is separate from Lu. This branch is based on `cognitum/component-quality-p2-20261101`, not a new package.

## Why

Cognitum's P2 worker launched a new Python interpreter for each trusted operation. For small calculations, interpreter startup and module imports dominate the requested computation. The P3 opt-in `WarmSingleUsePool` starts **one trusted, deterministic, effect-free plugin worker** during host initialization, waits for an explicit readiness handshake, and gives it **one request only**. The parent retains schema validation, policy authorization, response validation and tracing. That worker exits and a replacement prewarms in the background. If no ready worker is available, the unchanged disposable-worker path handles the request.

**No user task data enters a worker before request authorization; warmup itself is not an authority grant.** The pool refuses factories with effectful/nondeterministic operations. Caller payloads are snapshotted before dispatch. Shutdown/cancellation and worker error/timeout paths fail closed in the tested cases.

## Linux benchmark (one run, eight matched exact-arithmetic calls per class)

| Measurement | Result |
|---|---:|
| Cold worker median `Runtime.call` | 500.262 ms |
| Already-ready worker median `Runtime.call` | 5.262 ms |
| Conditional request speedup | **95.06x** |
| Initial Python prewarm time (outside request) | 504.430 ms |
| Standby replenishment wait | typically ~475–563 ms |
| One idle worker RSS (Linux /proc observation) | 96,392 KiB (~94 MiB) |
| Warm hits / cold misses in 16 standby-path calls including burst | 11 / 5 |

**Interpretation:** prewarming **moves** interpreter/import cost away from a *ready* request; it does not make startup free. Under rapid bursts, one standby is exhausted and misses fall back to cold workers. These are developer-host measurements, not real LLM end-to-end, installed Windows or production p95/p99 results. P2 same-context batching remains useful for bursts.

## Tests and source

- Local targeted regression: **141 passing pytest tests plus 186 unittest subtests**, with the prior P2 batching, calculator, trace, unified HDC/KAN/SSM, KAN endpoint and SSM resume suites.
- Additional P3 worker tests verify first-hit success, no prior-task worker reuse, validation before dispatch, rejected operations/effectful factory, shutdown/timeout fail-closed behavior, concurrent use, safe cold fallback and mutable payload snapshotting.
- `cognitum/warm_worker.py` and `cognitum/runtime.py` are the code changes. `tests/test_warm_worker_p3.py` and `tests/test_warm_worker_edge_p3.py` provide acceptance; `tools/benchmark_warm_worker_p3.py` reproduces timing.
- GitHub source blobs of the five code/test/benchmark files were compared with the exact local Git blobs.

## Timing definitions

The overall model-clock begins when the model host receives a prompt. Cognitum tool latency begins later, when the host invokes a validated Cognitum operation. Track independently: model prefill/decision, tool dispatch, warmup if any, worker computation, response validation, model continuation, and final answer. These local benchmarks include **no LLM prompt or model generation**.

## Unresolved release gates

1. **OS sandbox:** generic Python multiprocessing workers still inherit ordinary host user permissions; worker kill cannot prove descendant containment. Windows Job Object/restricted token and Linux cgroup/namespace enforcement remain necessary. No untrusted plugin prewarming.
2. **Idle reliability:** crash/TTL background health watcher, adaptive minimum warm count and memory/CPU budgets are not yet implemented. Do not preload every optional component.
3. **Portability:** Windows clean installation, subprocess lifecycle, and restarts are unverified.
4. **Performance proof:** mixed-operation runs with p95/p99, energy, memory footprints for heavier KAN/SSM/HDC dependencies, fairness and real transformer WITH/WITHOUT benchmarks.
5. **Full code qualification:** targeted reconstructed source regression is not a complete current canonical checkout regression.

**Release decision:** preserve as opt-in research optimization, NOT enabled in Cognitum's default runtime. Lu remains untouched.
