# Cognitum C14 G25E — Sparse binary outcome fitting and held-out causal interval calibration

**Date:** 2026-11-01 | **Scope:** Offline isolated research, no Cognitum production estimator or Lu modification. **Status:** Experimental investigation completed; G25 production inference NOT accepted.

## Executive conclusions

1. The preregistered twofold cross-fitting experiment distinguishes **zero-event training arms**, **one-to-three-event arms**, **estimated propensity-guard refusals**, and **numerical nonconvergence**. No-event arm cases are intentionally rejected for causal confidence intervals, even if the penalized logistic optimization returns finite coefficients. Zero events are not observational proof that positivity or exchangeability fails; this is a conservative information/admission policy.
2. Fixed ridge, Jeffreys-penalized Firth, and Firth-with-intercept-correction (FLIC) permit finite fits when there are 1–3 training-arm events, unlike the G25D-style ordinary MLE guard. All use the same correctly specified propensity fit and original 0.015 fitted guard.
3. **Firth is not universally more accurate:** FLIC can alleviate Firth predicted-probability shrinkage toward 1/2; ridge may have lower nuisance RMSE in these simulations. More completed datasets do not establish correct interval coverage across *all attempts*.
4. Reported interval coverage is conditional on successful nuisance fits, subject to nonrandom selection. Ordinary influence-function score SE is used for research; no nuisance-aware variance derivation, general finite-sample guarantee, or production approval follows.
5. The oracle uses generating e(X), m_t(X) and is explicitly **NONDEPLOYABLE**. Exact-replay scientific receipts and independent numerical checks do not establish actual Cognitum G9 code equivalence or cross-library Firth implementation equivalence.

## Frozen design and provenance

- A protocol SHA-256: `b8fa98ec57e97f3a59c456eacf212d0cc50ced351fb10f23a34095edc2137613`; B protocol SHA-256: `3bd8f8b498fc0c1d3d17f218e08e1105fdc146ff87f9f3f93256565859b393e4`.
- Frozen primary source SHA-256 (identical cohorts): `76db9a5c1454a5478eb340585111547c077c1aa791bc3a5e7c5ce9a457717e65`; B matches: `True`.
- Two new generators: **rare_curved** (roughly 4% untreated and 8% treated outcome rate), **ultrarare_interaction** (roughly 2% untreated and 4% treated); continuous two-covariate data, nonlinear treatment effect, smooth bounded propensity. New mechanisms and independent seeds relative to G25D.
- Exactly 1000 attempts per cell; two scenarios × n=350/900 × A/B = 8 cells = 8000 datasets. Five methods per fixture = 40000 method receipts. Within a cohort, n=350 and 900 reuse seed labels and are not guaranteed independent observations.
- All data, outcomes and truth are synthetic, and the known-nuisance oracle cannot be used in deployment. No real patient or user data.
- Freeze is documented by local source/config hashes; no claim of external timestamped preregistration or independent blinded source review.

## Completion and conditional 95% confidence-interval coverage

