# Cognitum C14 G25G — Stacked nuisance-score variance and sparse-event full-refit bootstrap

**Date:** November 1, 2026  |  **Status:** Completed research and numerical auditing. **NO production promotion**.  \
**Scope:** Standalone Cognitum C14 research package. No changes to Cognitum production source, Lu, its native tools, or Windows/Linux code. GitHub stores documentation only.

## Executive conclusion

- A mathematically motivated **two-fold cross-fit stacked-score influence-function correction** modestly widened confidence intervals in 5,600 fresh datasets from three cohorts. The separately preregistered, **post-pilot** 1,000-per-cell confirmation showed observed 95% coverage from 94.0% to 94.5% (misspecified propensity, n=900), and from 94.1% to 95.1% (n=1800). Under correctly specified propensity it moved 94.9% to 95.5% (n=900) and 94.7% to 95.4% (n=1800).
- This **does not establish superiority**: there were no newly uncovered cases among the 4,000 confirmation datasets; changes in coverage came from generally wider intervals, not proof of uniformly better variance calibration. The correction may be overconservative or underconservative on other data-generating processes. The limited parametric generator did not cover hidden confounding, weak positivity or doubly misspecified nuisance models.
- The positive-weight, full-refit sensitivity bootstrap preserved original observed event support and avoided event-free *bootstrap resamples* in this pilot, but retained many fitted-overlap refusals. Of 62 accepted baseline method/dataset combinations, **24** completed all 49 positive-weight refits, versus **14** for standard paired resampling. A 49-resample percentile interval is a coarse diagnostic, **not production-validated**.
- A separate QR-based Jeffreys information implementation with L-BFGS-B optimization matched the G25E BFGS Firth logistic fit in 32 multivariable datasets; external R `logistf` or `brglm2` equivalence has **not** been demonstrated because R is unavailable in the local runtime.

## Predeclaration and exact research boundaries

- `G25G_Frozen_A.json` SHA-256 `ad9cb83fd0b39bc36d9a870c199f508a0da4ba7373bd2f2033e27dfc75e6c148`
- `G25G_Frozen_B.json` SHA-256 `00e8e8bfc6b28b95de794077ead5fb5982482471c0f7c67c7e64449cfb710bc3`
- `G25G_Confirmation_C_Frozen.json` SHA-256 `592812b3f8b2c8f7de7d001e1fe6fc93b66cd267c54ca778d39b188682dde709`

A and B each predeclared 200 independent datasets per scenario/sample-size cell, for 1,600 total, plus four sparse cases per cell and method for two complementary full-refit bootstraps. C was **newly and prospectively frozen after** A/B results and before running its 4,000 independent seed fixtures (1,000 per cell); it is a separate confirmation stage, not retroactively part of A/B preregistration. All seeds and source checksums are in the JSON protocols. Resample cutoff of 49 is for mechanism diagnostics, not accurate bootstrap percentiles.

## Derivation — two-fold cross-fit parametric nuisance correction

For a subject with observed treatment `t`, response `y`, fitted propensity `e(x)` and outcome means `m1(x),m0(x)`, the AIPW score is:

`psi = m1-m0 + t*(y-m1)/e - (1-t)*(y-m0)/(1-e)`.

Let training fold `k` fit finite-dimensional logistic nuisance parameters by score equations `S`, with negative mean Hessian/information `I_k`; validation fold `j` evaluates `psi`, with its mean gradient `A_j = average(d psi_j / d beta_k)`. Taylor expansion gives this exploratory, subject-level first-order correction for `i` in training fold `k`:

`IF_adjusted_i = psi_i + (n_validation/n_training) * A_validation * inverse(I_training) * S_i`.

The standard error is `sd(IF_adjusted, ddof=1)/sqrt(n)`, centered at the **unchanged original cross-fit AIPW point estimate**. Under correct nuisance models, the *population* A terms vanish and the first-order extra term disappears asymptotically. When a nuisance working model is misspecified, its estimation may contribute first-order uncertainty not captured by a naive, fixed-score variance. Estimating these gradients in finite samples can itself add noise. No general regularity proof for all required C14 nuisance classes has been completed. This is NOT a variance derivation for Firth/FLIC, nonsmooth refusal selection, ML nuisances, or invalid identification.

