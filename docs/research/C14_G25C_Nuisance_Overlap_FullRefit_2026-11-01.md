# Cognitum C14 G25C — Nuisance-fit stability, overlap refusals and full-refit bootstrap research

**Date:** 2026-11-01 | **Status: G25C experimental work completed; G25 scientific acceptance FAILED. Production untouched.**

## Executive determination

In six fresh held-out cells totaling **6,000 positive synthetic datasets**, a preselected regularized propensity fit (L2=1 on slopes, no intercept penalty) retained the previous two-fold score estimator, nuisance outcome model and 0.015 positivity threshold. It improved method-specific completion from **5,546/6,000 (92.43%)** to **5,614/6,000 (93.57%)**, a net 68 recoveries. All 68 are cases refused by the unregularized implementation; none were newly refused by fixed regularization. Nevertheless **all six regularized cells failed the prespecified >=99% completion gate** and a rare-binary n=1,800 interval failed the nominal 95% Wilson-compatibility screen. There is **no production approval.**

Full-pipeline 99-fold pairs bootstrap was attempted on 120 separately seeded datasets per method. Only **18/120 per method** survived the policy that *every* resample must complete. Published coverage among those 18 would be heavily selected and is not valid population-level evidence. The oracle known-nuisance method is for nondeployable numerical context only.

## Research isolation and provenance

- This is an independent Python research implementation based on the G25 A/B package. It is **not a direct regression test of Cognitum production G9**. No Cognitum core source, Lu code or IPC policy was modified.
- Frozen study protocol SHA-256: `632e3d43caaddf5bec1f5e5f99dd266e9283f8249732405eb8887c0102c79cfc`.
- Original imported G25 estimator-source SHA-256: `36fa6d9f8113c9931f3bf1509a780350dfebf56ff20f18601735381750794d73` (same source digest as G25 A/B).
- Separate seed ranges: n=900 `1110000+`, `1120000+`, `1130000+`; n=1,800 `2110000+`, `2120000+`, `2130000+`. Each contains 1,000 cases. Bootstrap uses unrelated 4.1M+ seeds; numerical-library checks use 5.1M+ seeds.
- The protocol contained a known-nuisance oracle comparator that the first version of the 6,000-case runner accidentally omitted. This **post-first-results protocol correction** is recorded in `G25C_Protocol_Deviations.md`. The original receipts and file digests are preserved. The corrected rerun added 6,000 oracle intervals, and **12,000/12,000 original baseline/ridge method receipts remained exactly identical**. The corrected replay is **not an independent cohort** and must not be portrayed as one.
- Original G25 A/B cohort clipping amendment and source limitations are documented in the original G25 research package; this follow-up does not establish blind performance on a genuinely new family of generators.

## Prespecified held-out cells

All point-coverage figures below are **conditional on method completion**, and refusals are never silently removed from attempt denominators. The oracle has privileged access to true nuisance probabilities and must not be promoted.

| n | Scenario | Baseline accepted /1000 | Ridge accepted /1000 | Baseline coverage | Ridge coverage | Oracle coverage | Ridge Wilson 95% for coverage |
|---:|---|---:|---:|---:|---:|---:|---|
| 900 | smooth_gaussian | 897 | 914 | 95.76% | 95.62% | 95.20% | 94.10%–96.77% |
| 900 | rare_binary | 869 | 880 | 94.36% | 94.20% | 94.50% | 92.46%–95.56% |
| 900 | heavy_tail | 863 | 891 | 93.97% | 94.05% | 95.60% | 92.30%–95.42% |
| 1800 | smooth_gaussian | 975 | 978 | 95.18% | 94.99% | 96.10% | 93.44%–96.19% |
| 1800 | rare_binary | 974 | 979 | 93.43% | 93.36% | 94.20% | 91.63%–94.76% |
| 1800 | heavy_tail | 968 | 972 | 95.66% | 95.58% | 95.50% | 94.09%–96.70% |