| Cohort | Scenario | n | Outcome nuisance fit | Completed | Conditional CI coverage | Wilson 95% interval | Mean CI width | Outcome RMSE vs oracle |
|---|---|---:|---|---:|---:|---|---:|---:|
| A | rare_curved | 350 | ML (G25D event guard) | 211/1000 | 93.84% | 89.75%–96.36% | 0.1297 | 0.0892 |
| A | rare_curved | 350 | Fixed ridge λ=1 | 925/1000 | 94.92% | 93.31%–96.16% | 0.1187 | 0.0582 |
| A | rare_curved | 350 | Firth Jeffreys | 925/1000 | 93.62% | 91.86%–95.02% | 0.1277 | 0.0880 |
| A | rare_curved | 350 | Firth + FLIC | 925/1000 | 93.95% | 92.22%–95.31% | 0.1232 | 0.0677 |
| A | rare_curved | 350 | Oracle (not deployable) | 1000/1000 | 95.10% | 93.58%–96.27% | 0.1039 | n/a |
| A | rare_curved | 900 | ML (G25D event guard) | 977/1000 | 94.06% | 92.40%–95.38% | 0.0676 | 0.0457 |
| A | rare_curved | 900 | Fixed ridge λ=1 | 1000/1000 | 94.10% | 92.46%–95.40% | 0.0673 | 0.0394 |
| A | rare_curved | 900 | Firth Jeffreys | 1000/1000 | 93.90% | 92.24%–95.22% | 0.0678 | 0.0482 |
| A | rare_curved | 900 | Firth + FLIC | 1000/1000 | 94.20% | 92.58%–95.49% | 0.0675 | 0.0420 |
| A | rare_curved | 900 | Oracle (not deployable) | 1000/1000 | 94.30% | 92.69%–95.57% | 0.0645 | n/a |
| A | ultrarare_interaction | 350 | ML (G25D event guard) | 3/1000 | 100.00% | 43.85%–100.00% | 0.1066 | 0.0833 |
| A | ultrarare_interaction | 350 | Fixed ridge λ=1 | 532/1000 | 94.92% | 92.72%–96.49% | 0.0834 | 0.0379 |
| A | ultrarare_interaction | 350 | Firth Jeffreys | 533/1000 | 94.18% | 91.86%–95.87% | 0.0983 | 0.0802 |
| A | ultrarare_interaction | 350 | Firth + FLIC | 533/1000 | 94.56% | 92.30%–96.19% | 0.0891 | 0.0485 |
| A | ultrarare_interaction | 350 | Oracle (not deployable) | 1000/1000 | 93.70% | 92.02%–95.05% | 0.0710 | n/a |
| A | ultrarare_interaction | 900 | ML (G25D event guard) | 291/1000 | 91.07% | 87.23%–93.83% | 0.0490 | 0.0383 |
| A | ultrarare_interaction | 900 | Fixed ridge λ=1 | 956/1000 | 94.14% | 92.47%–95.46% | 0.0459 | 0.0263 |
| A | ultrarare_interaction | 900 | Firth Jeffreys | 957/1000 | 94.78% | 93.18%–96.01% | 0.0469 | 0.0406 |
| A | ultrarare_interaction | 900 | Firth + FLIC | 957/1000 | 94.15% | 92.48%–95.47% | 0.0462 | 0.0300 |
| A | ultrarare_interaction | 900 | Oracle (not deployable) | 1000/1000 | 94.30% | 92.69%–95.57% | 0.0440 | n/a |
| B | rare_curved | 350 | ML (G25D event guard) | 224/1000 | 95.98% | 92.54%–97.87% | 0.1327 | 0.0938 |
| B | rare_curved | 350 | Fixed ridge λ=1 | 929/1000 | 95.48% | 93.95%–96.64% | 0.1171 | 0.0584 |
| B | rare_curved | 350 | Firth Jeffreys | 929/1000 | 95.05% | 93.46%–96.27% | 0.1262 | 0.0896 |
| B | rare_curved | 350 | Firth + FLIC | 929/1000 | 95.37% | 93.82%–96.55% | 0.1213 | 0.0690 |
| B | rare_curved | 350 | Oracle (not deployable) | 1000/1000 | 95.60% | 94.14%–96.71% | 0.1032 | n/a |
| B | rare_curved | 900 | ML (G25D event guard) | 974/1000 | 94.46% | 92.84%–95.73% | 0.0675 | 0.0455 |
| B | rare_curved | 900 | Fixed ridge λ=1 | 1000/1000 | 93.90% | 92.24%–95.22% | 0.0672 | 0.0392 |
| B | rare_curved | 900 | Firth Jeffreys | 1000/1000 | 94.00% | 92.35%–95.31% | 0.0678 | 0.0480 |
| B | rare_curved | 900 | Firth + FLIC | 1000/1000 | 94.00% | 92.35%–95.31% | 0.0675 | 0.0418 |
| B | rare_curved | 900 | Oracle (not deployable) | 1000/1000 | 94.90% | 93.36%–96.10% | 0.0644 | n/a |
| B | ultrarare_interaction | 350 | ML (G25D event guard) | 1/1000 | 100.00% | 20.65%–100.00% | 0.1301 | 0.0901 |
| B | ultrarare_interaction | 350 | Fixed ridge λ=1 | 559/1000 | 96.60% | 94.75%–97.81% | 0.0828 | 0.0385 |
| B | ultrarare_interaction | 350 | Firth Jeffreys | 560/1000 | 95.71% | 93.70%–97.10% | 0.0976 | 0.0825 |
| B | ultrarare_interaction | 350 | Firth + FLIC | 560/1000 | 95.71% | 93.70%–97.10% | 0.0881 | 0.0508 |
| B | ultrarare_interaction | 350 | Oracle (not deployable) | 1000/1000 | 96.10% | 94.71%–97.13% | 0.0700 | n/a |
| B | ultrarare_interaction | 900 | ML (G25D event guard) | 290/1000 | 94.48% | 91.23%–96.58% | 0.0491 | 0.0388 |
| B | ultrarare_interaction | 900 | Fixed ridge λ=1 | 946/1000 | 95.14% | 93.57%–96.33% | 0.0456 | 0.0261 |
| B | ultrarare_interaction | 900 | Firth Jeffreys | 946/1000 | 94.82% | 93.22%–96.06% | 0.0467 | 0.0403 |
| B | ultrarare_interaction | 900 | Firth + FLIC | 946/1000 | 94.93% | 93.34%–96.15% | 0.0460 | 0.0297 |
| B | ultrarare_interaction | 900 | Oracle (not deployable) | 1000/1000 | 95.40% | 93.92%–96.53% | 0.0438 | n/a |

