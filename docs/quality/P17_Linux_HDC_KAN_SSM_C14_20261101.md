# Cognitum P17 — Linux production-gate review and component quality

**Engineering checkpoint:** November 1, 2026 (America/Phoenix); execution logged November 2 UTC.  
**Baseline:** P13/P14/P16 Linux-only local source package.  
**Disposition:** COMPONENT QUALITY PASS in tested scope; kernel production gate BLOCKED; **NOT PRODUCTION CERTIFIED**.  
**Separation:** No Lu changes. P15 and **all Cognitum Windows-specific work remain deferred**.

## 1. Production gate (P13/P14)

The current host reports `/sys/fs/cgroup` as **read-only cgroup2** and `inspect_delegation('/sys/fs/cgroup')` returns `ready_for_live_tests: false`, `kernel_enforcement_tested: false`, `CGROUP2_MOUNT_READ_ONLY`. No trusted writable subtree was available.

The local P13 and P14 checks were rerun successfully (11 passed, four live P12/P13 tests skipped). This **does not** prove kernel `memory.max`, `pids.max`, OOM, `cgroup.kill`, or simultaneous host/guardian/reconciler recovery. Installing the example systemd unit also remains pending. Do not weaken P12 fail-closed admission or simulate a writable cgroup as production acceptance.

**Required external-host completion:** provision a non-root delegated writable cgroup v2 subtree with memory and pids controllers enabled; run P12/P13 live suite, explicit OOM/PID exhaustion and descendant teardown, actual systemd-supervised P14 restart and full host/guardian/reconciler crash matrix, then a required-kernel P16 long soak. Same-UID cooperative admission remains less than a multi-user machine-wide authority guarantee.

## 2. HDC optimization

`cognitum/research/hdc_optional.py` now locally caches domain-separated SHA-256 role and entity atoms **per request**. No global unbounded cache, no change to IDs, protobuf contract, snapshot checking, top-k or authorization behavior. Tested 200 randomized 32-record requests against an independently computed Hamming reference, plus ties, invalid terms, and duplicate refusal.

Controlled ABBA test (8 alternated repetitions, 2,500 calls each): **0.123645 ms** before, **0.087856 ms** after, **1.407× faster** for the repeated-role workload. Not a general workload speed guarantee.

## 3. SSM optimization

`cognitum/specialists/ssm.py` adds a bounded 1-state/1-input/1-output scalar path. It preserves `math.fsum`, request shape checks, state limits, overflow denial, output fields and numerical recurrence. Multidimensional code remains unchanged. Tested 200 independent random references, chunked 32+32 continuation, strict overflow/input denial, and a multidimensional reference.

Controlled ABBA, 64-step sequences: scalar **0.174082 ms** before, **0.064198 ms** after (**2.712×**); 8-state **1.578040 ms** before, **1.530982 ms** after (about **1.031×**, not meaningful). These exclude sandbox launch and model inference.

## 4. KAN profiling and security gate

Pinned checkpoint, exact hash matching, research opt-in, no-pickle NumPy decode, out-of-distribution refusal and malicious ZIP path denial were tested. **No persistent model cache was enabled**; P8/P11 worker policy uses disposable one-request sandboxes.

For a small 1.3-KiB reference checkpoint, full pinned prediction averaged **0.514537 ms**, decode alone **0.402378 ms**, while a prepared model tensor call was **0.017481 ms**. This is a bottleneck diagnosis, **not** a legitimate 29× operational speedup: a cache across one-shot worker processes would alter lifecycle and authorization assumptions. Further work should measure an approved per-worker multi-query design or reduce verified decode cost without relaxing checks. KAN training/model-quality acceptance and unavailable upstream artifact fixture remain open.

## 5. C14 causal interval diagnostics (research-only)

Added `cognitum/research/causal_variance_diagnostics_p17.py` as an **unregistered research module**, not an estimator replacement or host-authorized causal result. For binary observed W/T/Y strata and explicitly *unverified* iid/ignorability assumptions, it computes:

- Conditional plug-in variance of standardized arm risks.
- Added random-covariate mixture variance `sum_w q_w (delta_w - ATE)^2 / n`.
- Research-only normal intervals; exact binary input validation, min-arm checks, and **refusal** of no-event or all-event cells.

Independent synthetic Monte Carlo, **800 attempted datasets per family** (n=400), with known generator truth:

| Synthetic family | Accepted/attempted | Conditional interval coverage among accepted | Mix-adjusted coverage among accepted |
|---|---:|---:|---:|
| Effect reversal | 800/800 | 76.75% | 94.62% |
| Moderate heterogeneity | 800/800 | 88.38% | 94.00% |
| Rare binary outcomes | **153/800** | 96.08% | 96.08% |

**647/800 rare-outcome draws refused.** Conditional-on-acceptance coverage is selected and cannot justify 95% unconditional CI claims. These tests exercise synthetic randomized observed-confounder mechanisms, **not** hidden confounding, partial identification or a globally valid causal interval.

A review of the already-recorded G25N research gate also confirms **NO GO** for production: its DKW method failed 12/12 width acceptance cells despite validity positives, and global exact likelihood-ratio confidence-region inversion is unfinished. P17 does not supersede that result. Next causal scientific task is globally invertible calibrated inference with mathematically outward-certified numerical projection, new preregistered holdouts and explicit refusal accounting—**not silent promotion of mix-adjusted Wald**.

## 6. Tests and reproducibility

The inherited and P17 tests passed when isolated into three groups:

- P8/P9: **27 passed, 1 intentionally deselected** (upstream KAN fixture missing).
- P11/P12: **23 passed, 2 live-kernel tests skipped**.
- P13/P14/P16 + P17 quality: **31 passed, 2 live-kernel tests skipped**.

**Combined segregated accounting: 81 passed, 4 skipped, 1 deselected.** An earlier all-in-one command stalled at 33 completed tests and was terminated; this unresolved orchestration/lifecycle nondeterminism is **not** counted as a pass. Post-termination process check found no lingering Cognitum worker processes; the longstanding shared admission directories remained.

An isolated development-wheel installation executed scalar SSM, HDC and the research variance diagnostic successfully. The P17 source patch applied cleanly to exact local P16 source and all five patched/new files matched byte-for-byte. Wheel RECORD hashes were recalculated; no production version or Lu source was changed.

Reproduce from archive root:

```bash
PYTHONPATH=. pytest -q tests/test_component_quality_p17.py tests/test_causal_variance_p17.py
PYTHONPATH=. python run_quality_evidence.py
# Linux gate groups separately to avoid orchestration stall:
PYTHONPATH=. pytest -q tests/test_sandbox_warm_p8.py tests/test_contained_warm_p9.py -k 'not test_kan_warm_execution_requires_trusted_hash_and_matches_p7_cold'
PYTHONPATH=. pytest -q tests/test_warm_guardian_p11.py tests/test_cgroup_p12.py tests/test_durable_admission_p12.py tests/test_cgroup_p12_live.py
PYTHONPATH=. pytest -q tests/test_cgroup_p13_readiness.py tests/test_cgroup_p13_live.py tests/test_recovery_watchkeeper_p14.py tests/test_guardian_pidfd_p16.py
```

## 7. Remaining gates and disposition

1. **P13** real kernel-backed memory/PID/OOM/descendant containment on an approved writable cgroup delegation.
2. **P14** independently deployed and OS-supervised actual simultaneous crash/restart recovery, beyond subprocess simulation.
3. **P16** required-kernel load/pressure soak and root-cause of monolithic-suite stall; performance monitoring across hardware.
4. **HDC/KAN/SSM** larger models, end-to-end host workloads, KAN checkpoint decode optimization compatible with disposable workers, formal security boundary review.
5. **C14** scientifically valid, sharp and calibrated partial-identification inference on fresh holdouts before any production estimator replacement.
6. **Windows P15 and every Cognitum Windows-specific task** remain **DEFERRED** until explicit user reversal. No Lu changes.

**Decision:** keep all new algorithms/paths in experimental Linux development scope; the HDC and SSM source optimizations can be proposed for future integration only after broader acceptance. Do not claim a production-ready Cognitum release.
