# Cognitum C14 G25 — Independent nonlinear/rare/heavy-tail causal CI research, cohorts A and B

**Date:** 2026-11-01  |  **Status:** Research Phase A/B complete; G25 scientific acceptance **NOT PASSED**. **No production estimator change.**

## Purpose and integrity
G24 showed that correctly specified cross-fitted AIPW influence-function intervals sometimes cover near nominal and that pooled-propensity misspecification can underestimate uncertainty. G25 tests whether these patterns persist in additional independent simulated settings without changing the production C14/G9 implementation.

- Cohort A: 3 independent scenarios × 1,000 attempts at n=900, fixed seeds 610000–610999, 620000–620999, and 630000–630999.
- Cohort B (separately frozen before evaluation): same scenario definitions, 1,000 attempts at n=1,800, seeds 810000–810999, 820000–820999, and 830000–830999.
- Both compare independent twofold cross-fitted AIPW under correctly specified nuisance models, intentionally pooled propensity, intentionally linear-only outcome regression, and a ground-truth nuisance-function oracle. All use basic score-standard-deviation / sqrt(n) normal intervals. The oracle is a *nondeployable diagnostic*, not a proposed algorithm.
- The positive generators use one measured continuous covariate clipped at ±2.7, a nonlinear propensity logit, a nonlinear outcome response, treatment-effect heterogeneity, either a rare binary outcome or heavy-tailed continuous residuals. The heavy-tail case uses a standardized t(5) covariate and outcome residuals; the other two use a winsorized normal covariate. Superpopulation true average treatment effects are analytic for continuous outcomes, numerical Gauss-Hermite integration for the rare binary outcome.
- Positive-generator covariate clipping was amended **after a 30-case developmental smoke and before any full 1,000-replicate holdout**. The amendment, original preregistration hash, and rationale are preserved in `G25_Predeclaration.json`. This transparency matters: it is not an unchanged blind preregistration. The smoke outputs are not scored in the holdout.
- Frozen cohort A prereg SHA-256: `b9b3317e9c286187b70d746e3c332df49ea09c894cfe0a78f9d266597d1331b5`. Frozen independent cohort B SHA-256: `2d8b3d48e3c554704911b1b37e476a7b495bc3df90e0e6d1f7679db1d58097f2`. G25 inference source SHA-256: `36fa6d9f8113c9931f3bf1509a780350dfebf56ff20f18601735381750794d73`; runner: `50ec01e0c8c099c2070e377f578bbbc7819607de40c30c7ab1c3675677cfa4da`. These are identical between both held-out runs.

## Held-out research results
The following coverage estimates are **conditional on completion**. Refusal rates are reported separately. Each completed case yields all four method intervals; none is silently excluded for poor coverage.

| Cohort | Scenario | Completed / 1,000 | Correct AIPW 95% CI coverage | Pooled-propensity AIPW | Known-nuisance oracle |
|---|---|---:|---:|---:|---:|
| A, n=900 | smooth_gaussian | 891 | 95.17% | 93.38% | 94.73% |
| A, n=900 | rare_binary | 877 | 95.78% | 95.78% | 95.44% |
| A, n=900 | heavy_tail | 848 | 95.87% | 93.75% | 95.40% |
| B, n=1,800 | smooth_gaussian | 980 | 94.18% | 93.27% | 95.00% |
| B, n=1,800 | rare_binary | 981 | 95.21% | 94.90% | 94.80% |
| B, n=1,800 | heavy_tail | 960 | 94.27% | 92.29% | 94.38% |

All cells required >=990 completed of 1,000 and a point coverage of >=93% plus the nominal 95% inside a Wilson 95% uncertainty interval. **Every positive cell failed the completion gate**, including both sample sizes. Correct-model coverage in all six cells was 94.18–95.87%; the individual cells passed the coverage-point and Wilson-compatibility screens, but this does not overcome refusals or constitute production acceptance.

The **pooled-propensity** method failed Wilson compatibility at n=900 for smooth Gaussian (93.38%, Wilson 91.55–94.83%) and n=1800 for smooth Gaussian (93.27%, Wilson 91.52–94.67%) and heavy-tail (92.29%, Wilson 90.43–93.82%). The last also failed the >=93% coverage floor. Mean signed bias remained modest while reported SEs were smaller than empirical estimator SD: n=1800 smooth Gaussian 0.941, heavy-tail 0.947. These data support the G24 concern that point-estimate robustness alone does not confer robust interval uncertainty.

### Unadjusted paired coverage differences versus correct AIPW
Pairs are matched on the same accepted simulated dataset. Intervals are 4,000-resample percentile bootstraps of dataset-paired coverage indicators, *without multiple-comparison adjustment*. These are exploratory and not preregistered discovery tests.

