# Cognitum C14 G25D — Separation of structural overlap, propensity-fit instability, and rare-event nuisance failures

**Date:** 2026-11-01  
**Milestone:** G25D research and verification completed; **full G25 production acceptance NOT MET**.  
**Scope:** Isolated offline Python research. No Cognitum production G9 algorithm edits, no Lu edits, no IPC/security-policy changes. GitHub is repository/documentation only.

## Executive finding

G25D differentiated three concerns that were conflated by some earlier diagnostic narratives:

1. **True positivity versus fitted propensity:** In two new correctly specified, bounded 2-covariate SCM families, observed *true* treatment probabilities stayed at least **0.135** away from the boundaries on sampled data. Nevertheless, an expanded polynomial nuisance fit sometimes produced a fitted cross-fold probability below the frozen **0.015** guard. Those are *fit-triggered refusals* in a simulated adequately overlapping model, not demonstrated structural lack of overlap.
2. **Insufficient rare-outcome information:** In the n=350 rare-binary cohort, unpenalized inference completed only **149/1000** in A and **145/1000** in B. Most refusals came from the **outcome fitting** minimum-event rule or nonconvergence, not from treatment-support failure. Conditional coverage on those selected completed cases is not population-level reassurance.
3. **Quantitatively weak versus structurally absent overlap:** The weak-overlap SCM has probabilities strictly between 0 and 1 but low enough to violate the fixed fitted 0.015 safety threshold. Both methods refused 1000/1000 in every weak-overlap cell. Separately, a prespecified sign-strata probe rejected 400/400 datasets with actual deterministic treatment allocation and avoided declaring 400/400 well-populated stochastic controls to be causally identified.

**Neither regularization nor conservative propensity uncertainty bands are validated as a universal repair.** A fixed L2=1 propensity penalty marginally changes completion; the 16-site Bonferroni diagnostic is too conservative for automatic admission in this experiment, warning on approximately 60–62% of fold-level n=900 audits even though true propensity remains comfortably bounded. Such intervals are diagnostics on a *fixed grid of parameter predictions*, not a proof of positivity or ignorability over the full covariate domain.

## Frozen design and integrity

- Cohort A protocol SHA-256: `a390497393dbdfe9cdb092f0017318f28afd696e2664ec008e11693b4a188115`.
- Replication B (new seeds frozen after A results) SHA-256: `969031f6d35b250a1791481ff63792e312b0767d1a5f80360bc896bd51e1bbeb`. No estimator tuning, but this second cohort was **not blinded from the first cohort's findings**.
- Additional structural support probe protocol SHA-256: `c23f2f50790bb737bb3a546c7a269cbc434298e144754c152e7469668408941f` (post-primary, preregistered before *its own* seeds).
- Two distinct new 2-dimensional SCM outcome families, `moderate_nonlinear` and `moderate_rare_binary`; `weak_overlap` is a stress model, excluded from positive acceptance scoring.
- Six 1000-dataset cells in each cohort: n=350/900 crossed with three scenarios, giving **12,000 unique synthetic datasets**. These use a separate 2D generating process and seed ranges from G25C. Source exact hashes were frozen in the run manifests and reverified by the external auditor.
- 3 estimation methods per dataset: unpenalized cross-fitting, fixed L2=1 propensity regularization (no change to outcome regression or propensity guard), and privileged known-nuisance oracle (**not deployable**). **36,000 method-level receipts** total.
- Negative metadata controls: 300 explicit decisions per run, with duplicated deterministic control IDs across A/B (**300 unique metadata-only controls, not 600 independent samples**). Hidden-confounder and measurement-error refusals are trusted external design declarations, **not observational detection algorithms**.
- Added observed support study: 400 deterministic structural violations and 400 stochastic comparison datasets; it must not be confused with the original metadata-only cases.

## Cohort A primary results

All reported coverage is **conditional on completion**, with every refusal retained in the 1000-case denominator for completion. Oracle coverage is a scientific reference only.

| n | Scenario | Unpenalized completes | Ridge completes | Unpenalized CI coverage | Ridge CI coverage | Oracle CI coverage |
|---:|---|---:|---:|---:|---:|---:|
| 350 | moderate_nonlinear | 859/1000 | 899/1000 | 95.11% | 94.66% | 95.50% |
| 350 | moderate_rare_binary | 149/1000 | 155/1000 | 95.97% | 96.77% | 94.60% |
| 350 | weak_overlap | 0/1000 | 0/1000 | not scored | not scored | 95.90% |
| 900 | moderate_nonlinear | 987/1000 | 987/1000 | 95.04% | 94.93% | 95.80% |
| 900 | moderate_rare_binary | 953/1000 | 954/1000 | 94.54% | 94.65% | 94.30% |
| 900 | weak_overlap | 0/1000 | 0/1000 | not scored | not scored | 95.60% |

