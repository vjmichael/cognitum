# Cognitum C14 G24 — AIPW variance root-cause investigation and unseen-SCM comparison

**Date:** October 31, 2026 (America/Phoenix; some container timestamps Nov 1 UTC)  
**Status:** Completed research holdout and independent verification. **NO production estimator change approved or implemented.**  
**Scope:** Cognitum-only research. No modification of Lu, its unified source, configuration, DLC routing, Windows/Linux development, or main branches.

## Executive conclusion

The G23 undercoverage does **not** appear to be a universal deterministic implementation error in the *correctly specified* two-fold influence-function (IF) standard error. Its measured size varies with generator, random cohort and sample size, and even the true-nuisance oracle occasionally falls below nominal coverage. A second, more reproducible problem exists when the propensity model is deliberately **misspecified**: the score-only IF standard error is systematically too small relative to the actual sampling variability, despite small point-estimate bias in this synthetic setup.

Five-fold cross-fitting is an eligible research candidate, but its pooled improvement over the original two-fold estimator was only **0.43 percentage points**, with an unadjusted seed-clustered 95% interval of **-0.033 to 0.900 percentage points**. **No method has established a statistically decisive, general accuracy improvement sufficient for a production change.**

## Source and preregistration integrity

- Design frozen before the first holdout at SHA-256: `dc999aaf82134253be62d87e0997ee26e5523f5dee809347ccdab90154f2adaa`.
- Second independent replication was preregistered separately before its run at SHA-256: `eb9c6a45ba062a5256f30d75c2057b047b5533029693a37802a6ea0e845f16af`.
- Exact held-out runner source SHA-256 (unchanged across cohorts): `005d24b9731052205c2c3f91f07aa15644f685bbde0630c45c98eab453dd8c0e`.
- New SCMs: **A, B, C**, each with distinct measured-Z prevalence, treatment assignment probabilities, baseline outcome risks and treatment heterogeneity; these are not the G7/G18/G23 parameters.
- Cohort A: seeds **31001–31250**; cohort B: **41001–41250**, disjoint from discovery/G23.
- Three SCMs × two sample sizes (**900 and 1800**) × 250 seeds × 2 cohorts = **3,000 dataset receipts** across 1,500 family-seed clusters (the two sample sizes reuse each cluster seed), and **24,000 method attempts**.
- The analytic synthetic average treatment effect is specified by the generation equations, not inferred from observed data. Only generators with measured adjustment and adequate overlap enter positive coverage comparisons.

## Unseen-generator coverage and width

Each pooled row represents 3,000 attempted intervals, with no refusals in the primary positive holdouts. Sample-size cells sharing a family-seed cluster are not assumed statistically independent. The 12-cell screen is six (SCM × sample size) cells repeated in two independent seed cohorts. Screening **does not** confer production approval.

| Method | Nominal 95% coverage observed | Mean width | Mean signed error | G24 research screen passed |
|---|---:|---:|---:|---:|
| Original G9 two-fold AIPW | 94.20% | 0.1274 | +0.0004 | 12/12 |
| G24 five-fold AIPW | 94.63% | 0.1264 | +0.0005 | 12/12 |
| Repeated 2-fold AIPW | 94.67% | 0.1274 | +0.0005 | 11/12 |
| Repeated 2-fold + split heuristic | 95.17% | 0.1308 | +0.0005 | 12/12 |
| Stratified delta/Wald | 94.53% | 0.1248 | +0.0004 | 12/12 |
| Pairs bootstrap, normal | 94.30% | 0.1252 | +0.0004 | 9/12 |
| Pairs bootstrap, percentile | 93.90% | 0.1224 | +0.0004 | 6/12 |
| Known-nuisance oracle (non-deployable) | 94.67% | 0.1248 | +0.0004 | 12/12 |

**Paired uncertainty for method differences, relative to original G9 two-fold AIPW:** clusters were family + seed (two sample sizes per cluster). A 3,000-resample seeded cluster bootstrap found:

| Comparison | Difference in covered fraction | Unadjusted 95% paired interval |
|---|---:|---:|
| G24 five-fold AIPW | +0.43 percentage points | -0.03 to +0.90 points |
| Repeated 2-fold AIPW | +0.47 percentage points | +0.00 to +0.93 points |
| Repeated 2-fold + split heuristic | +0.97 percentage points | +0.53 to +1.43 points |
| Stratified delta/Wald | +0.33 percentage points | -0.13 to +0.77 points |
| Pairs bootstrap, normal | +0.10 percentage points | -0.40 to +0.57 points |
| Pairs bootstrap, percentile | -0.30 percentage points | -0.90 to +0.27 points |
| Known-nuisance oracle (non-deployable) | +0.47 percentage points | +0.03 to +0.90 points |