- n=1,800 **rare_binary**: fixed-ridge point coverage 93.36%; Wilson 95% interval 91.63%–94.76%, **excluding** nominal 95%. Unregularized 93.43%, Wilson 91.70%–94.82%, also excludes 95%. The oracle was 94.20% in the same cell; its closeness to nominal cannot by itself prove the score variance is correct or invalidate the fitted-method finding.
- No method passed the 99% completion requirement in any of the six non-oracle positive cells. Even at n=1,800, the best regularized cell completed 979/1000, below the required 990/1000.
- Per-cell mean bias, CI width, reported SE to Monte Carlo SD ratio, refusal reasons and arm-level weight effective-sample-size diagnostics appear in `results/G25C_primary_summary.json`. All primary receipts appear in a compressed lossless JSON archive.

## Identification and overlap findings

- Both fitted methods retain a **0.015 minimum fitted-propensity bound**, unchanged fold counts, and no propensity clipping or post-hoc policy lowering.
- Research-only true propensities stay away from structural zero. Sample-dependent fitted propensity extrema nevertheless trigger positivity refusals. This is evidence that an unstable model fit can cause a *guard to refuse*, not proof that observed data identify a causal effect in general.
- Five fixed covariate bins, per-arm effective sample sizes and true-propensity lower bounds are diagnostic only; **none** can certify hidden ignorability or substitute for identification assumptions.
- All **300/300** negative controls refused under explicit structural support or trusted generator metadata. The hidden-confounding and measurement-error controls are *metadata-based refusals*, **not** automatic hidden-confounder detection.
- Paired on jointly accepted cases, coverage differences from regularization were near zero; the paired analysis reports all six per-cell comparisons. This does not establish equivalence in refused cases or under distribution shift.

## Full-pipeline pairs-bootstrap attempt

The preregistered diagnostic considered 20 independently seeded candidates in each of six cells (120 candidate datasets per model) and attempted **99 complete-data resamples per initially accepted dataset**, re-estimating all nuisance fits and split assignments. If *any* resample failed, that candidate produced **no** bootstrap CI; no opportunistic exclusion or imputation was performed.

| Metric | Baseline | Ridge |
|---|---:|---:|
| Candidate datasets attempted | 120 | 120 |
| Original fit refused | 9 | 6 |
| Initial fit accepted, incomplete bootstrap | 93 | 96 |
| Every resample completed | 18 | 18 |
| Resamples attempted | 10,989 | 11,286 |
| Resample refusals | 1,158 | 1,152 |

The bootstrap auditor independently checked every candidate, resample count, refusal reason tally and CI admission rule: **240 method slots = 15 base refusals + 189 incomplete full refits + 36 complete full refits**. The 36 complete method slots correspond to 18 completed candidates per method, not 36 independent datasets. This conditional subset is too small and biased toward easy-to-fit data to justify accuracy claims. The bootstrap experiment has no 95%-coverage acceptance power.

## Independent checks

- **13/13** source-level unit tests pass, including tampered coverage, missing/duplicate attempts, negative-control mutation, and bootstrap failure-record mutation.
- Independent structural audit: **6,000 unique fixture hashes; 18,000 method slots = 17,160 completed + 840 refused; 300/300 negative controls refused.**
- Deterministic source replay: **84 distinct fixture replays / 252 exact estimator results**, plus **12,000/12,000 exact pre-correction method receipts**. These are repeatability checks, not independent derivations.
- Numerically independent installed `statsmodels` GLM/OLS check across **48 separate cases**, including ordinary logistic, penalized logistic, and continuous OLS. Maximum absolute propensity prediction difference: unregularized `6.17e-08`; ridge `5.02e-05`; continuous-outcome OLS `3.11e-15`; all met prespecified numerical tolerances.
- Full refit bootstrap integrity auditor: **120 unique candidates, 240 method slots, 22,275 resample attempts, every failure accounted for**.

