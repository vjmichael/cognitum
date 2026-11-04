# Cognitum C14 — CH40-M.5F verified FLINT Gram-kernel supplement

**Executed 2026-11-03 (America/Phoenix). Research-only. Scientific C14 release NO-GO.**

## Why this gate exists

CH40 already uses an upper bound on the Fisher-information determinant obtained from the **positive-semidefinite Fisher Gram matrix**, rather than simply relying on Hadamard diagonal products. In this CH40-M.5F supplement we **do not claim new mathematics**. We implement a fast FLINT/Arb path for this same verified bound and measure both arithmetic cost and quality on the original CH23 data. The CH40-J signed evidence is **not modified**.

## Algorithm and proof scope

For original three-parameter logistic rows, `eta_i(b) = x_i dot b` is linear over a rational rectangular box. Compute exact rational `eta_i` extrema by signs of `x_i`, without feeding a wide interval to Arb. Let `u_i >= sup_{b in box} p_i(1-p_i)`, with `p_i=logistic(eta_i)`. The maximum weight occurs at zero, if present, otherwise at the endpoint closest to zero, and the Arb endpoint upper is exact-dyadic extracted. Then

`I(b) = sum_i n_i p_i(1-p_i) x_i x_i^T <= G = sum_i n_i u_i x_i x_i^T` (PSD/Loewner), so `det I(b) <= det G` for positive-definite matrices. The 3x3 Gram matrix and its determinant are **exact rational**; FLINT supplies an outward logarithm upper. The binomial likelihood upper is rowwise monotonic for `s=0,n` or global binomial entropy for `0<s<n`. No expansion of an interval determinant or numerical Hessian is required.

The independent checker re-derives row linear extrema, weight bounds and likelihood with the **separate CH40-J rational/Decimal implementation**. It rounds each row's positive weight bound **upward** to 85 decimal places before forming an exact rational Gram, so its denominator size is bounded. It refuses a native claim whose rowwise upper weights or total upper fall below those independent ceilings. A result without this replay is **unverified diagnostic-only**.

FLINT `arb` uses a low-precision radius field. When a broad box is constructed as a wide ball, radius rounding can create extra overestimation even with a high-precision midpoint. Exact rational endpoint optimization avoids that without weakening outward rigor. See official FLINT docs on midpoint/radius ball arithmetic.

## Actual results

- All 15 original CH23/CH40-K hash-pinned certificates loaded without substitution.
- **15/15** highest-cap frozen terminal boxes independently verified using distinct arithmetic (FLINT 192 bits versus rational/Decimal 95-digit checker).
- **960/960** original terminal boxes evaluated natively. Remaining **945 are not independently replayed** under this gate.
- All 15 highest-cap Gram log-determinant bounds tighten their corresponding pure Hadamard-only bound (magnitude shown individually in JSON).
- The original CH40 producer **already exploited Gram**. **0/15** highest-cap cases and **0/960** all-leaf native diagnostics improve their historical node cap materially (threshold 1e-7). Therefore **do not alter certified frontier or global objective gap**.
- Paired CPU time on the highest-cap boxes only: native **0.171813 s** vs separate independently checked rational/Decimal **1.421828 s**, a **8.2754x kernel comparison**, excluding file I/O, solver search, and signature verification. This is **not** a whole-solver speedup claim, and measures two arithmetic implementations that use different numeric precisions.
- Local **13/13** focused tests passed, including rank-deficient model refusal, tampered-weight refusal, original-trace pins and all 15 independent comparisons.

## Reproduce with the immutable original fixtures

Requires Python 3.13 (or supported compatible build), python-flint 0.9.0, the external original `CH40K/traces` and `CH40K_ACCEPTANCE.json`, and the **independent** original `rational_kernel40d.py` under `CH40J/source`. No original data are embedded in this source package.

From `research/ch40m5-flint-gram`:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=/path/to/flint-site python run_m5.py \
  --traces /path/CH40K/traces \
  --pins /path/CH40K/CH40K_ACCEPTANCE.json \
  --checker-dir /path/CH40J/source \
  --all-leaves --output /tmp/CH40M5_ALL15_FRONTIER_REPORT.json
CH40M_TRACES=/path/CH40K/traces CH40M_PINS=/path/CH40K/CH40K_ACCEPTANCE.json \
CH40M_CHECKER=/path/CH40J/source PYTHONPATH=/path/to/flint-site \
  python -m unittest discover -s . -p 'test_m5.py' -v
```

The tests skip native tests when `python-flint` is not installed, and skip original-case tests when immutable fixtures are absent. **A skipped CI job is not a scientific acceptance.** `ctx.prec` is restored after each call; run these experimental kernels in serial / isolated workers because global context mutation is not approved for concurrent production calls.

## Decision and next gate

**ADOPT AS A RESEARCH CANDIDATE** for replacing slower generic rational/Decimal *producer* arithmetic, while always retaining the independent checker and the original coupled/likelihood bound-selection logic. CH40-M.5F does **not** retire the checker, establish equivalent whole-solver performance, independently verify every leaf, close the 0.05 finite-root gap, validate a causal claim, enable a Lu tool, or modify historical signed evidence.

Next: integrate FLINT kernel as an opt-in adapter to **existing** certified search, pair full per-node independent witness production with native speed, then compare identical frontiers and matched process CPU+RAM against the current MPFR path. If this does not improve end-to-end search, keep it research-only.
