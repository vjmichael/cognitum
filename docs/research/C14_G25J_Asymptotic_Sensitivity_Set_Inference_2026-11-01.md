# Cognitum C14 G25J — Simultaneous asymptotic sensitivity confidence sets and Gamma elicitation safeguards

**Date:** November 1, 2026 (America/Phoenix)  
**Status:** Fresh-seed G25J research **COMPLETE and independently receipt-audited**; **G25 scientific promotion DENIED**.  
**Scope:** Isolated Cognitum C14 research. No production Cognitum estimator, Lu runtime, Lu DLC, branch main or permission changes.

## Executive finding

An experimental eight-cell multinomial **joint-normal asymptotic simultaneous outer set** is dramatically narrower than the finite-sample seven-Bonferroni/Clopper–Pearson outer set previously constructed in G25I, when Γ=0 and supports are well populated. Across the four moderate-support families, Γ=0 outer-set coverage is roughly 94–96% and the matched width is around 35–37% of G25I. However, the experimental method is **not a uniform finite-sample guarantee**; at intermediate Γ it refuses many cases near non-smooth sensitivity-bound kinks, and some of the remaining selected cases under-cover the *population identified set*. It therefore fails preregistered completion, coverage and width gates in multiple cells and cannot replace G25I or any production estimator.

Crucially, *covering the simulated true treatment effect* when the user-selected Γ is large is weaker than **simultaneously covering both endpoints of the population sensitivity-identified set**. G25J is graded against the harder endpoint condition; no good-looking 100% effect inclusion number is used to hide endpoint failures.

## Frozen design and provenance

- Exactly **24,000 distinct datasets**, two disjoint fresh-seed cohorts (A/B), each 1,000 datasets per family × sample size (six G25I families × n=900/1,800). This is **new sampling from the existing G25I synthetic generators**, not independent new SCM families.
- Prespecified Γ ∈ {0,.10,.25,.50,1}; **120,000 sensitivity settings** and **240,000 method attempts** (exact G25I reference and experimental G25J method).
- Identical observed 2×2×2 (W,T,Y) counts supplied to both methods; simulator-held true population probabilities and true ATE used only for research scoring, not for numerical interval construction or access grants.
- Per-cell refusal rules frozen before the holdout: empty observed treatment/stratum arm; arm count <25; any 8-category joint count <10; within .02 of an endpoint kink; degenerate covariance. Every refusal has its own receipt. No method could automatically grant causal identification.
- Freeze SHA-256 (A): `dc40459843b71d14a288838532232f220b62e3ff15bb1472fa4810f1884a461d`; (B): `db3b63e835ff13043352ce420d159e7d39c21a434c0c4e7accfb7d04399e4db6`. Full source digests are in both frozen JSON protocols. The unchanged G25I reference core is included with its provenance.

### Operational deviation (no selective analysis)

Both frozen cohort runners **successfully wrote every dataset receipt** but subsequently exited nonzero while JSON-serializing a NumPy `int64` in the *summary* stage. We preserved their logs, original source and file hashes; a separate post-freeze reporting-only utility reconstructed summary JSON from the complete receipts. The untouched frozen source hashes were rechecked, and an independent auditor regenerated and verified all 24,000 dataset fixtures and all 240,000 recorded method results. The original runner exit failures are **not** represented as successful executions. See `G25J_Operational_Deviation.md`.

## Estimands, assumptions, and derivation

This retains G25I’s specific **bounded counterfactual outcome-risk difference Γ**, not Rosenbaum treatment odds and not a data-estimated hidden-confounding bound. For observed stratum w, write `A=P(W=w,T=0)`, `B=P(W=w,T=1)`, `m0=P(Y=1|W=w,T=0)`, `m1=P(Y=1|W=w,T=1)` and `d=P(W=w,T=1,Y=1)`, `b=P(W=w,T=0,Y=1)`.

The stratum’s contribution to the sharp *population* identified bounds is:

```text
L_w = d - b + A max(0, m1 - Gamma) - B min(1, m0 + Gamma)
U_w = d - b + A min(1, m1 + Gamma) - B max(0, m0 - Gamma)
L = sum_w L_w,  U = sum_w U_w
```

For samples with positive observed arms and locally smooth branches, the multinomial covariance is `V=(diag(p)-p pᵀ)/n`, with analytic endpoint gradients `gL,gU`. The asymptotic endpoint covariance is `gᵢᵀVgⱼ`. The simultaneous one-sided critical `c` is solved from `P(Z_L ≤ c, -Z_U ≤ c)=.95` with the **estimated** endpoint correlation, yielding `[Lhat - c·SE(Lhat), Uhat + c·SE(Uhat)]` clipped to the logical ATE range [-1,1]. This targets *simultaneous endpoint-set containment*, not the shorter **Imbens–Manski pointwise-parameter CI**. The latter has important non-uniformity qualifications developed by Stoye; G25J does not claim to implement it.

The delta approximation may fail or become nonuniform at kinks, close to zero support, or if an analyst chooses Γ after inspecting the data. The frozen refusal thresholds are operational heuristics rather than a proof of nominal conditional or uniform coverage. Exact G25I Bonferroni/CP intervals retain their original, stronger finite-sample guarantee **conditional on their assumptions** and can be wider.

## Pooled A+B empirical comparisons

Each row here contains **2,000 attempted datasets**. Coverage means both true population Γ-identified-set endpoints lie in the reported outer set. The G25J coverage is **conditional on the separately shown accepted count**. Width ratio is mean G25J width divided by mean G25I exact width **on the same accepted datasets**. The G25I exact-reference set coverage was 100% in all 100,000 reference-calculable settings; that is conservative, not evidence of nominal 95% calibration.

| Generator | n | Γ | Accepted / 2,000 | G25J set coverage | Wilson 95% | Width / exact reference |
|---|---:|---:|---:|---:|---:|---:|
| Observed adjustment | 900 | 0.00 | 2000/2,000 | 95.55% | 94.56%–96.37% | 0.355 |
| Observed adjustment | 900 | 0.25 | 1402/2,000 | 95.22% | 93.98%–96.22% | 0.744 |
| Observed adjustment | 900 | 1.00 | 2000/2,000 | 95.15% | 94.12%–96.01% | 0.884 |
| Observed adjustment | 1800 | 0.00 | 2000/2,000 | 94.75% | 93.68%–95.64% | 0.357 |
| Observed adjustment | 1800 | 0.25 | 1565/2,000 | 95.53% | 94.39%–96.44% | 0.794 |
| Observed adjustment | 1800 | 1.00 | 2000/2,000 | 94.55% | 93.47%–95.46% | 0.915 |
| Hidden prognostic, randomized | 900 | 0.00 | 2000/2,000 | 94.45% | 93.36%–95.37% | 0.355 |
| Hidden prognostic, randomized | 900 | 0.25 | 1084/2,000 | 91.42% | 89.60%–92.95% | 0.743 |
| Hidden prognostic, randomized | 900 | 1.00 | 2000/2,000 | 93.90% | 92.76%–94.87% | 0.884 |
| Hidden prognostic, randomized | 1800 | 0.00 | 2000/2,000 | 95.15% | 94.12%–96.01% | 0.357 |
| Hidden prognostic, randomized | 1800 | 0.25 | 813/2,000 | 92.99% | 91.02%–94.55% | 0.797 |
| Hidden prognostic, randomized | 1800 | 1.00 | 2000/2,000 | 95.30% | 94.28%–96.14% | 0.914 |
| Hidden common cause | 900 | 0.00 | 2000/2,000 | 95.30% | 94.28%–96.14% | 0.358 |
| Hidden common cause | 900 | 0.25 | 1771/2,000 | 95.48% | 94.41%–96.36% | 0.742 |
| Hidden common cause | 900 | 1.00 | 2000/2,000 | 95.35% | 94.34%–96.19% | 0.887 |
| Hidden common cause | 1800 | 0.00 | 2000/2,000 | 95.30% | 94.28%–96.14% | 0.359 |
| Hidden common cause | 1800 | 0.25 | 1874/2,000 | 95.84% | 94.84%–96.65% | 0.789 |
| Hidden common cause | 1800 | 1.00 | 2000/2,000 | 95.65% | 94.67%–96.46% | 0.916 |
| Misclassified adjustment | 900 | 0.00 | 2000/2,000 | 94.60% | 93.52%–95.51% | 0.365 |
| Misclassified adjustment | 900 | 0.25 | 1054/2,000 | 94.12% | 92.53%–95.38% | 0.752 |
| Misclassified adjustment | 900 | 1.00 | 2000/2,000 | 94.15% | 93.03%–95.10% | 0.896 |
| Misclassified adjustment | 1800 | 0.00 | 2000/2,000 | 94.90% | 93.85%–95.78% | 0.367 |
| Misclassified adjustment | 1800 | 0.25 | 972/2,000 | 93.62% | 91.91%–94.99% | 0.800 |
| Misclassified adjustment | 1800 | 1.00 | 2000/2,000 | 94.95% | 93.90%–95.83% | 0.923 |