The 95% Wilson interval here quantifies Monte Carlo uncertainty in **the fraction covered among completed datasets**. It cannot correct selection bias caused by refusing difficult cases. An apparent 100% with only three successful fits is statistically uninformative and cannot pass the required 99% completion screen.

## Failure taxonomy — primary complete cohorts

| Cohort | Scenario | n | Fit | Zero-event refusals | Low-event refusals | Numerical solver refusals | Fitted propensity guard |
|---|---|---:|---|---:|---:|---:|---:|
| A | rare_curved | 350 | ML (G25D event guard) | 44 | 723 | 16 | 6 |
| A | rare_curved | 350 | Fixed ridge λ=1 | 44 | 0 | 0 | 31 |
| A | rare_curved | 350 | Firth Jeffreys | 44 | 0 | 0 | 31 |
| A | rare_curved | 350 | Firth + FLIC | 44 | 0 | 0 | 31 |
| A | rare_curved | 900 | ML (G25D event guard) | 0 | 21 | 2 | 0 |
| A | rare_curved | 900 | Fixed ridge λ=1 | 0 | 0 | 0 | 0 |
| A | rare_curved | 900 | Firth Jeffreys | 0 | 0 | 0 | 0 |
| A | rare_curved | 900 | Firth + FLIC | 0 | 0 | 0 | 0 |
| A | ultrarare_interaction | 350 | ML (G25D event guard) | 449 | 548 | 0 | 0 |
| A | ultrarare_interaction | 350 | Fixed ridge λ=1 | 449 | 0 | 1 | 18 |
| A | ultrarare_interaction | 350 | Firth Jeffreys | 449 | 0 | 0 | 18 |
| A | ultrarare_interaction | 350 | Firth + FLIC | 449 | 0 | 0 | 18 |
| A | ultrarare_interaction | 900 | ML (G25D event guard) | 43 | 659 | 7 | 0 |
| A | ultrarare_interaction | 900 | Fixed ridge λ=1 | 43 | 0 | 1 | 0 |
| A | ultrarare_interaction | 900 | Firth Jeffreys | 43 | 0 | 0 | 0 |
| A | ultrarare_interaction | 900 | Firth + FLIC | 43 | 0 | 0 | 0 |
| B | rare_curved | 350 | ML (G25D event guard) | 40 | 710 | 17 | 9 |
| B | rare_curved | 350 | Fixed ridge λ=1 | 40 | 0 | 0 | 31 |
| B | rare_curved | 350 | Firth Jeffreys | 40 | 0 | 0 | 31 |
| B | rare_curved | 350 | Firth + FLIC | 40 | 0 | 0 | 31 |
| B | rare_curved | 900 | ML (G25D event guard) | 0 | 24 | 2 | 0 |
| B | rare_curved | 900 | Fixed ridge λ=1 | 0 | 0 | 0 | 0 |
| B | rare_curved | 900 | Firth Jeffreys | 0 | 0 | 0 | 0 |
| B | rare_curved | 900 | Firth + FLIC | 0 | 0 | 0 | 0 |
| B | ultrarare_interaction | 350 | ML (G25D event guard) | 424 | 575 | 0 | 0 |
| B | ultrarare_interaction | 350 | Fixed ridge λ=1 | 424 | 0 | 1 | 16 |
| B | ultrarare_interaction | 350 | Firth Jeffreys | 424 | 0 | 0 | 16 |
| B | ultrarare_interaction | 350 | Firth + FLIC | 424 | 0 | 0 | 16 |
| B | ultrarare_interaction | 900 | ML (G25D event guard) | 54 | 652 | 4 | 0 |
| B | ultrarare_interaction | 900 | Fixed ridge λ=1 | 54 | 0 | 0 | 0 |
| B | ultrarare_interaction | 900 | Firth Jeffreys | 54 | 0 | 0 | 0 |
| B | ultrarare_interaction | 900 | Firth + FLIC | 54 | 0 | 0 | 0 |

