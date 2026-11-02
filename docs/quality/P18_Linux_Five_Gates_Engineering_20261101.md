# Cognitum P18 — Five Linux Production/Component Gates

**Engineering date:** 2026-11-01 America/Phoenix (execution 2026-11-02 UTC)  
**Baseline:** P17 Linux-only component quality snapshot.  
**Product boundary:** Cognitum only. Lu unchanged. **ALL Windows-specific work and P15 deferred.**  
**Disposition:** Partial engineering advancement; **NOT production-certified**. Do not conflate test skips with passes.

## Gate 1: P13 real kernel containment — BLOCKED, test harness expanded

- The actual `/sys/fs/cgroup` cgroup-v2 mount is `ro` in this container. A trusted writable delegation is absent. `memory` and `pids` controllers exist but cannot be assigned to Cognitum here.
- New **opt-in real kernel tests** `tests/test_p18_kernel_pressure_live.py`: 64 MiB `memory.max` with a blocked-at-gate child subsequently attempting 128 MiB, requiring kernel `memory.events` `oom_kill >= 1`; and `pids.max=4` with a blocked-at-gate child attempting 10 forks, requiring a real `EAGAIN` and `pids.events max` event. Scope teardown must call `cgroup.kill`, prove unpopulated, and remove exact scope.
- **2/2 P18 pressure tests skipped, not passed.** Two P12 and two P13 live tests also skipped. No OOM, PID ceiling, or kernel descendant-kill certification.
- Live tests require an *exclusive*, administrator-delegated, writable **non-root** cgroup-v2 subtree with `memory` and `pids` enabled. Never run these against the mount root or a shared application cgroup.

## Gate 2: P14 independent host-death recovery — improved, live deployment OPEN

- Hardened `DurableWarmAdmission.reconcile_once` to demand exact `cognitum-isolate-<nonce>` root **before touching the corresponding cgroup**. Prior check only required a path prefix; a same-UID forged active marker could target an unrelated sandbox root.
- Two new negative tests confirm wrong-root markers remain poisoned without kernel calls and missing kernel scope remains blocked. Focused P14/P12 tests: **14/14 passed** (7 P14, 5 P12, 2 new).
- Wrote `deploy/cognitum-p14-watchkeeper@.service.example` as an **uninstalled, operator-review template**; `systemd-analyze verify` produced no diagnostics. Systemd in this container is offline. It is **not** an installed or operating recovery service.
- Actual simultaneous host+guardian crash with external OS-supervised reconciler and writable cgroup still OPEN. Admission stays fail-closed when proof is missing.

## Gate 3: P16 worker reliability — bounded acceptance achieved; monolithic intermittency OPEN

- A 62-pass / 4-skip / 1-deselect monolithic P8-P16 run completed once in 44.17 seconds. Other mixed runs stalled at various worker-suite transitions (including P14→P16), while P14/P16 isolated runs passed. **This is not a deterministic monolithic PASS.**
- P18 introduces a file-backed, process-separated, timeout-bounded Linux acceptance harness to prevent inherited stdout pipes from indefinitely holding up log collection after a test host exits. A timeout remains a failure; the harness does not treat cleanup uncertainty as success.
- Independently executed group logs:
  - P8/P9: **27 passed, 1 upstream KAN fixture deselected**.
  - P11/P12: **23 passed, 2 real-kernel tests skipped**.
  - P13/P14/P16/P17/P18: **50 passed, 4 real-kernel tests skipped**.
  - **Combined segregated accounting: 100 passed, 6 skipped, 1 deselected.**
- Real P7 namespace + P11 guardian integration: **36/36** authorized operations (12 KAN, 12 HDC, 12 SSM), 6.06 seconds, warm budget zero after close. No remaining `cognitum-isolate-*` roots observed after the final run. **Not kernel-required mode.**
- Further repeated monolithic and kernel-required soaks remain OPEN; the intermittent hang was not definitively root-caused.

## Gate 4: HDC, KAN and SSM quality — bounded reference acceptance improved

- **HDC**: 1,200 additional random bounded queries (1–32 candidates, varying role/entity, varying top-k), exact independent Hamming-distance ranking and authorization flags.
- **SSM**: 500 new randomized recurrence comparisons spanning 1–8 state/input/output dimensions and up to 64 time steps, exact output/state agreement, and chunked continuation equivalence.
- **KAN**: replace two-pass `np.load` + `zipfile.ZipFile` with one-pass, bounded per-member NPY parsing; dtype/object denial, preallocation header shape/byte checks, ZIP member/traversal checks and SHA pinning preserved; **no persistent cache** or untrusted checkpoint acceptance.
- Two checkpoint ABBA eight-round timings (400 requests per variant/round, NumPy 2.3.5): one-layer **0.5232 → 0.4397 ms** (1.19×), two-layer **0.8037 → 0.6415 ms** (1.25×). Exact identical prediction bytes in both fixtures; these are **small local microbenchmarks**, not general/model inference performance claims. Forged huge `.npy` shape refused before ndarray allocation.
- 36 real worker requests succeeded with exact trusted KAN pin and approved HDC/SSM operations. Broad model-quality, learned KAN validation and unavailable upstream KAN fixture remain OPEN.

## Gate 5: C14 causal science — new negative research gate, NO production promotion

- Added an unregistered **research-only** iid multinomial nonparametric bootstrap for observed binary W/T/Y strata. No production handler or authorization. Strictly rejects the interval if the P17 base diagnostic refuses or **any bootstrap resample** violates predeclared arm/event guards. No selectively accepted bootstrap reweighting.
- Two separate new synthetic seed cohorts, 4 families, 400 attempted datasets each, n=400, 199 bootstrap replicates: **3,200 attempts**. Across both cohorts:
  - effect reversal: bootstrap **520/800** accepted;
  - moderate heterogeneity: **798/800** accepted;
  - rare outcomes: **0/800** accepted (base diagnostic 173/800);
  - observed imbalance: **511/800** accepted.
  - total bootstrap intervals **1,829/3,200**; **1,371 refusals**, not failures hidden from denominators.
- Conditional coverage of selectively accepted intervals cannot prove unconditional calibration. Some cells undercovered. These results **do not solve** G25N failed width thresholds (12/12), partial identification, hidden confounding, full exact-rank global likelihood-ratio inversion, outward certified global optimization or justified Gamma.
- Scientific decision: **C14 G25 full production inference gate remains NO GO**. The new bootstrap is an exploratory negative/feasibility result only; no production estimator changed.

## Product and packaging

- Rebuilt `cognitum_core-0.1.0-py3-none-any.whl` as a **development-only** wheel from verified P17 contents, replacing P18 KAN, durable recovery and the unregistered causal research module; recalculated and verified every `RECORD` entry. The installed wheel was smoke-tested from `/tmp` outside source tree with existing local dependencies.
- Source and tests were developed/executed locally. Github remains repository and documentation record, not the development hub.
- P18 patch and full tree are bundled with tests, evidence, runbook, and checksums.

## Remaining immutable release conditions

1. Real cgroup-v2 attach, OOM/PID ceiling, `cgroup.kill`, descendant cleanup on properly delegated Linux host.
2. Actual installed OS-supervised P14 restart and simultaneous host/guardian/watchkeeper crash matrix.
3. Repeatable, unflaky combined worker lifecycle test and sustained required-kernel pressure soak.
4. Independent large/real-model KAN quality, HDC/SSM host usage and throughput certification.
5. C14 preregistered independent scientific evidence for valid causal intervals, calibrated width and globally invertible/certified partial-identification procedure.

**No Windows tasks are included; they remain deferred.**