## Cohort B independent-seed replication

B uses different fixed seeds and was frozen before B was run, after the A outcome was known; comparisons are unchanged.

| n | Scenario | Unpenalized completes | Ridge completes | Unpenalized CI coverage | Ridge CI coverage | Oracle CI coverage |
|---:|---|---:|---:|---:|---:|---:|
| 350 | moderate_nonlinear | 882/1000 | 922/1000 | 94.22% | 94.90% | 94.60% |
| 350 | moderate_rare_binary | 145/1000 | 153/1000 | 93.10% | 92.16% | 93.40% |
| 350 | weak_overlap | 0/1000 | 0/1000 | not scored | not scored | 97.00% |
| 900 | moderate_nonlinear | 989/1000 | 990/1000 | 93.93% | 93.84% | 95.10% |
| 900 | moderate_rare_binary | 954/1000 | 955/1000 | 94.97% | 94.97% | 95.20% |
| 900 | weak_overlap | 0/1000 | 0/1000 | not scored | not scored | 95.40% |

## Refusal decomposition — primary A

| n | Scenario | Fitted method | Failure reasons and counts |
|---:|---|---|---|
| 350 | moderate_nonlinear | unpenalized_crossfit | estimated_positivity_guard: 141 |
| 350 | moderate_nonlinear | ridge1_crossfit | estimated_positivity_guard: 101 |
| 350 | moderate_rare_binary | unpenalized_crossfit | nuisance_fit_insufficient_binomial_events: 728, estimated_positivity_guard: 101, nuisance_fit_nonconverged_binomial_fit: 22 |
| 350 | moderate_rare_binary | ridge1_crossfit | nuisance_fit_insufficient_binomial_events: 748, estimated_positivity_guard: 75, nuisance_fit_nonconverged_binomial_fit: 22 |
| 350 | weak_overlap | unpenalized_crossfit | estimated_positivity_guard: 1000 |
| 350 | weak_overlap | ridge1_crossfit | estimated_positivity_guard: 1000 |
| 900 | moderate_nonlinear | unpenalized_crossfit | estimated_positivity_guard: 13 |
| 900 | moderate_nonlinear | ridge1_crossfit | estimated_positivity_guard: 13 |
| 900 | moderate_rare_binary | unpenalized_crossfit | nuisance_fit_insufficient_binomial_events: 30, estimated_positivity_guard: 14, nuisance_fit_nonconverged_binomial_fit: 3 |
| 900 | moderate_rare_binary | ridge1_crossfit | nuisance_fit_insufficient_binomial_events: 30, estimated_positivity_guard: 13, nuisance_fit_nonconverged_binomial_fit: 3 |
| 900 | weak_overlap | unpenalized_crossfit | estimated_positivity_guard: 1000 |
| 900 | weak_overlap | ridge1_crossfit | estimated_positivity_guard: 1000 |

The B cohort provides matching reason counts in `results/G25D_replication_summary.json`. Importantly, **n=900** rare-binary refusals are mostly outcome-model event-count / convergence failures, while **n=900** smooth Gaussian refusals are entirely fitted-propensity guard failures.

## Propensity-prediction uncertainty calibration

The unpenalized correctly specified propensity model uses a Fisher-information-based asymptotic prediction band over 16 fixed covariate sites, with Bonferroni protection *within each fitted fold*. Those grid intervals are not AIPW-effect confidence intervals, and their empirical validity requires correctly specified logistic nuisance models. Reporting is per fitted fold, not a percent of unique datasets.

| Cohort | n | Scenario | 16-site simultaneous true-logit coverage per fitted fold | Grid lower-bound < 0.015 warning rate per fitted fold |
|---|---:|---|---:|---:|
| A | 350 | moderate_nonlinear | 97.76% | 95.47% |
| A | 350 | moderate_rare_binary | 97.24% | 94.98% |
| A | 350 | weak_overlap | 96.42% | 100.00% |
| A | 900 | moderate_nonlinear | 96.54% | 61.53% |
| A | 900 | moderate_rare_binary | 97.12% | 60.50% |
| A | 900 | weak_overlap | 95.81% | 100.00% |
| B | 350 | moderate_nonlinear | 97.46% | 95.54% |
| B | 350 | moderate_rare_binary | 98.11% | 95.27% |
| B | 350 | weak_overlap | 95.74% | 100.00% |
| B | 900 | moderate_nonlinear | 95.54% | 62.37% |
| B | 900 | moderate_rare_binary | 96.11% | 62.32% |
| B | 900 | weak_overlap | 95.82% | 100.00% |