The classification order gives explicit priority to training-arm zero events, then the ordinary MLE under-four-event guard, then numerical and fitted-propensity checks. Every fold has independent event/nonevent diagnostics in the receipts regardless of the first-reported refusal reason. Neither a fitted e(X) below 0.015 nor a zero-event outcome arm proves structural violation of causal positivity; these are separate reasons to withhold a causal interval under this study policy.

## Pairwise accepted-case comparisons

The paired metrics are *only* for fixtures accepted by both ordinary logistic and the comparison method. They must not be extrapolated to all attempted datasets.

| Cohort | Scenario | n | Candidate | Newly completed vs ML | New refusals vs ML | Shared-accepted coverage difference (pp) |
|---|---|---:|---|---:|---:|---:|
| A | rare_curved | 350 | Firth + FLIC | 714 | 0 | +0.47 |
| A | rare_curved | 350 | Firth Jeffreys | 714 | 0 | +0.00 |
| A | rare_curved | 350 | Fixed ridge λ=1 | 714 | 0 | +1.42 |
| A | rare_curved | 900 | Firth + FLIC | 23 | 0 | +0.10 |
| A | rare_curved | 900 | Firth Jeffreys | 23 | 0 | -0.20 |
| A | rare_curved | 900 | Fixed ridge λ=1 | 23 | 0 | +0.00 |
| A | ultrarare_interaction | 350 | Firth + FLIC | 530 | 0 | +0.00 |
| A | ultrarare_interaction | 350 | Firth Jeffreys | 530 | 0 | +0.00 |
| A | ultrarare_interaction | 350 | Fixed ridge λ=1 | 529 | 0 | +0.00 |
| A | ultrarare_interaction | 900 | Firth + FLIC | 666 | 0 | -0.34 |
| A | ultrarare_interaction | 900 | Firth Jeffreys | 666 | 0 | +1.37 |
| A | ultrarare_interaction | 900 | Fixed ridge λ=1 | 665 | 0 | -0.69 |
| B | rare_curved | 350 | Firth + FLIC | 705 | 0 | -0.45 |
| B | rare_curved | 350 | Firth Jeffreys | 705 | 0 | -1.34 |
| B | rare_curved | 350 | Fixed ridge λ=1 | 705 | 0 | +0.00 |
| B | rare_curved | 900 | Firth + FLIC | 26 | 0 | +0.21 |
| B | rare_curved | 900 | Firth Jeffreys | 26 | 0 | +0.21 |
| B | rare_curved | 900 | Fixed ridge λ=1 | 26 | 0 | +0.10 |
| B | ultrarare_interaction | 350 | Firth + FLIC | 559 | 0 | +0.00 |
| B | ultrarare_interaction | 350 | Firth Jeffreys | 559 | 0 | +0.00 |
| B | ultrarare_interaction | 350 | Fixed ridge λ=1 | 558 | 0 | +0.00 |
| B | ultrarare_interaction | 900 | Firth + FLIC | 656 | 0 | +1.03 |
| B | ultrarare_interaction | 900 | Firth Jeffreys | 656 | 0 | +1.03 |
| B | ultrarare_interaction | 900 | Fixed ridge λ=1 | 656 | 0 | +1.03 |

## Local validation and provenance audit