No multiplicity correction was applied to those exploratory method comparisons. The oracle and split heuristic are **not deployable** confidence-interval candidates. Widening intervals or using true nuisance functions to improve synthetic coverage is not an evidence-based production solution.

## Why the original confidence intervals can be too narrow

G9 uses the standard augmented inverse-propensity-weighted score for a binary treatment, observed binary covariate Z, and binary outcome:

`score = (m1(Z)-m0(Z)) + T*(Y-m1(Z))/e(Z) - (1-T)*(Y-m0(Z))/(1-e(Z))`.

Its normal confidence interval estimates SE as the **sample standard deviation of cross-fitted scores divided by sqrt(n)**. That is a plausible asymptotic IF-based estimator when the nuisance estimates meet sufficient consistency/orthogonality assumptions. It is **not** automatically a valid finite-sample variance estimator under arbitrary nuisance misspecification.

In particular, when propensity estimates pool the Z strata while outcomes are correctly stratified, score orthogonality with respect to outcome-fitting errors is no longer guaranteed. Nuisance estimation can contribute first-order uncertainty not captured by treating the fitted score vector as fixed. This is a theoretically plausible mechanism; the simulation evidence agrees with it, but no formal decomposition of every finite-sample term has been proved.

**G23 original (1,000 seeds at n=900):** correctly specified two-fold AIPW covered **92.8%**; reported SE / empirical Monte Carlo estimator SD **0.944**. Pooled-propensity AIPW covered **87.4%**; SE/SD **0.785**. Under a newly seeded replay of the original generator:

| Sample size | Method | Coverage | Mean reported SE / empirical estimator SD |
|---:|---|---:|---:|
| 900 | Correct two-fold AIPW | 94.8% | 1.015 |
| 900 | Correct five-fold AIPW | 95.4% | 1.017 |
| 900 | Deliberately pooled propensity | 90.0% | 0.814 |
| 900 | Known-nuisance oracle diagnostic | 95.2% | 1.010 |
| 1800 | Correct two-fold AIPW | 93.0% | 0.958 |
| 1800 | Correct five-fold AIPW | 93.6% | 0.963 |
| 1800 | Deliberately pooled propensity | 86.2% | 0.768 |
| 1800 | Known-nuisance oracle diagnostic | 93.4% | 0.958 |

The new n=900 correctly specified cohort reaches near-nominal coverage; the same n=1800 cohort happens to under-cover, **including for the true-nuisance control**. This is evidence of sensitivity to finite-sample/case composition and Monte Carlo variation, not a proof that asymptotic IF variance itself is systematically broken under correct nuisance specifications. The generator's analytic true-nuisance IF SE is **0.03461 at n=900** and **0.02447 at n=1800**; its empirical Monte Carlo SD can fluctuate around those population values.

By contrast, the pooled-propensity misspecification consistently understates uncertainty in the original and new cohorts. The correct response is **model diagnostic, refusal, and a method with an appropriate variance derivation**, not an arbitrary multiplicative SE correction trained on one simulator.

## Full-pipeline refit bootstrap diagnostic

A separate, much smaller diagnostic refitted both propensity/outcome nuisance models and fold assignments in **199 complete-data bootstrap resamples per attempt** over 150 candidate datasets. Exactly **140/150** completed all resamples; **10/150 refused**, and the failed bootstrap cases were not silently discarded or included in coverage denominators. The average refit-bootstrap SE was **{refit['mean_refit_bootstrap_se_over_naive_if_se']:.3f}×** the IF SE on accepted cases.

| Conditional on 140 fully accepted datasets | Coverage | Mean width |
|---|---:|---:|
| G24_REFIT_BOOT_NORMAL | 95.0% | 0.1502 |
| G24_REFIT_BOOT_PERCENTILE | 97.1% | 0.1462 |
| G9_NAIVE_IF | 96.4% | 0.1482 |

The subset is small and **selected for bootstrap success**; these figures do not establish population-level coverage or a superior general-purpose CI. Full refitting did not supply a large, universal adjustment. Any future refit bootstrap must report all invalid resamples and justify refusal/minimum-overlap policy.

## Identification and overlap safety controls

