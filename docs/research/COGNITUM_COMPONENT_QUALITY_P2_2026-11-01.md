# Cognitum P2 — Cross-component worker batching and research-process safety

**Date:** 2026-11-01  
**Branch target:** `cognitum/component-quality-p2-20261101` on P1 unified Cognitum  
**Status:** engineering prototype validated locally; **not production-promoted**.  
**Product boundary:** ONE Cognitum distribution, with HDC/KAN/SSM included; **NO Lu changes or Cognitum-to-Lu integration**.

## Engineering decision

The P1 profile located the dominant latency: creating a fresh Python interpreter for every small operation. Removing workers or granting ambient file/network authority would be wrong. P2 introduces **opt-in, bounded, same-context batching**, preserving the normal single-request API and no persistent worker across separate tasks.

## Changes implemented

**A. Generic Cognitum runtime (additive API):** `Runtime.call_batch(...)` validates and authorizes every input BEFORE launching one disposable `multiprocessing.spawn` worker. It accepts 1–16 requests with identical correlation, workspace, subject, operation and timeout. Only deterministic, effect-free, trusted plugins are eligible. It freezes mutable payload dictionaries before launching the child, instantiates a fresh plugin object per operation, applies one group deadline, validates every result, and returns no partial data on any failure. Batch use requires a trusted in-process `trusted_batch_opt_in=True` parameter; this is **not an authentication mechanism**. Neither `Runtime.call` nor `worker.execute` changed.

**B. Standalone C14 G25 research process (separate adapter, same Cognitum repo):** `TaskBatch` submits 1–16 research reports from ONE trusted task into one pinned research worker and reaps the worker and POSIX descendants after completion. Cancellation, deadline, duplicate IDs, forgery, scientific refusal and full-batch failure are tested. The host's G25I estimator/guard stays byte-identical. It uses nonblocking `selectors` I/O and caps its own stdout buffer to `batch_size × 65,536` bytes; no unbounded `communicate()` buffering. **POSIX-only**; rejects Windows rather than inventing equivalent containment.

**Important limit:** These are optional Python research/trusted-code workers, **not an OS sandbox**. Generic `multiprocessing` worker termination does not attest killing arbitrary subprocess descendants. No signed arbitrary external worker execution, privilege containment, Windows Job Object or Windows installed test is claimed. Security gating is required before production adoption.

## Performance: matched exact-arithmetic calculator benchmark

Linux Python 3.13.5. Three paired trials per group, same input/request schema, separate-worker results checked against the batched results. Warm Python environment and cold process spawns on each group. Numbers below are medians; three trials are **insufficient for a reliable p95**.

| Operations per task | Separate workers | Bounded batch | Speedup |
|---:|---:|---:|---:|
|  1 | 479.0 ms | 481.1 ms | 1.00× |
|  4 | 2,028.6 ms | 503.5 ms | 4.03× |
|  8 | 4,086.2 ms | 527.7 ms | 7.74× |
| 16 | 8,849.6 ms | 545.7 ms | 16.22× |

**Interpretation:** One operation has essentially no advantage. Groups of 4, 8 and 16 amortize Python startup and reduce whole-task wall time. This does not prove lower CPU energy, long-horizon memory, installed Windows performance, LLM task success or that a specific HDC/KAN/SSM task benefits equally.

The research-only G25 benchmark used **one matched trial per group**, not repeated calibration: n=1 1.17×, n=4 3.55×, n=8 8.68×. G25 results are directional only; they may vary with SciPy load/caches.

## Tests

- **17 generic batch tests**: baseline parity, effectful operation refusal, duplicate request IDs, cross-context and forged-scope denial, malformed and dry-run refusal, shared timeout, mutable-dictionary freeze, no partial results.
- **289 cross-domain selected tests PASS**, with **73 unittest subtests**. **One historical test DESELECTED**: its source snapshot references missing `docs/decisions/2026-10-28-C14-G15-real-LLM-gate-deferred.md`, absent from the archived snapshot and GitHub branch; it is an unrelated missing document, not silently counted as a pass.
- **22 independent G25 research batch tests PASS**: 1/2/4/8/16 input parity with separately launched G25 host, legitimate refusal, wrong-science batch failure, worker tampering, duplicate IDs, timeouts, cancellation killing POSIX descendants, stdout overproduction, no automatic causal certification.
- **45 unchanged G25 guard/host tests PASS**; **23 unchanged original cancellation tests PASS**. These are independent from the newly added batch suite.
- **Clean ZIP overlay** independently applied to untouched reconstructed source: **32 core tests + 182 subtests** and **22 G25 batch tests PASS**, with all payload hashes verified.
- **69 P1 HDC/KAN/SSM specialist tests** passed again in the intact P1 candidate (SSM state resume and KAN spline endpoint corrections retained).

These suites cover a substantial selected local regression set, not the entire current repository at one canonical SHA. The extra tests do not close HDC/KAN efficacy, signed checkpoint provenance, C14 statistics, OS sandbox or Windows installation.

## Readiness decisions

| Gate | Result | Qualification |
|---|---|---|
| Generic effect-free batched execution | **PASS (experimental)** | New opt-in; default `call` unchanged |
| Exact result parity and no partial output | **PASS** | Calculator and G25 black-box comparisons |
| POSIX G25 batch cancel, descendant cleanup, output cap | **PASS (research)** | No OS sandbox claim |
| Measured whole-task speed | **PASS for fixed bench** | Three samples per general case; directional, no p95 claim |
| Fresh package overlay and replay | **PASS** | 32 core + 22 G25 batch cases on extracted source |
| Full current GitHub branch checkout and all tests | **OPEN** | Historical+selected overlay test environment |
| HDC C08 revocation/P3 and KAN C09 checkpoint/P3 | **OPEN** | Must reconcile earlier source with current branch |
| Signed hostile-worker OS containment / Windows Job Object | **OPEN** | Prevent production default enablement |
| Production release and automated model specialist routing | **NOT APPROVED** | More integration, policy and utility data required |

## Next optimization targets

1. Install and test a **single Cognitum wheel from a canonical current source SHA** on clean Linux and Windows; execute full repository regression and reference data checks.
2. Rebase and independently attack-test C08 durable index invalidation and C09 trusted checkpoint revocation onto unified source. Explicitly measure HDC retrieval quality and KAN model prediction error against matched baselines, not only microseconds.
3. Convert the batch prototype to a real OS-isolated worker host with per-task authorization, resource quotas, enforced descendant kill, durable cancellation and restart. Only then consider default runtime enablement.
4. Profile p50/p95/RSS, CPU/GPU cost, and saturation on long runs across C05-C17. Test user tasks and model WITH/WITHOUT Cognitum separately from kernel accuracy.

**Source integrity:** P2 was applied to locally reconstructed `cognitum/runtime.py` and `cognitum/worker.py`, whose **initial Git blob hashes exactly matched** the P1 Cognitum GitHub branch. HDC/KAN/SSM P1 source and its guard remained unchanged. GitHub is an archival repository, not the development or acceptance host.