Finite-difference unit tests verified all three analytic gradient blocks for propensity, untreated outcome and treated outcome. Information matrices are fold-specific; no unregularized inverse is applied when their estimated condition number exceeds the fixed guard.

## Independent held-out confirmation C (1,000 datasets per cell)

| Generator | N | Naive coverage | Stacked coverage | Oracle coverage | Mean stacked/naive width | Paired coverage difference (pp; exploratory 95% CI) |
|---|---:|---:|---:|---:|---:|---|
| correct_propensity | 900 | 94.9% | 95.5% | 94.4% | 1.071× | +0.6 (+0.2 to +1.1) |
| correct_propensity | 1800 | 94.7% | 95.4% | 94.8% | 1.035× | +0.7 (+0.2 to +1.3) |
| pooled_propensity | 900 | 94.0% | 94.5% | 94.2% | 1.032× | +0.5 (+0.1 to +1.0) |
| pooled_propensity | 1800 | 94.1% | 95.1% | 94.9% | 1.025× | +1.0 (+0.4 to +1.6) |

All 4,000 C cases completed all three intervals. The oracle uses true nuisance functions and is not deployable. Differences above use unadjusted paired 10,000-resample coverage bootstrap across distinct datasets, not a multiplicity-corrected claim of method superiority. Wilson coverage intervals are saved separately per cell; nominal 95% lies within each confirmation cell interval.

**Why no promotion based on these numbers:** 1000 independent datasets per cell are adequate to sharpen *these four* cells, but not enough to validate other causal families, rare binary outcomes, weaker overlap, estimation failures, misspecification of both nuisance models, interval width/coverage tradeoffs, or selective refusal policies. The corrected CI is wider, and there was no newly-uncovered dataset in C; this alone is not proof of calibrated variance.

## A/B exploratory pilot (separate from post-pilot C)

| Cohort | Generator | N | Naive | Stacked | Oracle |
|---|---|---:|---:|---:|---:|
| A | correct_propensity | 900 | 94.5% | 95.5% | 94.5% |
| A | correct_propensity | 1800 | 94.5% | 94.5% | 93.0% |
| A | pooled_propensity | 900 | 92.0% | 93.5% | 94.5% |
| A | pooled_propensity | 1800 | 95.5% | 95.5% | 95.5% |
| B | correct_propensity | 900 | 93.5% | 95.0% | 94.5% |
| B | correct_propensity | 1800 | 95.5% | 96.0% | 95.5% |
| B | pooled_propensity | 900 | 96.0% | 97.0% | 95.5% |
| B | pooled_propensity | 1800 | 94.0% | 94.5% | 94.5% |

Each A/B cell contains 200 distinct new datasets, with no refusals. Because the sample-size, generator and seed cells have differing uncertainty, do not pool them into a single nominal-coverage claim.

## Sparse-case ordinary-pairs versus positive-weight full-refit bootstrap

| Evidence | Paired resampling | Positive exponential weights |
|---|---:|---:|
| Baseline-accepted method/dataset combinations | 62 | 62 |
| Attempted full refit resamples | 3,038 | 3,038 |
| Invalid resamples | 470 | 269 |
| Datasets with 49/49 valid refits | 14 | 24 |

**Refusal mechanisms, all draws accounted for:**
- Paired: `fitted_overlap_guard` 162, `numerical_solver_nonconvergence` 10, `zero_event_training_arm` 298.
- Positive-weight: `numerical_weighted_ridge_nonconvergence` 13, `weighted_fitted_overlap_guard` 256.

Pair bootstrap draws rows with replacement and regenerates folds, so rare-arm events may disappear. Positive exponential weights keep every originally observed row at positive weight while holding the original folds fixed; this avoids new empty-event folds *by construction*, but cannot manufacture events in an originally empty fold and cannot guarantee adequate effective information. Both approaches refit propensity and outcome nuisance parameters every resample. Weight-bootstrap methodology requires separate theoretical justification under these sparse selection/refusal rules, and 49 draws are far too few for reliable tail calibration. Resampled failures are **never discarded** for an admitted CI: if any of the B draws fails, its bootstrap interval is refused. Any partial percentile is tagged diagnostic only.

