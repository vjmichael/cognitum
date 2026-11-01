# Cognitum C14 G25F — Full-pipeline nuisance-refit uncertainty under sparse outcomes

**Date:** November 1, 2026  
**Scope:** Standalone Cognitum research; no production estimator or Lu source changes.  
**Milestone decision:** **FAIL / diagnostic research completed; G25 scientific acceptance remains open.**

## Executive result

- Two disjoint new synthetic cohorts (A/B), **2,000 datasets total** across 8 cohort/scenario/size cells, **6,000 primary method receipts**. The primary comparison is fixed-ridge outcome logistic versus Firth/FLIC with the SAME fitted propensity and 0.015 guard; truth oracle is strictly nondeployable.
- **13,662 complete-data bootstrap refits attempted, 1,448 invalid (10.60%)**. Among 160 prespecified bootstrap method/dataset selections, 22 initial fits refused, leaving **138 base-accepted combinations**. Only **21/138 (15.22%)** completed all **99** bootstrap resamples. Under the study rule, a single invalid resample invalidates the bootstrap interval; no resample is silently dropped.
- Conditional original IF coverage appears near nominal in many supported cells; refusals and the small sample rule prevent acceptance. **No general nuisance-aware variance formula is derived, and the bootstrap procedure is not certified** when sparse-event models are nonregular or resampling fails.
- Ten independent **analytic closed-form saturated two-group Jeffreys** tests, including complete separation, match the Firth coefficient optimizer with maximum absolute error below **7×10⁻⁷**; FLIC retains training event counts to numerical tolerance. This is **not a comparison with an external R package**.
- **30/30 local tests passed**, including three adversarial receipt-tampering cases. Cohort audits replayed **64 datasets / 192 complete estimator results**, verified all receipts and checked cross-cohort fixture hash uniqueness.

## Frozen design, true model and limitations

The two fresh nonlinear binary-outcome generators use independent 2-D uniform covariates on [-1.6, 1.6], one correctly specified nonlinear logistic treatment propensity, and scenario-specific arm-specific logistic outcomes. The population effect is integrated numerically using 72-point-per-axis Gauss–Legendre quadrature, rather than estimated from the outcome sample. True ATEs are approximately **0.0432344** (rare-shifted) and **0.0277358** (ultra-rare-sharp). On a 101×101 covariate grid, known propensity ranges **0.0961–0.7495**, indicating substantive generating-model overlap. The fitted propensity may still cross the operational 0.015 guard.

The primary cohorts have **250 seeds per cell**, below the G25 formal ≥1,000 independent datasets per cell. Each cohort uses a disjoint seed range; A seeds 880001–880250, B seeds 980001–980250. The same seed labels are used for n=350 and n=900 within a cohort, so inferential comparisons should account for shared-seed clustering, rather than naively pooling across sample sizes.

The bootstrap plan selected the **first 10 seeds in every cell**, before examining success, and attempted 99 independently seeded *paired-dataset* resamples per base-accepted method/dataset. Every resample reassigns cross-fitting folds and refits the treatment propensity and outcome regressions. The resampling mechanism is research-only; its finite-sample validity in the presence of prefit selection and sparse-event discontinuities has **not** been established.

**Source/protocol freezes:**
- Cohort A: protocol SHA-256 `3331a83d1148ff0d9a9ad820384814a2f54acdf6747a1679efc395b507b7556b`; primary receipt SHA-256 `cade174e81f3a85157b839127b8f313c0089a3edc60aee1ce1889f3e70bd1b61`; bootstrap receipt SHA-256 `a0a9771ebd646fe19c144ba06a1bdc8b22cec063184a675d8184c99fdcc7b465`.
- Cohort B: protocol SHA-256 `e3f9f589e566efcf28c88ec7a28980ad6491094a517a682b7d388a44f1a5ba2a`; primary receipt SHA-256 `0061f5192218517978bce01b73964d5c8ac85ab57e1911621aaf986078128c81`; bootstrap receipt SHA-256 `a86322a9606cd1e35da83a785bceb04765d510f701a158a1e6ed9f1fc6af71ad`.

**Operational deviation:** The original combined frozen driver repeatedly stalled between cells and was interrupted before completion. A separately hashed `tools/run_g25f_cell.py` was introduced *after* protocol freezing to run the exact frozen generator, estimator and bootstrap functions one cell per process, preserving all fixed settings and seeds. `tools/assemble_g25f.py` concatenated receipts, and the separate auditor independently replayed them. The replacement driver was not part of the original source freeze. Its SHA-256 is `96f44e1936c28b0ff0cdd54b016c0bbfb093c83fb3954dd158438e32df6cceff`. This evidence is **not externally preregistered**, and no unchanged-original-runner acceptance claim is made. Single-threaded BLAS was used for reliability; the complete root cause of combined-runner stalls remains unproven.

