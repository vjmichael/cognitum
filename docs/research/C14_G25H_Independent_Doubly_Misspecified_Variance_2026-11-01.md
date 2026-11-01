# Cognitum C14 G25H — Independent stacked-variance validation under joint nuisance misspecification

**Date:** November 1, 2026 (America/Phoenix)  
**Disposition:** G25H research validation and artifact audit COMPLETE; **C14 G25 scientific production promotion FAIL / NO CHANGE.**  
**Scope:** Standalone, reproducible Cognitum research. No Lu or Cognitum production algorithm modifications. GitHub is repository/provenance storage only.

## Executive findings

1. **Correct variance is not an unbiased causal estimate.** In the polynomial test with deliberately misspecified propensity **and** outcome nuisances, the n=1,800 AIPW estimate had a mean bias of about +0.052, despite reported-standard-error / empirical-sampling-SD ratios close to 1. Stacked variance raised or lowered interval width but did not remove this bias; the nominal 95% CI covered the true effect only around 36% of the time. In the more nonlinear oscillatory model, double-misspecification coverage was below 1% at n=1,800.
2. **A first-order stacked correction is numerically validated for the tested parametric score equations, not broadly statistically validated.** A separately assembled *global* two-fold estimating-equation Jacobian, computed with finite differences, matched 256 independently seeded test comparisons to high precision. That is internal mathematical replication, not external statistical-software verification.
3. **Fitted overlap guards do not establish causal identification.** The 0.015 propensity guard refused all 400 structural non-overlap and 400 extreme positive-overlap stress datasets in the post-primary probe. Every one of the 400 hidden-confounder datasets nevertheless produced numeric intervals in all four model variants. Those were research-quarantined using simulator-only knowledge; an operational policy cannot access the hidden confounder.
4. Some nominally favorable cells **overcover**, including a fully specified polynomial working model at n=900 where corrected coverage was around 96.2%; expanding intervals is not, by itself, evidence of correct uncertainty calibration.
5. External R `logistf`/`brglm2` Firth equivalence remains **NOT EXECUTED**: this local runtime has no `Rscript`. The unchanged QR/BFGS cross-check passes, but the two Python solvers share the same Jeffreys-information objective.

## Protocol and cohort provenance

- Cohorts A and B: two separately SHA-256-frozen protocols, each with **4,000 independent datasets** (2 families × 2 sample sizes × 1,000 seeds); **8,000 unique primary datasets** and **32,000 nuisance-variant attempts** overall. Each accepted fit produces both original score-only and corrected stacked CIs, plus a synthetic nondeployable oracle for research; no refusal is dropped from the denominator.
- Held-out seed ranges are disjoint across A/B, G25G, and the G25H discovery/development seeds. The polynomial family is generated from the six-column design, while the oscillatory family contains sine terms that are omitted even from the full working basis. Therefore the frozen label `both_correct_working` is literally correctly specified **only in the polynomial family**; do not interpret it as true for oscillatory.
- Four fixed working-model specifications are evaluated on each identical dataset: full/full, linear propensity/full outcome, full propensity/linear outcome, and linear/linear. Cross-fitting is two-fold; propensity fit, conditional-outcome fit, fitted overlap threshold of **0.015**, and all numerical guards are frozen. This G25H validation does not alter any C14 production nuisance or inference code.
- Post-primary sentinel program: **separately frozen after** seeing primary A/B results, **before** running its own disjoint fresh seeds. 3 high-risk conditions × 2 sizes × 200 = **1,200 independent stress fixtures**. Its early harness crash from an undefined synthetic oracle at structural zero propensity was corrected and fully documented *before the first successful result*. Both manifest versions are retained. Only observed numerical-return status—not invalid causal CI endpoints—is saved.

### Frozen source and manifest hashes