### Why the method is not accepted

- The randomized-hidden-prognostic model at **n=900, Γ=.25** accepted only **1,084/2,000** cases and achieved **91.42%** full-set containment; its Wilson 95% interval is **89.6–92.9%**, excluding nominal 95%. Its n=1,800 Γ=.25 cell accepted **813/2,000**, with **92.99%** containment.
- The misclassified-confounder model at **n=900, Γ=.50** achieved **92.6%** full-set containment among 1,319 accepted cases. The method fails even without requiring perfect 95% point coverage.
- Intermediate Γ refusal rates are large and data dependent. For instance the measured n=900 Γ=.25 cell accepted only 1,402/2,000 cases because 598 were near kinks. A selected subset with apparently good coverage is not unconditional evidence.
- At Γ=1, widths often exceed the maximum allowed ratio of 0.90, including n=1,800 measured (0.915) and misclassified (0.923). A width win at Γ=0 does not satisfy every Gamma cell.

### Refusals, negative controls, and all-method receipt accounting

Across 120,000 G25J asymptotic method attempts:
| Status | Count |
|---|---:|
| Asymptotic computed | **70,778** |
| Near non-smooth kink | **9,227** |
| Low observed treatment/stratum arm count | **19,990** |
| Sparse joint Y/T/W cell | **5** |
| Observed arm missing | **20,000** |

All **4,000 structurally non-overlapping datasets** were refused at all five Γ values (20,000 method refusals). All 4,000 weak-positive-overlap datasets were correctly retained as high-risk; **one** n=1,800 case met the delta admission thresholds, and its single-case observed inclusion cannot support an acceptance claim. No hidden confounding was detected or excluded by numerical fitting.

The baseline G25I reference generated 100,000 calculable CP intervals and refused 20,000 calculations for the structural-zero-overlap cases. **100,000/100,000** calculable reference intervals simultaneously contained the population identified set in this constructed experiment; very wide intervals can achieve this and should not be described as calibrated at exactly 95%.

## Sensitivity parameter and observed-strength benchmark

G25J calculates `max_t |E[Y|T=t,W=1] - E[Y|T=t,W=0]|` as **descriptive measured-covariate association**, not an identified upper bound on confounding. Pooled mean descriptive strengths were approximately:

| Family | n=900 mean | n=1,800 mean | Simulator-only Γ required |
|---|---:|---:|---:|
| Measured adjustment | 0.284 | 0.280 | 0 |
| Hidden prognostic, randomized treatment | 0.349 | 0.346 | 0 |
| Hidden confounder | 0.330 | 0.330 | ~0.137 |
| Misclassified confounder | 0.199 | 0.195 | ~0.300 |