## Full primary held-out results — per cohort

| Cohort | Scenario | n | Outcome nuisance | Completed / 250 | Conditional CI coverage | Wilson 95% MC interval | IF SE / empirical SD | Refusal causes |
|---|---|---:|---|---:|---:|---|---:|---|
| A | Rare nonlinear shifted response | 350 | Fixed ridge outcome λ=1 | 220/250 | 95.91% | 92.4–97.8% | 1.017 | fitted_overlap_guard=19; zero_event_training_arm=11 |
| A | Rare nonlinear shifted response | 350 | Firth + FLIC | 220/250 | 95.00% | 91.3–97.2% | 1.013 | fitted_overlap_guard=19; zero_event_training_arm=11 |
| A | Rare nonlinear shifted response | 350 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 95.20% | 91.8–97.2% | 0.975 | none |
| A | Rare nonlinear shifted response | 900 | Fixed ridge outcome λ=1 | 249/250 | 97.19% | 94.3–98.6% | 1.026 | fitted_overlap_guard=1 |
| A | Rare nonlinear shifted response | 900 | Firth + FLIC | 249/250 | 96.79% | 93.8–98.4% | 1.019 | fitted_overlap_guard=1 |
| A | Rare nonlinear shifted response | 900 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 97.20% | 94.3–98.6% | 1.058 | none |
| A | Ultra-rare interaction response | 350 | Fixed ridge outcome λ=1 | 154/250 | 96.10% | 91.8–98.2% | 1.029 | fitted_overlap_guard=13; zero_event_training_arm=83 |
| A | Ultra-rare interaction response | 350 | Firth + FLIC | 154/250 | 96.10% | 91.8–98.2% | 1.029 | fitted_overlap_guard=13; zero_event_training_arm=83 |
| A | Ultra-rare interaction response | 350 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 96.40% | 93.3–98.1% | 1.013 | none |
| A | Ultra-rare interaction response | 900 | Fixed ridge outcome λ=1 | 242/250 | 94.21% | 90.5–96.5% | 0.940 | fitted_overlap_guard=1; zero_event_training_arm=7 |
| A | Ultra-rare interaction response | 900 | Firth + FLIC | 242/250 | 94.21% | 90.5–96.5% | 0.938 | fitted_overlap_guard=1; zero_event_training_arm=7 |
| A | Ultra-rare interaction response | 900 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 93.60% | 89.9–96.0% | 0.953 | none |
| B | Rare nonlinear shifted response | 350 | Fixed ridge outcome λ=1 | 234/250 | 95.30% | 91.8–97.4% | 1.043 | fitted_overlap_guard=8; zero_event_training_arm=8 |
| B | Rare nonlinear shifted response | 350 | Firth + FLIC | 234/250 | 95.30% | 91.8–97.4% | 0.856 | fitted_overlap_guard=8; zero_event_training_arm=8 |
| B | Rare nonlinear shifted response | 350 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 94.80% | 91.3–96.9% | 1.011 | none |
| B | Rare nonlinear shifted response | 900 | Fixed ridge outcome λ=1 | 250/250 | 95.60% | 92.3–97.5% | 0.970 | none |
| B | Rare nonlinear shifted response | 900 | Firth + FLIC | 250/250 | 95.20% | 91.8–97.2% | 0.964 | none |
| B | Rare nonlinear shifted response | 900 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 95.20% | 91.8–97.2% | 0.978 | none |
| B | Ultra-rare interaction response | 350 | Fixed ridge outcome λ=1 | 168/250 | 95.83% | 91.7–98.0% | 1.102 | fitted_overlap_guard=6; zero_event_training_arm=76 |
| B | Ultra-rare interaction response | 350 | Firth + FLIC | 168/250 | 95.83% | 91.7–98.0% | 0.816 | fitted_overlap_guard=6; zero_event_training_arm=76 |
| B | Ultra-rare interaction response | 350 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 94.80% | 91.3–96.9% | 0.988 | none |
| B | Ultra-rare interaction response | 900 | Fixed ridge outcome λ=1 | 243/250 | 95.47% | 92.1–97.5% | 0.970 | zero_event_training_arm=7 |
| B | Ultra-rare interaction response | 900 | Firth + FLIC | 243/250 | 94.24% | 90.6–96.5% | 0.951 | zero_event_training_arm=7 |
| B | Ultra-rare interaction response | 900 | Known-nuisance oracle (NONDEPLOYABLE) | 250/250 | 94.00% | 90.3–96.3% | 0.984 | none |

