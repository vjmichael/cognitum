# Cognitum C14 G25 — Engineering gate closure, batch 1

**Date:** 2026-11-01 | **Scope:** Cognitum research only | **Release:** NOT APPROVED

## Executive result

G25I's conservative partial-identification calculation has been wrapped by a fail-closed *research reporting* boundary with strict observation validation, explicit Gamma/assumption declarations, missing-arm and sparse-arm refusal policy, structured non-certifying outcomes, and deterministic receipt revalidation. The original G25I mathematical core is pinned unchanged from the G25N archive. No experimental estimator is promoted; no Cognitum production or Lu source is modified.

## Tests and numerical checks executed locally

| Suite | Passed | Failed |
|---|---:|---:|
| New gate guard, CP equivalence, counterfactual LP, tampering | 22 | 0 |
| Unchanged G25L suite | 22 | 0 |
| Unchanged G25M suite | 20 | 0 |
| Unchanged G25N suite | 32 | 0 |
| **Total** | **96** | **0** |

Additional embedded checks: 120 independent SciPy/HiGHS counterfactual-mean LP comparisons against G25I plug-in identified-set endpoints; Clopper–Pearson exact beta intervals compared with `statsmodels.stats.proportion.proportion_confint(method='beta')` at 1, 2, 5, 20, 200 and 900 observations, including endpoints and randomly selected successes. Tests reject rehashed forged certification flags and data changes.

The archived G25N SHA-256 manifest was rechecked for all **55/55** payload entries. An independent source-level audit read every **14,000** archived dataset receipts in **28** complete cells: **12,000** positive observed-arm cases and **2,000** observed-arm-missing cases; all prior false-certification flags remained false and all missing-arm cases remained refused. **560** deterministic stratified interface replays completed and matched.

The conservative minimum-25-count research policy flags **1,222** of the 12,000 positive-support cases for further review. On the stratified 560-case replay, 427 had a conditional sensitivity report, 53 were blocked as sparse and 80 as missing an observed arm. There were zero receipt anomalies or manifest mismatches.

## Scientific scope and limitations

An interval conditional on analyst-specified Gamma is **not** a proof of exchangeability, absence of hidden confounding or correct sensitivity bound. Even a 95%-or-better confidence outer set can be too wide and fail a precision/calibration gate. Nothing here changes G25M's mathematically established width impossibility for its particular frozen hybrid region or G25N's 12/12 DKW width failures. Statistical calibration on broad fresh continuous/nonlinear causal models remains open. The standalone guard is **not integrated into Cognitum's production runtime**; this is a safety-ready research candidate only.

An independent Clopper–Pearson library equivalence was completed locally. Independent **R Firth `logistf`/`brglm2` equivalence remains open** because this environment lacks R. Separate external scientific review and explicit promotion authorization are also still needed. Global Monte Carlo likelihood inversion, certified endpoint projection, and any improved-width 95% inference remain open. No release gate is passed by redefining its threshold.

## Next technical work

1. Connect the guarded *conditional reporting contract* to a nonproduction C14 capability test harness; verify real input/output and cancellation/failure provenance without authorizing causal inference.
2. Conduct an independent holdout with continuous and nonlinear covariates, rare outcomes, and hidden-confounding negative controls; keep all attempted cases in the acceptance denominator.
3. Obtain external statistical code review and R Firth equivalence, and establish the criteria for any later production estimator change.
4. Only when the scientific and runtime release gates pass, request explicit authorization for promotion. Do not build another speculative G25O-onward estimator merely to satisfy a number-of-milestones target.