New independent no-overlap cases: **100/100 rejected** by both G9 AIPW and G8 stratified Wald. New near-overlap cases: G9 **100/100 refused** (43 extreme propensity, 53 training-fold overlap and 4 insufficient overall overlap), whereas G8 computed **96/100 descriptive Wald intervals**. Those 96 must **not** be treated as causally valid or mixed into coverage scoring merely because they are numeric. A future host-reviewed C14 capability should use the strongest applicable identification/overlap policy independent of which estimator returns a number.

These are source-level scientific controls only; no Lu tool-grant/OS-sandbox authority was exercised.

## Preregistered G24 research screen (before first results)

A candidate must pass **each** of 12 generator/cohort/size cells: at least **200 completed cases** per cell; at least **99% completion**; coverage point estimate **≥93%**; nominal 95% inside the empirical coverage's **Wilson 95% interval**; mean CI width **≤1.15×** the G8 stratified reference; absolute mean signed bias **≤0.015**; and coverage no worse than original two-fold G9 by more than **1 percentage point**. Zero receipt inconsistencies required. These are **screening conditions only**, not a guarantee of nominal frequentist coverage and not automatic permission to modify any algorithm.

Across two cohorts, five-fold AIPW and stratified delta/Wald each passed **12/12 research cells**, while original G9 two-fold also passed **12/12**; repeated ordinary two-fold passed **11/12**; pairs bootstrap-normal **9/12**, percentile **6/12**. The split-variance heuristic passed **12/12**, but lacks a defensible uncertainty derivation and is disqualified for promotion. The oracle also passed, but uses privileged ground truth and is disqualified.

## Additional requirements before any production estimator change (proposed G25 acceptance, NOT retrospectively part of G24)

1. Preregister broader models with **continuous and nonlinear measured covariates**, multiple effect-heterogeneity mechanisms, non-Gaussian/rare-outcome conditions, and separately marked hidden-confounding/measurement-error failures; no tuning on evaluation seeds.
2. Repeat with at least **1,000 independent datasets per acceptance cell** or a justified precision/power design; report *both* achieved coverage and its uncertainty. Require the nominal 95% target to remain compatible with Monte Carlo uncertainty in **every** supported cell; investigate any cell below 93% rather than compensating by pooling across scenarios.
3. Require estimator correctness/variance justification (asymptotic derivation or valid resampling procedure) for the advertised nuisance classes. Specifically **do not claim arbitrary misspecification-robust confidence intervals** solely from doubly robust point-estimate consistency.
4. Check refusal and uncertainty behavior against weak/no overlap, hidden common causes, and measurement error. No causal-confidence label when identification conditions are invalid; counts include every attempted dataset.
5. Evaluate mean width, bias, tail behavior, computation cost and repeatability, plus independent real-library cross-checks. A candidate should not be promoted merely because its intervals are wider.
6. Require an independent code review, separate holdout replication, exact receipt/provenance audit, and rollback plan; **no algorithm changes without separate explicit user authorization**.

## Independent verification and regression results

- Independent receipt auditor, **3,000 distinct fixture hashes and 24,000 interval receipts**, two non-overlapping cohorts: **PASS**; deliberate tampering rejected.
- Deterministic numerical replay of **80 complete cases / 640 method results**: **80/80 exact matches**.
- G24 auditor, generator, variance and bootstrap unit tests: **19 passed**.
- Existing Cognitum G8/G9 scientific regression tests: **56 passed**.
- Nuisance-reestimated bootstrap refusals and near-overlap reports preserved, not erased.
- All results obtained with the existing Cognitum G7/G8/G9 source and independent G24 research scripts. **No production algorithm changes**, no Lu source or DLC modifications, and no HTP packages required.

## Reproduction artifacts

`G24_Predeclaration.json`, `G24_Replication_Predeclaration.json`, `tools/run_c14_g24_variance_holdout.py`, `tools/run_c14_g24_refit_bootstrap.py`, `tools/run_c14_g24_root_cause_diagnostics.py`, `tools/g24_paired_effects.py`, `tools/audit_c14_g24_receipts.py`, `tests/*`, `results/G24_1500_Fresh_SCMs.json`, `results/G24_1500_Independent_Replication.json`, `results/G24_Full_Refit_Bootstrap_Diagnostic.json`, `results/G24_Root_Cause_Diagnostics.json`, `results/G24_Paired_Coverage_Effect.json`, `results/G24_Independent_Audit.json`, `results/G24_Numerical_Spot_Replay.json`, and CSV summaries are bundled in the companion archive. Raw dataset records contain only synthetic binary measurements (represented by fixture identifiers/hashes and estimator outputs), not personal data or model weights.