### Cross-cohort pooled research view (not independent approval)

| Scenario | n | Ridge completed | Ridge conditional coverage | Firth/FLIC completed | Firth/FLIC conditional coverage |
|---|---:|---:|---:|---:|---:|
| Rare nonlinear shifted response | 350 | 454/500 | 95.59% | 454/500 | 95.15% |
| Rare nonlinear shifted response | 900 | 499/500 | 96.39% | 499/500 | 95.99% |
| Ultra-rare interaction response | 350 | 322/500 | 95.96% | 322/500 | 95.96% |
| Ultra-rare interaction response | 900 | 485/500 | 94.85% | 485/500 | 94.23% |

**Interpretation:** These percentages are conditional on successful model fitting and are susceptible to selective-completion bias. A good-looking 95% conditional coverage cannot offset failure of the predefined ≥99% completion gate. At n=350 in ultra-rare cases, both candidate models fail on over one third of attempted datasets. Estimator-specific SE/empirical-SD ratios fluctuate substantially at this pilot size; no general factor correction or ranking is warranted.

## Full-pipeline bootstrap diagnostics

| Cohort | Scenario | n | Method | Baseline accepted / 10 | Complete 99/99 | Invalid bootstrap refits / attempted | Mean diagnostic bootstrap SE / IF SE* |
|---|---|---:|---|---:|---:|---:|---:|
| A | Rare nonlinear shifted response | 350 | Fixed ridge outcome λ=1 | 10/10 | 0 | 106/990 | 1.003 |
| A | Rare nonlinear shifted response | 350 | Firth + FLIC | 10/10 | 0 | 119/990 | 1.161 |
| A | Rare nonlinear shifted response | 900 | Fixed ridge outcome λ=1 | 10/10 | 4 | 17/990 | 1.034 |
| A | Rare nonlinear shifted response | 900 | Firth + FLIC | 10/10 | 3 | 10/990 | 0.986 |
| A | Ultra-rare interaction response | 350 | Fixed ridge outcome λ=1 | 8/10 | 0 | 220/792 | 1.043 |
| A | Ultra-rare interaction response | 350 | Firth + FLIC | 8/10 | 0 | 229/792 | 1.329 |
| A | Ultra-rare interaction response | 900 | Fixed ridge outcome λ=1 | 9/10 | 1 | 54/891 | 0.972 |
| A | Ultra-rare interaction response | 900 | Firth + FLIC | 9/10 | 1 | 29/891 | 0.989 |
| B | Rare nonlinear shifted response | 350 | Fixed ridge outcome λ=1 | 8/10 | 0 | 161/792 | 1.081 |
| B | Rare nonlinear shifted response | 350 | Firth + FLIC | 8/10 | 0 | 148/792 | 1.181 |
| B | Rare nonlinear shifted response | 900 | Fixed ridge outcome λ=1 | 10/10 | 4 | 9/990 | 1.025 |
| B | Rare nonlinear shifted response | 900 | Firth + FLIC | 10/10 | 5 | 13/990 | 1.055 |
| B | Ultra-rare interaction response | 350 | Fixed ridge outcome λ=1 | 4/10 | 0 | 118/396 | 1.093 |
| B | Ultra-rare interaction response | 350 | Firth + FLIC | 4/10 | 0 | 126/396 | 1.429 |
| B | Ultra-rare interaction response | 900 | Fixed ridge outcome λ=1 | 10/10 | 1 | 49/990 | 1.003 |
| B | Ultra-rare interaction response | 900 | Firth + FLIC | 10/10 | 2 | 40/990 | 1.053 |

*The mean SE ratio includes partially successful resampling runs with ≥2 accepted resamples. It is a descriptive statistic only: conditioning on successfully refitted resamples may bias it, and no automatic adjustment or valid interval follows. Only 21 baseline-accepted method/dataset combinations across both cohorts completed all 99 resamples, too few for a defensible method-level bootstrap coverage assessment.*

**Refusal taxonomy:** bootstrap failures are recorded as structural *information/policy* refusals (zero-event training arm), operational fitted-positivity guard, or typed numerical fitting errors. A zero-event training arm is not proof that outcome probabilities are exactly zero; it is a deliberately conservative confidence-admission rule. A finite penalized fit cannot supply missing causal assumptions. The nondeployable oracle is excluded from bootstrap candidate inference.

## Independent implementation and validity tests