- `G25H_Frozen_A.json` SHA-256 `65deb3ddd067d7915401d8f80b7c16908678b3712c9f963a0da0352eecf7b72e`
- `G25H_Frozen_B.json` SHA-256 `518766c6584cca67c027d2885abf657e911563077c105f59da319eee113acf2c`
- `G25H_Observed_Sentinel_Frozen_PRE_FIX.json` SHA-256 `2f9c2d37123bf808aed8a64ab7dbc4e603d9aa853fd56459fed2e8e583f9925f`
- `G25H_Observed_Sentinel_Frozen.json` SHA-256 `8e2cd346bf7feac543a6c1f3c09a1e4148ee231bc314af5a7420c1d746975ece`
- `tools/g25h_core.py` SHA-256 `958c7217d3d07e38474a7a877a79bc3bc477b2317abfb37a3edf714916bedbd7`
- `tools/g25h_independent_if.py` SHA-256 `d53350f08a4f00ed4210afafa26c74af4038589c0b99ac1192ac2f627db71b5d`
- `tools/run_g25h.py` SHA-256 `4904092e78072a6d1ee80379a664b0f91fda5811d58986dd0bd222bc1eedb895`
- `tools/audit_g25h.py` SHA-256 `806a3bbc2a89094153b4bdc5f67897a859976b42a90f72a1fd9ef9c76940ce4c`
- `tools/g25h_observed_sentinels.py` SHA-256 `e45ecb5e130b81789796d0dfe792914f771809a31674557429ba510fe4f61615`

## Final A+B combined primary results (2,000 attempts per family × n cell)

Coverage is **conditional on fitting acceptance** and compared with known synthetic true ATE. The fixed primary study has 1,000 **per cohort cell**; this pooled description is supplementary to the separate cohort records.

| True family | N | Fitted working specification | Completed / 2,000 | Score-only coverage | Stacked coverage | Signed bias | Stacked SE / empirical SD | G25H research screen |
|---|---:|---|---:|---:|---:|---:|---:|---|
| polynomial | 900 | full propensity / full outcome | 1998/2000 | 95.05% | 96.20% | -0.0001 | 1.077 | FAIL |
| polynomial | 900 | linear propensity / full outcome | 2000/2000 | 94.70% | 95.50% | +0.0003 | 1.037 | PASS |
| polynomial | 900 | full propensity / linear outcome | 1998/2000 | 96.00% | 96.45% | -0.0052 | 1.065 | FAIL |
| polynomial | 900 | linear propensity / linear outcome | 2000/2000 | 63.45% | 64.65% | +0.0526 | 1.048 | FAIL |
| polynomial | 1800 | full propensity / full outcome | 2000/2000 | 94.85% | 95.75% | -0.0003 | 1.034 | PASS |
| polynomial | 1800 | linear propensity / full outcome | 2000/2000 | 94.90% | 95.40% | -0.0001 | 1.018 | PASS |
| polynomial | 1800 | full propensity / linear outcome | 2000/2000 | 96.05% | 95.55% | -0.0026 | 1.026 | PASS |
| polynomial | 1800 | linear propensity / linear outcome | 2000/2000 | 36.00% | 35.95% | +0.0518 | 1.022 | FAIL |
| oscillatory | 900 | full propensity / full outcome | 1942/2000 | 93.46% | 95.67% | +0.0086 | 1.073 | FAIL |
| oscillatory | 900 | linear propensity / full outcome | 2000/2000 | 92.15% | 93.85% | +0.0094 | 1.023 | FAIL |
| oscillatory | 900 | full propensity / linear outcome | 1942/2000 | 96.50% | 96.86% | -0.0055 | 1.081 | FAIL |
| oscillatory | 900 | linear propensity / linear outcome | 2000/2000 | 14.65% | 15.95% | +0.0984 | 1.033 | FAIL |
| oscillatory | 1800 | full propensity / full outcome | 1997/2000 | 93.14% | 94.39% | +0.0082 | 1.030 | PASS |
| oscillatory | 1800 | linear propensity / full outcome | 2000/2000 | 92.10% | 93.25% | +0.0091 | 1.009 | FAIL |
| oscillatory | 1800 | full propensity / linear outcome | 1997/2000 | 97.05% | 95.99% | -0.0003 | 1.047 | FAIL |
| oscillatory | 1800 | linear propensity / linear outcome | 2000/2000 | 0.80% | 0.85% | +0.0973 | 1.004 | FAIL |

**Predeclared research screen** per individual cohort cell: at least 99% completion; stacked coverage ≥93% with 95% contained in its Wilson 95% interval; |signed bias| ≤0.015; mean reported stacked SE/empirical estimator SD in [0.9, 1.1]; zero negative causal admissions. The table above displays pooled A+B descriptive checks using the same criteria; original preregistered cohort-by-cohort decisions are not replaced. Even every cell passing would not automatically authorize production.

### Paired interval changes, on accepted matched datasets

