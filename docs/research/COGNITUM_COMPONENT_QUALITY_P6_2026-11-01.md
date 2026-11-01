# Cognitum P6 — Trusted idle maintenance and global cold-worker budget

**Date:** November 1, 2026  
**Status:** validated nonproduction engineering optimization; not production promotion.  
**Branch:** `cognitum/component-quality-p6-trusted-maintenance-cold-budget-20261101`  
**Parent:** `cognitum/component-quality-p5-adaptive-two-standby-20261101`  
**Scope:** Independent Cognitum product (HDC/KAN/SSM included); **no Lu changes**.

## What changed

1. **Host-owned idle maintenance:** `cognitum.warm_host.TrustedWarmMaintenance` starts preapproved warm pools and runs the existing `pool.maintain()` policy on a small explicit maintenance thread. The host owns its start/close lifecycle, provides snapshots, records maintenance failures and terminates/reaps the pools on close. Nothing starts automatically from a library import or a model request. The default remains **2 warm standbys, minimum 1, maximum 4 process-wide**.
2. **Shared cold admission budget:** `cognitum.worker_budget` adds an atomic process-local 8-worker ceiling across ordinary `worker.execute`, P2 `execute_batch` and all P4/P5 pool cold fallbacks. Over-capacity tasks are rejected promptly instead of queuing or launching further Python processes; reservations remain until child cleanup completes. The existing per-pool cold cap still applies. This is **8 possible cold workers IN ADDITION TO up to 4 reserved warm workers**, not an 8-process system-wide maximum; separate hosts need their own quota manager.
3. **Stable public contracts:** internal `overloaded` maps to existing public `execution_status='error'` plus sanitized `worker_capacity_exhausted`; trace, typed-result and inert wire code catalogs were extended accordingly. No scientific result is returned after an overload.
4. **Explicit negatives and diagnostics:** unit tests cover duplicate/invalid pools and tick interval, no unwanted auto-start, idle shrink/restoration, cross-pool warm cap, all cold entrypoints sharing one budget, timeout releases, underflow, and real 10-simultaneous spawned cold calls (8 admitted / 2 rejected).

## Local acceptance results

- New P6 tests: **18 passed** (one real spawned 10-request stress).
- Existing P5 adaptive pool: **15 passed**.
- Existing P4 pool: **22 passed**.
- P2/P3 worker, trace, typed result and wire regression: **84 passed + 95 unittest subtests**.
- HDC/KAN/SSM and selected scientific runtime regression: **58 passed + 4 subtests**.
- Selected total: **197 passing pytest tests plus 99 subtests**. Tests ran in separate completed groups; no incomplete group counted.
- `python -m compileall`: pass; 
- Full unified source wheel: built `cognitum_core-0.1.0-py3-none-any.whl` (single distribution, not a new product).

## Developer-host matched latency

| Condition | Tool-request median (not LLM prompt) |
| --- | ---: |
| Cold disposable worker, n=5 | **511.929 ms** |
| P5 manual maintenance, 2 ready, n=8 | **4.811 ms** |
| P6 trusted maintenance, 2 ready, n=8 | **5.795 ms** |

P6 recorded 39 maintenance ticks during the eight ready-warm calls and zero warm misses. The approximate 1 ms difference is **not significant evidence of slowdown** at these sample sizes. Initial prewarm takes approximately 0.5 seconds and remains outside the already-ready request clock. The benchmark did not include an LLM, real HDC/KAN/SSM task selection, or Windows execution.

## Security/quality boundaries

- **Trusted deterministic and effect-free plugins only.** Neither `multiprocessing.spawn` nor the capacity budget is an OS sandbox; workers inherit ordinary host-user privileges. No untrusted extension execution enabled.
- The global cold budget is **per host process**, not across separate applications or remote nodes, and direct external processes outside Cognitum remain untracked.
- The Python disposable worker does **not guarantee descendant-tree termination**. Linux cgroup/namespace and Windows restricted token + Job Object enforcement require independent implementation and acceptance.
- The warm manager requires explicit host construction; it is **not wired into the default user CLI** or claimed as an installed production background service.
- No HDC/KAN/SSM scientific effectiveness claims, statistical calibration changes or production release claims were introduced.
- Full latest canonical repository tests and physical Windows acceptance are not established by this local reconstructed-source benchmark.

## Next P7 gates

1. Integrate trusted host resource telemetry and a measured CPU/memory-based 1–4 standby controller; avoid pool oscillation and apply per-provider quotas within process-wide max4.
2. Replace the generic worker's weak process-termination semantics with independently tested descendant-tree containment, restricted identity, and broker-only I/O on both Linux and Windows.
3. Run mixed HDC/KAN/SSM and causal/math workloads with p50/p95/p99, memory (prefer PSS), queue/refusal counts, worker cold startup, and real transformer WITH/WITHOUT Cognitum comparisons.
4. Qualify one complete canonical Cognitum source SHA and clean installed Windows distribution; retain the single Cognitum product.

**Release decision:** P6 design passes the stated local engineering subset. Production default remains gated on OS isolation, lifecycle containment and installed acceptance.
