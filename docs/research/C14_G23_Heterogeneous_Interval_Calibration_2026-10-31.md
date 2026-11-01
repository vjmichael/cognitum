# Cognitum C14 G23 — Heterogeneous-effect interval calibration, independent holdout

**Research date:** October 31, 2026 (Arizona); runs recorded November 1 UTC.  
**Scope:** Cognitum-only research; no Lu source, configuration, runtime, DLC admission or repository changes.  
**Result:** Two 500-seed independent replications completed; receipt and selected numerical replay passed. Scientific issue is **not fully resolved**.

## Question and preregistered diagnostic design

The G18 research benchmark reported only **89/100 (89%)** coverage for a nominal 95% two-fold cross-fitted AIPW interval at n=900 in the observed-heterogeneous scenario. Is this a Monte Carlo anomaly, or does interval calibration remain weak? What changes under nuisance-model misspecification or poor treatment overlap?

- Discovery reference: G18 seeds 2001–2100, never reused in this report.
- Independent holdout A: seeds 10001–10500; holdout B: 20001–20500. **1,000 separately seeded datasets per condition**, at n=300, 900 and 1,800 (within G7's max n=3,000).
- A further 1,000 datasets per size at n=300 and n=900 use a **separate, deliberately weak-overlap** generator with treatment probabilities 0.04 and 0.96 across binary covariate strata. The weak-overlap generator is entirely within this research tool; no production G7 generator was edited.
- Total **5,000 datasets** × 9 interval methods = **45,000 method attempts**, including explicitly counted refusals. All outcomes have known analytic synthetic population treatment effect **0.295**; this is *not inferred from observational data*.
- Intervals: G9 AIPW (stratified nuisance), three prespecified pooled-nuisance ablations, G8 population-mix Wald, pairs-bootstrap percentile/normal/BCa (399 resamples), and an **oracle-nuisance diagnostic that uses the data-generating probabilities**. Oracle-nuisance results are **not deployable model performance**.
- Coverage is calculated only where an interval was computed, with the computed denominator and refused denominator always shown. All statuses, width, bias and empirical variability are preserved.

## G18 discovery cohort vs new holdout results, n=900

| Method | G18 discovery (100) | G23 independent holdouts (1,000) | Wilson 95% uncertainty for holdout coverage |
|---|---:|---:|---:|
| Stratified AIPW | 89.0% | 92.8% (928/1000) | 91.0%–94.2% |
| Population-mix Wald | 92.0% | 93.8% (938/1000) | 92.1%–95.1% |
| Pairs bootstrap percentile | 92.0% | 93.2% (932/1000) | 91.5%–94.6% |
| Pairs bootstrap normal | 93.0% | 93.8% (938/1000) | 92.1%–95.1% |

The earlier 89% was lower than the new 92.8% estimate, so a small discovery-cohort fluctuation contributed. **However, 92.8% remains below nominal 95%,** and its uncertainty interval does not include 95%. This warrants further investigation, rather than declaring the method fixed. Several methods and sample sizes were examined; these intervals and any informal significance checks are descriptive, **not multiplicity-adjusted proof of a universal defect**.

## More detailed n=900 results, 1,000 attempts per method

| Method | Successful intervals / attempts | Coverage on successful intervals | Mean width |
|---|---:|---:|---:|
| Cross-fit AIPW (stratified) | 1000/1000 | 92.8% | 0.139 |
| Population-mix Wald | 1000/1000 | 93.8% | 0.136 |
| Pairs bootstrap percentile | 1000/1000 | 93.2% | 0.134 |
| Pairs bootstrap normal | 1000/1000 | 93.8% | 0.136 |
| AIPW (pooled propensity) | 1000/1000 | 87.4% | 0.109 |
| AIPW (pooled outcome) | 1000/1000 | 97.1% | 0.169 |
| AIPW (both pooled) | 1000/1000 | 0.0% | 0.114 |
| AIPW with true nuisance (diagnostic) | 1000/1000 | 94.2% | 0.136 |

- **Nuisance misspecification matters:** pooling propensity across Z while retaining a stratified outcome model yields **87.4%** coverage, near-zero average signed bias (=0.0021), but mean reported SE / empirical estimator SD = **0.785**. This is consistent with **underestimated uncertainty**, despite the favorable bias behavior. Standard asymptotic AIPW point-estimation robustness does not automatically validate this naive confidence interval under nuisance misspecification.
- Pooling both nuisance models produces substantial systematic bias (=0.2006) and **0/1,000 covered** in this synthetic design; do not average away the failures.
- Pooling the outcome model while retaining the stratified propensity gives wider, often conservative intervals (coverage 97.1%); this is not automatically a preferred estimator.
- Even the oracle-nuisance control reaches only 94.2% at n=900. This prevents attributing all undercoverage to estimated nuisance functions alone. Different finite-sample mechanisms and repeated-cohort effects remain plausible.

## Sample-size sensitivity, observed heterogeneous

| n | Stratified AIPW | Population-mix Wald | Oracle-nuisance control | AIPW pooled propensity |
|---:|---:|---:|---:|---:|
| 300 | 93.9% (988/1,000) | 94.0% | 95.2% | 88.3% |
| 900 | 92.8% (1000/1,000) | 93.8% | 94.2% | 87.4% |
| 1800 | 92.9% (1000/1,000) | 93.3% | 93.3% | 87.0% |

The n=1,800 cohort does not automatically restore nominal 95% coverage, including for the oracle diagnostic. This study does **not** isolate the definitive cause. Sample-size groups reuse seed labels for controlled comparison and therefore should not be treated as fully independent across n.

## Weak-overlap stress tests (not a calibrated positive execution gate)

| Method | Successful intervals / attempts | Coverage on successful intervals | Mean width |
|---|---:|---:|---:|
| Cross-fit AIPW (stratified) | 0/1000 | — | — |
| Population-mix Wald | 498/1000 | 89.0% | 0.421 |
| Pairs bootstrap percentile | 0/1000 | — | — |
| AIPW with true nuisance (diagnostic) | 1000/1000 | 96.6% | 0.483 |

| Method | Successful intervals / attempts | Coverage on successful intervals | Mean width |
|---|---:|---:|---:|
| Cross-fit AIPW (stratified) | 3/1000 | 100.0% | 0.259 |
| Population-mix Wald | 1000/1000 | 92.8% | 0.281 |
| Pairs bootstrap percentile | 647/1000 | 92.4% | 0.275 |
| AIPW with true nuisance (diagnostic) | 1000/1000 | 94.9% | 0.284 |

The true treatment propensity is still mathematically positive, but its 0.04/0.96 extremes create practical overlap problems. G9 intentionally refuses many AIPW and bootstrap intervals, with rejections recorded instead of omitted. In particular, a few surviving AIPW intervals cannot certify nominal coverage. The oracle diagnostic has impossible-to-obtain true nuisance probabilities and **must not override the refusal policy**. Conditional coverage among surviving cases is not coverage across all attempts.

## Verification and execution environment

- Python 3.13 with NumPy and SciPy; existing G7/G8/G9 Cognitum scientific methods, locally installed DoWhy 0.14, EconML 0.17.0, CVXPY 1.9.3 and all previously tested optimization solvers. G23 uses the G7/G8/G9 numerical routines; it **does not** claim that DoWhy/EconML/CVXPY ran on all 5,000 datasets.
- **Independent receipt auditor:** 5,000 fixture hashes, 45,000 method attempts, unique seeds, group totals, interval endpoints, coverage flags, signed error, widths, all rejection status counts — PASS.
- **Deterministic numerical spot-replay:** 80 randomly selected complete fixtures reproduced identical results — PASS. This does not mean independent verification of every mathematical interval formula.
- **Targeted regressions:** 81 passed, 7 skips (environment-dependent legacy negative/source gates); no unexpected failures. Earlier G22 scientific-suite result remains separately documented as 653 passed and two expected skips; G23 did not rerun that entire 653-test suite.
- **Two holdout execution durations:** 11.16s and 9.69s for the synthetic routines; these are **not LLM inference latency**.
- Source and raw receipts are included in the downloadable G23 archive, not copied into a public repository by default.

## Engineering conclusion and next research gate

**G23 exploratory calibration evidence complete; root cause not yet formally isolated.** The original 89% result partly reflects limited Monte Carlo precision, but further holdouts support undercoverage for AIPW and substantially worse behavior under pooled-propensity misspecification. More robust interval methods should be compared on **new, predeclared generators and fresh seed sets** without tuning to this holdout. Candidate follow-on work: improved nuisance-aware variance estimates, repeated cross-fitting, split stability, multiplier/bootstrap inference, explicit overlap thresholds, and independent cross-library estimator implementations. These are *research candidates*, not shipped fixes.

**No source changes to Lu, no cross-platform convergence interference, no production authorization to execute newly proposed C14 capabilities.**