| True family | N | Model | Newly covered | Lost coverage | Paired difference (percentage points) |
|---|---:|---|---:|---:|---:|
| polynomial | 900 | full propensity / full outcome | 23 | 0 | +1.15 |
| polynomial | 900 | linear propensity / linear outcome | 26 | 2 | +1.20 |
| polynomial | 1800 | full propensity / full outcome | 18 | 0 | +0.90 |
| polynomial | 1800 | linear propensity / linear outcome | 7 | 8 | -0.05 |
| oscillatory | 900 | full propensity / full outcome | 43 | 0 | +2.21 |
| oscillatory | 900 | linear propensity / linear outcome | 26 | 0 | +1.30 |
| oscillatory | 1800 | full propensity / full outcome | 25 | 0 | +1.25 |
| oscillatory | 1800 | linear propensity / linear outcome | 1 | 0 | +0.05 |

The per-dataset paired comparisons and unadjusted confidence intervals/McNemar exploratory tests are saved in `results/G25H_AB_combined_analysis.json`. Do not read these multiple comparisons as superiority evidence without multiplicity correction and wider family holdouts.

### Refusal accounting

- polynomial / n=900: full/full fit completed **1998/2000**, refused **2**; refusal counts `{"fitted_overlap_guard": 2}`.
- polynomial / n=1800: full/full fit completed **2000/2000**, refused **0**; refusal counts `{}`.
- oscillatory / n=900: full/full fit completed **1942/2000**, refused **58**; refusal counts `{"fitted_overlap_guard": 58}`.
- oscillatory / n=1800: full/full fit completed **1997/2000**, refused **3**; refusal counts `{"fitted_overlap_guard": 3}`.

The fitted propensity threshold can produce research refusals even when generating propensities are bounded away from zero; this is not proof of structural positivity failure. All methods were tracked using attempted denominators. Oracle is nondeployable.

## High-risk observed-data stress results (post-primary, separately frozen)

| Case | N | Datasets | Numerical returns, full/full | Numerical returns, linear/linear | Causal CIs admitted |
|---|---:|---:|---:|---:|---:|
| structural_no_overlap | 900 | 200 | 0 | 0 | 0 |
| structural_no_overlap | 1800 | 200 | 0 | 0 | 0 |
| near_zero_propensity | 900 | 200 | 0 | 0 | 0 |
| near_zero_propensity | 1800 | 200 | 0 | 0 | 0 |
| latent_confounder | 900 | 200 | 200 | 200 | 0 |
| latent_confounder | 1800 | 200 | 200 | 200 | 0 |

In all observed-data stress fixtures, all four variants had the same broad pattern: no numerical returns for the constructed structural-zero or near-zero families, and **200/200** numerical returns at each n for hidden confounding. **This cannot be a deployment-side hidden-confounding detector.** The simulator quarantines invalid labels based on inaccessible ground truth. A fitted statistical model does not establish ignorability; sensitivity analysis, identification assumptions, design evidence and explicit uncertainty/refusal policies remain necessary.

### Sentinel harness correction and audit

- At structural probability zero the normal synthetic *oracle* is undefined. The initial sentinel runner terminated before recording results; after a recorded pre-result source correction, a temporary clipped e is used **only** to evaluate and discard that unusable oracle. The fitted models still receive identical x, treatment, outcome, fold assignments and original 0.015 guard; the *actual* generating e is recorded unchanged. See `G25H_Observed_Sentinel_Deviation.md` and original/updated manifests.
- Sentinel auditor checked **1,200 unique** case receipts, all **4,800** numerical-return flags, all zero causal admissions, and **72 exact replays**. It also verified that raw invalid confidence intervals and synthetic oracle values were not emitted.

## Mathematical validation of the two-fold stacked correction

Cross-fitted AIPW uses `psi_i = m1(Xi)-m0(Xi) + Ti(Yi-m1)/e(Xi) - (1-Ti)(Yi-m0)/(1-e(Xi))`. Its score-only SE treats cross-fitted score variation as the primary influence. The two-fold parametric stacked correction adjusts training-observation IFs by `(n_val/n_train) * A_val * I_train^{-1} S_train`, where `A_val` is the validation-score derivative with respect to the training nuisance parameters, `I_train` is training information, and `S_train` are the fitted nuisance estimating scores.
An independent **global** estimating equation is assembled as `G_i(theta) = (psi_i - mu, 1[i in train_1]*S_i(beta_1), 1[i in train_2]*S_i(beta_2))`. Its Jacobian is obtained by central finite differences of held-out AIPW means and training logistic scores. The influence is `-e_mu^T J^{-1} G_i`. This tests the block structure and fold normalization independently of the G25H analytic derivative/information expressions.