- **Exact analytic Firth reference:** For two saturated binomial groups, the Jeffreys-penalized group estimates are `(events+0.5)/(group_n+1)`. Ten cases (including complete separation, low events, and high event rates) match the optimizer; maximum observed coefficient error 6.747e-07, FLIC predicted event-total calibration maximum error 6.210e-11. This is an independently derived *analytical* reference, not an external `logistf`/`brglm2` run.
- **No-event policy:** A treatment-arm training fold with zero outcomes is refused by both fitted methods, even though Firth may return a finite coefficient. The oracle can still return a value for simulation diagnosis, but is never a deployed estimator.
- **Audits:** cohort A 1000 distinct dataset hashes and 3000 methods; cohort B 1000 hashes and 3000 methods. Total 64 spot-replayed cases and 192 exact method outputs across early and late seeds in all cells; full accounting of 13662 refits. Cross-cohort fixture hashes unique.
- **Local regression:** 30 tests passed, including deliberate manipulation of coverage, method presence and bootstrap refusal taxonomy even after recalculating summary hashes; all were rejected by the auditor.
- **Environment:** Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0; Linux; no R binary available, no independent external Firth package run, no live Lu integration test. No Docker or additional downloads needed for these experiments.

## Acceptance decision — no production promotion

| Requirement | Finding | Decision |
|---|---|---|
| Frozen cohort and source identification, independent seeds | Two disjoint cohorts, source and protocol hashes, all receipts audited; post-freeze driver workaround explicitly disclosed | PASS (with documented deviation) |
| No drop of failed resamples | 13,662 attempted, 1,448 invalid; strict any-invalid refusal | PASS for accounting |
| Numerical validation of Firth | Exact saturated two-group formula and FLIC event-total calibration | PASS for analytic reference, NOT full external equivalence |
| ≥1,000 datasets per acceptance cell | 250 per cohort cell (500 pooled) | **NOT MET** |
| ≥99% completion on every positive cell | n=350 ultra-rare pooled 322/500 = 64.4%; multiple other failures | **FAIL** |
| General justified variance under estimated penalized nuisance | No complete asymptotic derivation or valid resampling theorem; refit failures common | **NOT ESTABLISHED** |
| Independent external Firth and production G9 equivalence | Not performed | **NOT ESTABLISHED** |
| All causal identification conditions and adverse negative controls | Known synthetic DGP and overlap only; hidden-confounding/measurement error outside this pilot | **NOT ESTABLISHED** |
| Separate explicit authorization for changing production Cognitum | No such authorization obtained or required for research | **NO CHANGE** |

## Recommended next tasks (G25G)

1. Derive/check the first-order influence contribution from estimated ridge/Firth/FLIC nuisance fitting for the supported model classes, accounting for cross-fitting and refit selection; **do not** assert generic double-robust confidence intervals under arbitrary nuisance misspecification.
2. Examine alternative resampling schemes *as independent research* (stratified-by-treatment/outcome bootstrap, m-out-of-n, subsampling) and justify whether their conditioning changes the sampling target. Report all attempted cases and intervals. Do not silently convert missing-event cases into a pseudo-population.
3. Obtain actual external R `logistf`/`brglm2` equivalence or independent audited implementation and real Cognitum G9 source parity before any algorithm proposal. Current tests establish analytical saturated-model correctness only.
4. Repeat larger independent holdouts (≥1,000 per acceptance cell) across more mechanism families, and explicitly test hidden confounding, measurement error, structural overlap violation and rare outcomes. Preserve refusal as a valid outcome, rather than forcing a confidence interval.
5. Require independent review, test receipts, failure budgets and a rollback plan; no release of production estimator changes without separate user approval.

## References and reproduction

- Puhr et al. (2017), *Firth’s logistic regression with rare events: accurate effect estimates and predictions?* DOI: https://doi.org/10.1002/sim.7273 (Firth prediction shrinkage and intercept correction).
- R `brglm2` documentation: https://search.r-project.org/CRAN/refmans/brglm2/html/brglmFit.html (adjusted-score and Jeffreys-penalty references; **not run in this environment**).
- R `logistf` FLIC documentation: https://search.r-project.org/CRAN/refmans/logistf/html/flic.html (**not run**).

```bash
cd Cognitum_C14_G25F_2026-11-01
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=tools
python -m unittest discover -s tests -v
python tools/independent_firth_check.py
python tools/audit_g25f.py G25F_Cohort_A_Frozen_Protocol.json
python tools/audit_g25f.py G25F_Cohort_B_Frozen_Protocol.json
# To regenerate a cell (writes new receipts in results/cells):
python tools/run_g25f_cell.py G25F_Cohort_A_Frozen_Protocol.json rare_shifted 350
# Regenerate all eight cell outputs before calling:
python tools/assemble_g25f.py
```

All scientific receipts are synthetic. They contain no actual medical or personal records. Every test/source is independent of the production Cognitum estimator and Lu application. GitHub is a repository and documentation record, not the development runtime.