Notice that the **misclassified-confounder** generator needs Γ≈0.300, larger than its observed-covariate association benchmark (~0.195–0.199). Treating that benchmark as an automatic upper bound would be unsafe. The user/analyst must supply independently justified Γ scenarios, with source provenance, limitations and a refusal to certify causal identification automatically. Numerical sign-tipping Γ from the plugin identified set is merely a sensitivity *display*, not an estimator of hidden confounding.

## Integrity and independent numerical verification

| Check | Result |
|---|---|
| Full frozen-cohort dataset replay and receipt audit | **24,000/24,000 exact datasets; 240,000/240,000 interval method receipts** |
| G25J pre-holdout unit tests | **34/34 passed** |
| Supplemental post-holdout adversarial auditor tests | **9/9 passed**, including forged claims rehashed at the file level |
| G25I unchanged regression tests | **22/22 passed** |
| Independent SciPy linear programming | **800 comparisons**, max absolute error 2.2e-16 |
| Independent gradient directional finite differences | **417 comparisons**, max absolute error 1.1e-09 |
| Independent bivariate normal CDF | **400 comparisons**, max error 2.6e-14 |
| Automatic causal-certification labels | **0/24,000** |
| Frozen seed cohort overlap | None (A/B disjoint by frozen seed construction) |

These numerical cross-checks use SciPy independent optimizers/CDFs; **they are not an independent external causal-sensitivity-package validation**. R `logistf`/`brglm2` and a separate partial-ID package remain unverified. There is no real-world causal-data validation, no new multivariate/continuous covariate SCM generator, and no theoretical uniformity proof near kinks.

## Research gate decision

**FAIL — G25J not promotable.** The registered positive research screen required ≥95% completion, observed set coverage ≥93%, nominal 95% inside Wilson 95% uncertainty for each cell, and matched width ≤90% of exact G25I in all supported cells. Intermediate Γ failures are clear. No thresholds, estimators or cohorts were revised after seeing results. Inference under unjustified Γ and hidden confounding is not certified; no production changes approved or made.

### Follow-up: G25K candidate

Investigate **kink-aware, locally uniform moment-inequality/partial-identification inference** or appropriately validated subsampling, with a preregistered strong- and weak-overlap policy. Include genuinely different SCMs, multivalued/continuous covariates and independently reviewed statistical-package checks. Avoid interpreting post-selection conditional coverage as unconditional coverage. Keep the exact G25I reference intact.

## Reproduction

From this package root (Python 3.13, NumPy/SciPy/pytest/statsmodels in the supplied environment):

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=tools:baseline
pytest -q tests
python tools/g25j_postfreeze_summary_serialization.py A  # read preserved JSONL
python tools/g25j_postfreeze_summary_serialization.py B
python tools/audit_g25j.py A
python tools/audit_g25j.py B
python tools/aggregate_g25j.py
python tools/g25j_additional_independent_validation.py
```

To **re-generate** cohort receipts from the frozen `run_g25j.py`, run `python tools/run_g25j.py A` and `B` in a fresh directory; expect the documented reporting-stage NumPy scalar serialization error after all receipts are written, then use the post-freeze summary-repair script above. Do not interpret the original runner nonzero exit as a failed numerical cohort or a clean process success. The full receipts are already bundled; no rerun is needed to inspect results.

## Scientific references and scope

- Imbens & Manski (2004), *Confidence Intervals for Partially Identified Parameters*, Econometrica: https://doi.org/10.1111/j.1468-0262.2004.00555.x
- Stoye (2009), *More on Confidence Intervals for Partially Identified Parameters*, Econometrica: https://doi.org/10.3982/ECTA7347
- G25I validated finite-sample CP implementation and numerical LP derivation are included; no claim of independent experimental replication by a third-party scientific group.

**Conclusion:** A sharper *regular-cell asymptotic* outer set is scientifically interesting, but G25J demonstrates substantial limitations under sensitivity-bound kinks and data-dependent exclusions. **Overall G25 remains OPEN; NO PRODUCTION PROMOTION.**