## Why this is not a nuisance-robust confidence interval

For observed covariate X, treatment T, outcome Y, propensity e(X) and outcome regressions m_t(X), the AIPW score equals

`m1(X) - m0(X) + T*(Y-m1(X))/e(X) - (1-T)*(Y-m0(X))/(1-e(X))`.

Using its sample variance divided by n implicitly relies on regularity and nuisance convergence/orthogonality conditions. A doubly robust **point estimate** can remain consistent when one nuisance estimator is misspecified, without guaranteeing that a naive score-only **confidence interval** correctly accounts for first-order nuisance-estimation contributions. A stacked estimating-equations sandwich may address specific smooth fitted nuisance models, but cross-fitting changes the dependence structure and requires explicit derivation. Full-pipeline resampling is a possible check, not a cure if many resamples fail identification/refusal criteria. This G25C experiment does **not** supply a complete sandwich derivation or a validated misspecification-robust CI.

## Gates and engineering decision

| Requirement | Result |
|---|---|
| 1,000 attempted per positive cell | **PASS** (6/6) |
| ≥990 completed per fitted-method cell | **FAIL** (0/12) |
| Correct-model CI coverage ≥93% on accepted cases | **PASS, conditional only** (12/12) |
| Nominal 95% within Wilson 95% in every fitted cell | **FAIL** (n=1,800 rare_binary both methods) |
| Independent library nuisance prediction checks | **PASS, limited** (48 samples, not external causal CI verification) |
| Full-refit bootstrap 99/99 acceptance | **FAIL** (18/120 per method) |
| Exact receipt integrity, refusal and replay | **PASS** |
| Source-level G9 production equivalence/host integration | **NOT TESTED** |
| Arbitrary misspecification-robust CI derivation | **NOT ESTABLISHED** |
| Separate user approval for production estimator changes | **NOT GIVEN** |

**Decision:** Hold Cognitum production G9 unchanged. G25C is completed research but **G25 acceptance remains open**. Do not use these findings to authorize production interval algorithms, to disable refusal, or to change Lu security/host authorization.

## Next G25 engineering sequence

1. **G25D overlap/fit separation:** predeclare *new* model families, support diagnostics with a calibrated propensity uncertainty rule and a conservative exclusion boundary. Treat true identification violations and unstable nuisance fits separately, but never override causal nonidentification with a numeric interval. Need fresh independent datasets and all refusals preserved.
2. **G25E rare-event inference:** explicitly compare independent penalized/Firth-like outcome fits, rare-binomial inference, propensity stability, score tails/skewness and finite-sample confidence procedures; test severe event sparsity. Separate calibration from variance proof.
3. **G25F nuisance-aware variance:** derive, review and implement an estimable stacked-system sandwich for stated model classes (including sample-split dependence) and evaluate a principled full-refit bootstrap refusal policy. No generic double-robust CI claim under arbitrary misspecification.
4. **G25G external and production checks:** verify against independent causal libraries and actual source G9 with identical fixtures, broader multivariate nonlinear SCMs and distinct replication cohorts, 1,000+ datasets per acceptance cell (or preregistered power design), plus deployment rollback and host authorization gates.

## Reproduction

From the package directory (Python 3.13 with NumPy, SciPy, statsmodels):
```sh
python -m unittest discover -v -s tests
python tools/audit_g25c.py
python tools/audit_g25c_bootstrap.py
python tools/g25c_numeric_spot_replay.py
python tools/run_g25c_library_crosscheck.py
python tools/run_g25c.py                 # reruns primary, overwriting output
python tools/run_g25c_bootstrap.py       # reruns exploratory bootstrap
```
No network access, C14 production wheel, DoWhy/CVXPY, Lu, OS elevation or hosted CI is required to reproduce this isolated study. Tests and analyses were executed locally; GitHub is only a copy of the research record.