- **256 independent numerical Jacobian comparisons:** maximum absolute IF deviation `5.43e-10` and maximum reported-SE deviation `2.96e-13`. Both meet strict numerical tolerances.
- **32** separate QR-information Firth/BFGS cross-check cases: max coefficient deviation `5.94e-07`. This reproduces prior in-house independent-optimizer checks, **not** official R `logistf`/`brglm2` equivalence.
- Mathematical agreement between finite differences and closed-form Jacobian **does not imply** unbiased ATE, overlap/ignorability validity, finite-sample nominal coverage, or correctness under arbitrary nuisance fitting algorithms.

## Audit and regression totals

- G25H primary: A **4000** / B **4000** unique receipts; A/B **32000** variant attempts; **192** exact complete-case replays. Both audits **PASS**.
- G25H initial simulator-labeled negative controls: A/B **1200**; these are quarantined status cases, not actual observed-data diagnostics.
- Separate observed-data sentinels: **1200** dataset receipts, **4800** fitted-method status records, **72** exact sentinel replays; audit **PASS**.
- G25H current tests **16/16 passed**; unchanged G25G parent regressions **18/18 passed**. Synthetic holdouts and internal replays do not replace independent external adjudication.

## Scientific acceptance decision — FAIL / NO PRODUCTION PROMOTION

1. Both nuisance working models can be wrong. G25H directly demonstrates substantial point-estimate bias; no variance adjustment can make an inconsistent point estimate causally trustworthy.
2. The scope is two-fold, finite-dimensional logistic working models; no general theorem for Firth/FLIC, flexible machine learning, nonbinary outcomes, model-selection/refusal bias, or real observational data was established.
3. Several positive cells fail completion, calibration-compatibility or bias screens. Correct-model settings can also show overcoverage; do not promote a method because a wider interval captures more synthetic true effects.
4. The observed overlap guard correctly refuses tested extreme-support fixtures but silently returns numerical estimates on every simulated hidden-confounder fixture. Admission by a simulator label is not operational identification. Never claim an automatic unmeasured-confounding detector.
5. R `logistf`/`brglm2` equivalence remains unverified (`Rscript` absent). Existing QR checks are only an independent numerical implementation of the same objective.
6. Separate independent code review, external software comparison, real annotated data, uncertainty derivation beyond tested parametric nuisances, explicit approval and rollback would be required before *any* Cognitum production change. Lu is not modified and Cognitum remains an optional independent add-on.

## Next step (G25I proposal)

Study **identification-aware C14 capability refusal**, formal uncertainty and sensitivity under unobserved confounding, nuisance-model diagnostics, explicit model-selection uncertainty, and (if dependencies become available) R `logistf`/`brglm2` cross-language numerical equivalence. A broader DAG-based real-world benchmark and independent statistical review should precede any production adoption.

## Reproduction

Environment: CPython 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2 (statsmodels 0.14.6 present; R unavailable). Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`, and `PYTHONPATH=tools` at the package root. Verify `SHA256SUMS.json`, then run:

```sh
python tools/run_g25h.py A
python tools/run_g25h.py B
python tools/audit_g25h.py A
python tools/audit_g25h.py B
python tools/g25h_combine.py
python tools/g25h_observed_sentinels.py
python tools/audit_g25h_sentinels.py
python tools/verify_g25h_independent.py
pytest -q tests
```

The raw receipts, complete independent/structural audits, exact replay counts, packed ZIP hashes, frozen manifests and source are included in the companion package.

### Methodological references

- Double robust variance estimation with parametric working models (Biometrics, 2025): https://pmc.ncbi.nlm.nih.gov/articles/PMC12050975/. The publication examines IF, empirical sandwich and bootstrap variance for parametric working models, and does not itself validate this G25H cross-fit implementation.
- `logistf` Firth/FLIC official CRAN documentation: https://search.r-project.org/CRAN/refmans/logistf/html/logistf.html.
- `brglm2` adjusted-score GLM fitting documentation: https://search.r-project.org/CRAN/refmans/brglm2/html/brglmFit.html.

**End of isolated G25H engineering report.**