| Cohort | Scenario | Pooled minus correctly specified coverage | Unadjusted 95% paired interval |
|---|---|---:|---:|
| A | smooth_gaussian | -1.80 pp | -3.14 to -0.56 pp |
| A | rare_binary | +0.00 pp | -0.91 to +0.91 pp |
| A | heavy_tail | -2.12 pp | -3.30 to -0.94 pp |
| B | smooth_gaussian | -0.92 pp | -2.04 to +0.10 pp |
| B | rare_binary | -0.31 pp | -1.12 to +0.51 pp |
| B | heavy_tail | -1.98 pp | -3.02 to -0.94 pp |

## Refusals and safety

| Cohort | Positive attempts | Positive refusals | Primary overlap refusals | Rare binary fitting refusals | Negative-control refusals |
|---|---:|---:|---:|---:|---:|
| A | 3,000 | 384 | 345 | 39 | 300/300 |
| B | 3,000 | 79 | 78 | 1 | 300/300 |

The chosen cross-fold positivity rule rejects if *any* fitted propensity in either held-out fold falls below 0.015 or above 0.985. In the positive synthetic generators, the true propensity stays roughly between 0.05 and 0.71, but finite-sample nuisance fitting sometimes predicts more extreme probabilities. This **policy/model-fit disagreement**, rather than confirmed structural non-overlap, accounts for 345/384 A refusals and 78/79 B refusals. The rare binary outcome model also sometimes has too few events or nonconvergent logistic fits. Do not silently clip predictions or lower the cutoff on these evaluated seeds to manufacture an apparent pass. A newly preregistered independent evaluation is required before changing overlap policy.

The three separate 100-dataset negative-control families per cohort intentionally refuse: (1) deterministic treatment/no observed support, (2) **trusted synthetic metadata** indicating an unobserved confounder, (3) trusted metadata indicating measurement error in the required adjustment variable. The hidden-confounding/measurement-error controls test **metadata-based refusal**, not an algorithm that detects latent confounding from observed data. Such detection is not generally guaranteed.

## Gates: objective outcome
- **FAIL:** >=99% completion and >=990 complete per positive acceptance cell. Across both cohorts, 463/6,000 positive attempts refused (7.72%).
- **FAIL / unsupported:** at least one pooled-propensity cell below the >=93% coverage floor; three cells exclude nominal 95% within Wilson 95% coverage uncertainty.
- **PASS, limited:** all six correctly specified AIPW cells have point coverage >=93% and Wilson intervals that include nominal 95%, conditional on acceptance. This does not excuse refusal or prove general validity.
- **PASS:** structural independent receipt audits for both cohorts; 6,000 unique case IDs, all 24,000 possible method-slot attempts accounted for as either 22,148 completed interval receipts or 1,852 slots refused with their parent dataset; 600/600 explicit negative controls refused; 11/11 local unit tests passed including deliberate tampering and truncation failures.
- **NOT EVALUATED:** correction for nuisance estimation under misspecification with formally justified sandwich or resampling theory; production G9 integration/regression; direct independent library cross-checks; substantive real-world dataset inference; large multivariate or latent-variable Monte Carlo; reproducibility on other environments; peer review and rollback validation. These are required before algorithm promotion.

## Important limits and next G25 work
1. Predeclare a *new, disjoint* cohort for empirical-overlap/weight-stability diagnostics, including effective-sample-size bounds, train/test support, and calibrated probability uncertainty. Do not revise this tested guard retroactively. Benchmark conservative identification refusals separately from nuisance-fitting warnings.
2. Derive nuisance-aware variance correction using stacked estimating equations under explicit misspecification and compare full refit bootstrap plus influence-function methods. Avoid claiming generic double-robust confidence intervals under arbitrary nuisance misspecification.
3. Expand to multivariate continuous/nonlinear covariates, independently drawn effect-heterogeneity patterns, rare binary events with varied prevalence, stronger tails, measured error, and known hidden common causes; at least 1,000 **independent datasets per acceptance cell**, with Wilson MC compatibility.
4. Cross-check nuisance fits and point/CI behavior against independent official causal libraries when available. Report any incompatibilities and finite-sample disagreements, not just average favorable results.
5. Add holdout replication under genuinely new generators, exact-method numerical replay on source G9 (not merely this isolated code), and production host refusal/conversation-authority tests before seeking separate approval for any change.

## Isolation and reproducibility
G25 experimental code and generated data live solely in this research package. No Lu source, Lu IPC, Cognitum installed production algorithm, or shared main branch was modified. Dependencies: Python 3.13-compatible NumPy and SciPy for reproduction; tests use stdlib unittest. Runtime recorded as Python 3.13.5, NumPy 2.3.5. Run `python -m unittest discover -v -s tests`, then `python tools/audit_g25_independent.py` (no solver/network access needed). Run `python tools/run_g25.py` and `python tools/run_g25.py --config G25_Predeclaration_B.json --output results/G25_B_positive_receipts.json --summary results/G25_B_summary.json` for deterministic re-execution. Independent structural auditor does not independently recompute causal estimators, and no production runtime was exercised.

**Decision:** Retain production G9 unchanged. G25 research A/B documents a reproducible modeling/refusal-policy issue and a misspecification-associated undercoverage pattern, but is **not completed or promotion-ready**.