## Firth implementation check and limitations

The QR-information, L-BFGS-B implementation agrees with the earlier BFGS Firth optimizer on **32** independent multivariable synthetic cases. Maximum coefficient difference: `5.94327338e-07`; maximum FLIC event-total residual: `1.54560809e-11`. This confirms two independent numerical strategies for the *same mathematical objective*, not equivalence with independent external Firth software. Neither the G25G stacked-score variance nor positive-weight bootstrap provides a validated Firth causal CI.

External primary methodological references:
- Puhr et al. (2017), *Firth’s logistic regression with rare events: accurate effect estimates and predictions?*, DOI `10.1002/sim.7273`, https://pubmed.ncbi.nlm.nih.gov/28295456/.
- Public R `logistf` FLIC documentation: https://search.r-project.org/CRAN/refmans/logistf/html/flic.html.
- Parametric double-robust sandwich variance research: https://pmc.ncbi.nlm.nih.gov/articles/PMC12050975/. These sources motivate the research design but are not an external validation of this specific cross-fit implementation.

## Audit and regression evidence

- G25G: **18/18 unit tests passed**, including gradient finite-difference tests, deterministic hashes, Firth independent checks, and malicious mutation checks for coverage, method presence, oracle labeling and bootstrap admission.
- G25F unchanged parent suite: **30/30 regression tests passed**.
- A/B: **1,600** generator-reverified primary fixtures, **80** exact primary-model replays. C: **4,000** generator-verified fixtures and **160** exact replays. All intervals have internally consistent coverage flags, widths, centers and nondeployable oracle labels.
- All **64** A/B bootstrap method/dataset summary receipts, totaling all 6,076 resample decisions across paired and positive-weight methods, were deterministically re-executed in two bounded cohorts; **64/64 exact matches**. They were not independently reimplemented by another statistical software package.
- Original G25F code copied into this standalone package byte-for-byte, with its relevant source hash still recorded in the A/B frozen manifests. GitHub has not been used as an execution or CI hub.

## Scientific acceptance decision — **FAIL / NO PROMOTION**

1. Stacked-score correction currently validated only as a research first-order approximation for finite-dimensional logistic nuisances with two-fold cross-fitting; general variance and identification assumptions remain incomplete.
2. Rare-outcome full-pipeline resampling still fails the all-valid bootstrap gate in most selected datasets. Positive-weight resampling is an interesting diagnostic but currently lacks independent CI calibration and cannot justify causal intervals on event-free source folds.
3. External R `logistf`/`brglm2` Firth/FLIC numerical equivalence remains unverified (R runtime unavailable).
4. More causal families with nonlinear/continuous outcomes, confounding and measurement-error negatives, weak overlap, additional nuisance working-model failures and full seed-independent ≥1,000/cell validation are required.
5. No production estimator change or Lu integration is authorized by G25G. A future production change requires explicit separate user approval plus reproducibility, independent code review, rollback and safety/refusal gates.

## Handoff — proposed G25H

Validate stacked correction against independently derived stacked estimating equations and finite-sample simulations with both nuisances misspecified; compare valid independent implementations in R. Explore smoothing/regularization or properly specified selective inference for sparse bootstrap failures without hiding refusals. Expand to real annotated benchmarks or realistic nonbinary outcomes and externally audited holdouts. Do not weaken the conversation-bound Lu native worker authorization rules while researching these numerical modules.

## Reproduction

`numpy`, `scipy`, `pytest` suffice for this isolated package; `statsmodels` is optional for additional cross-checks. On Linux, set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`. Run `python -m pytest -q tests`, `python tools/run_g25g.py --cohort A --mode primary` (and B), `python tools/run_g25g_confirmation.py`, `python tools/audit_g25g_confirmation.py`, and each bounded `python tools/replay_g25g_bootstrap.py --cohort A`/`B`. SHA-256 verification should precede new runs. `results/` contains the complete numeric receipts and audits. R package comparisons cannot be reproduced with this Python-only package.

**End of G25G isolated scientific report.**