- Full audit: **PASS**, 8000 distinct fixture hashes, 40000 full method receipts, 160 exact same-source case replays (800 method results); cross-cohort seed overlap 0.
- **1054 distinct datasets** had at least one event-free outcome training arm across both cohorts; these were conservatively refused by all fitted candidates. Counts include only datasets, not fold multiplicities.
- Independent `statsmodels` GLM comparison passed **88 checks** on 40 fixtures (ordinary and ridge slopes). Firth analytic-score vs numerical-gradient and independent finite-difference SciPy optimization comparison passed on **24 fixtures**. Independent external Firth package **NOT tested**.
- Local tests: see `results/G25E_unit_tests.txt`; the auditor has adversarial tests that reject missing methods and altered coverage flags.
- Environment: Python 3.13.5, Linux, NumPy/SciPy/statsmodels; no Docker, CVXPY, DoWhy, network or live Lu worker required.
- Receipt hashes: A `25cc2f440b7182f0b787c51a5868f4299478a6a358ddb6647b92439990bd5def`, B `1642ac59a1458cacbe799ba9eeb263590a948670610c179ba2698b9d25ede721`.

## Acceptance decisions — do not claim production readiness

| Gate | Decision |
|---|---|
| 1000 seeded attempts per scenario/sample-size/cohort | PASS |
| Exact independent receipt accounting, fail-closed no-event classification | PASS for tested scenarios |
| ≥99% method completion in **every** positive cell | **FAIL** |
| ≥93% conditional 95% CI coverage with 95% in Wilson 95% interval for every cell | **FAIL** |
| Structural positivity / hidden confounding / measurement error certificates | NOT ESTABLISHED; synthetic assumptions only |
| Valid AIPW CI under arbitrary model misspecification or sparse nuisance estimation | NOT ESTABLISHED |
| Independent external Firth-library equivalence | NOT TESTED |
| Direct Cognitum G9 production source equivalence | NOT TESTED |
| Separate user approval for production algorithm change | NOT AUTHORIZED |

## Scientific method references

- Puhr et al. (2017), *Firth’s logistic regression with rare events: accurate effect estimates and predictions?*, Statistics in Medicine, DOI: [10.1002/sim.7273](https://doi.org/10.1002/sim.7273) — Firth reduces coefficient bias; original Firth predicted probabilities can be biased toward 1/2; FLIC adjusts the intercept.
- FLIC concerns probability calibration of the outcome nuisance model and is not itself a guarantee of valid causal identification or AIPW confidence-interval coverage.
- Mansournia et al. (2018), *Separation in Logistic Regression: Causes, Consequences, and Control*, AJE, DOI: [10.1093/aje/kwx299](https://doi.org/10.1093/aje/kwx299) — penalized likelihood for separation, and caution over the difference between Wald and profile likelihood intervals.

## Next research work (G25F)

1. Review score-IF variance under *estimated* penalized nuisance models: finite-sample repeated-fitting coverage, conditional refusal policy, and nuisance-aware resampling with explicit invalid-resample accounting.
2. Verify Firth results against a truly independent implementation (e.g. R `brglm2` or an independently audited reference) and Cognitum G9 source; independently cross-check scenario generators and analytic ATE by quadrature.
3. Research (not silently enable) nonzero-event prior assumptions and rare-event prediction policies for true zero-event training folds, with conservative uncertainty, refusal disclosure and separate identification review.
4. Broaden beyond two-covariate simulated binary-outcome families, including misspecified response and propensity models, effect heterogeneity, and external causal-library comparisons, before any production change.

## Reproduction

```bash
python -m unittest discover -s tests -q
PYTHONPATH=tools python tools/independent_validation.py
PYTHONPATH=tools python tools/check_firth_numeric.py
PYTHONPATH=tools python tools/run_g25e.py G25E_Cohort_A_Frozen_Protocol.json
PYTHONPATH=tools python tools/run_g25e.py G25E_Cohort_B_Frozen_Protocol.json
PYTHONPATH=tools python tools/audit_g25e.py
PYTHONPATH=tools python tools/summarize_g25e.py
```

Re-running the cohorts overwrites local research results, not production source; audit the original archive before doing so. Checksums manifest provided in the package. GitHub remains a repository/documentation ledger only.