Although the grid bands achieve roughly nominal or conservative grid-wise truth containment in this correctly specified simulator, their lower bounds are overly cautious as *causal admission policies*. The fitted propensity refusal threshold must remain unchanged; **a warning does not rescue a refused case, and a reassuring band does not certify causal identification**.

## Observed support negative/positive-control probe (separate preregistered addendum)

The diagnostic partitions X1 into two predeclared sign strata and counts treatment/control observations in each bin:

- **Structural deterministic treatment:** X1 sign fully determines treatment. Zero cross-arm support occurs in each stratum; **400/400** direct empirical support contradictions produced `REFUSE_CAUSAL_CI` (200 at each sample size).
- **Moderate stochastic treatment:** Each sign group contained observations from both treatment arms; **400/400** produced `NO_BINNED_SUPPORT_CONTRADICTION_NOT_CERTIFIED`. This label means *no contradiction detected by this coarse test*, not observational proof of continuous-X positivity or no hidden confounding.
- Hidden confounding and measurement error still **cannot be detected from observational measurements alone**. Fail-closed labels for those conditions require trustworthy provenance or explicit identification assumptions; a model may instead report uncertainty about those assumptions.

## Research acceptance decisions

| Gate | Evidence | Outcome |
|---|---|---|
| 1000 attempts per model/scenario/n/cohort | 12 cells; exactly 12,000 distinct datasets | **PASS** |
| All negative structural checks refuse | 400/400 actual observed structural contradictions | **PASS for tested sign-strata designs only** |
| Positive completion ≥99% for n=900, each cohort | A smooth 987/1000 both; B smooth 989/1000 unpenalized, 990/1000 ridge; rare A 953–954; B 954–955 | **FAIL** |
| Positive conditional coverage ≥93% and nominal 95% included in Wilson 95% interval, at n=900 | All four n=900 positive-family model/cohort combinations per variant within screen; conditional on selection | **PASS as conditional research screen only** |
| Propensity uncertainty band valid for universal admission | Frequent warnings despite known moderate overlap | **FAIL / NOT JUSTIFIED** |
| Nuisance-aware variance with misspecification-valid CI derivation | No such CI derivation implemented | **NOT ESTABLISHED** |
| Independent causal-library CI comparison and direct Cognitum G9 regression | Not part of this standalone runner | **NOT TESTED** |
| Exact receipts, hashes, structural audit | 36,000 method receipts, 180 exact same-source estimator replays, no duplicate fixtures | **PASS** |
| Unit tests | 20/20 local unit tests | **PASS** |
| Independent source review and user approval for production change | Not requested/established | **NOT AUTHORIZED** |

## Interpretation of oracle results

The oracle uses e(X) and m_t(X) from the data-generating SCM. Numerical oracle coverage in the weak-overlap cohort **must never** be promoted to a usable inference result: finite numerical intervals are not permission to ignore a positivity guard. It serves solely to expose estimator/finite-sample behavior under privileged simulation knowledge.

## Outstanding G25 requirements and engineering handoff

1. **G25E — sparse binary outcomes.** Investigate penalized/Firth-like finite-sample outcome nuisance fits, event-poor folds, model fit diagnostics and robust rare-outcome inference with separate calibration cohorts. Avoid silent smoothing that hides no-event folds or identification failures.
2. **G25F — nuisance-aware CI derivation.** Develop a reviewed influence/stacked-equations variance derivation for stated nuisance classes or a valid refit/resampling policy that accounts for failures. Do not infer variance robustness from doubly robust point consistency.
3. **G25G — source equivalence and external benchmarks.** Verify against actual Cognitum G9 implementation and independent causal libraries; then larger, independently designed causal models, multiple covariates and model misspecification, controlled Monte Carlo precision, rollbacks and host authorization gates.
4. **No new production policy based on propensity prediction bands.** Preserve 0.015 threshold and all fail-closed refusals unless separately justified and explicitly approved.

## Local reproduction

Requires Python 3.13, NumPy, SciPy; no Lu, CVXPY, DoWhy, internet, Docker, elevation, CI, or live worker.

```bash
python -m unittest discover -s tests -v
python tools/audit_g25d.py                 # verifies both archived cohorts and replays 180 cases
python tools/g25d_support_probe.py          # deterministic support-control replay
python tools/run_g25d.py                    # cohort A; overwrites A receipts
python tools/run_g25d.py --config G25D_Replication_Predeclaration.json --output results/G25D_replication_receipts.json.gz --summary results/G25D_replication_summary.json
```

Reproduction requires re-running the primary with the same frozen config and code; GitHub is used only as source/repository/documentation, not the development environment.