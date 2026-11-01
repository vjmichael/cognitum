# Cognitum C14 G25I — Causal identification, hidden-bias sensitivity and partial-identification bounds

**Date:** November 1, 2026 (America/Phoenix)  
**Status:** Isolated research COMPLETED and audited; overall C14 G25 production scientific acceptance **OPEN / NO PROMOTION**.  
**Scope:** Cognitum causal-inference research only. No changes to Cognitum production C14, Lu, DLC integration, permission policy or Windows/Linux application code.

## Scientific conclusion

A fitted causal model cannot infer from its own numeric convergence and observed overlap that unmeasured common causes are absent. G25H demonstrated that limitation with a hidden-confounder sentinel. G25I introduces independently checked, assumption-indexed **sensitivity identified sets**, with conservative finite-sample bounds, so users can see how conclusions depend on an explicitly chosen upper bound Γ on selection bias.

The new method is **not** a substitute for causally identifying the treatment effect. In particular, Γ is a scientific input/assumption, **not** a data-estimated or automatically verified certainty parameter. The conservative intervals cover very broadly, often 100% of simulated truths when the true Γ is sufficiently small relative to the asserted Γ, but are wider than well-calibrated 95% confidence intervals. No automatic causal-confidence admissions occurred.

## Frozen design and source provenance

- Two independent, preregistered synthetic cohorts (A/B): 1,000 seeds per family/size/cohort, six families × two sample sizes (900 and 1,800): **24,000 unique datasets**.
- Five prespecified Γ values per dataset, 0, 0.10, 0.25, 0.50, 1: **120,000 attempted sensitivity calculations**.
- **20,000** positive-support datasets yielded **100,000** numerical sensitivity results. All **4,000** structural-zero-overlap datasets refused all five conditional calculations (**20,000** refusal records) and retained non-exchangeability Manski point bounds.
- Pre-holdout test-fixture correction and seed-range correction documented separately; both frozen protocols were regenerated **before** any fresh held-out result. Original G25H and G25G source trees were left untouched.
- Generator and fit code SHA-256 values and all per-file manifests are included in the reproduction archive. The two frozen JSON protocols record every study parameter and source hash.

## Mathematical statement (binary outcome)

Let W be a **binary observed adjustment variable**, T a binary treatment, and Y a binary observed outcome, with potential outcomes Y(0),Y(1). Define e(w)=P(T=1|W=w), m_t(w)=E[Y|T=t,W=w]. Under consistency, the unknown counterfactual mean E[Y(t)|T=1−t,W=w] is constrained only by:

    max(0, m_t(w) − Γ) ≤ E[Y(t)|T=1−t,W=w] ≤ min(1, m_t(w) + Γ).

This is a **bounded counterfactual risk-difference assumption** for both arms in every observed stratum. It is not a Rosenbaum Γ odds ratio and is not an E-value. These bounds plus the observed table define an interval for the ATE. For Γ=1, they reduce exactly to the no-exchangeability **Manski bounds**. For Γ=0, they reduce to the adjusted point estimand, but identify a causal ATE only when the required exchangeability, consistency, positivity and measurement assumptions actually hold.

Sample uncertainty is added by seven exact Clopper–Pearson binomial intervals at Bonferroni level α/7 (one marginal W frequency, two treatment propensities, four outcome means); endpoints are optimized over the resulting rectangular confidence region, including the sum-to-one stratum-weight constraint. This gives a **conservative at-least-95%-coverage outer interval for the population sensitivity identified set**, conditional on the stated Γ bound, independent i.i.d. sampling, binary variables and consistency. Coverage is not guaranteed when Γ is too small to bound hidden selection bias, assumptions fail or target populations differ.

## Pooled A+B descriptive results

Each row has 2,000 attempted datasets. "Γ=0 outer coverage" is deliberately descriptive even in models where Γ=0 is **false**, and therefore is **not** coverage of a valid nominal CI. Numerical intervals are not causal-admission decisions.

| Simulator family | n | Simulator-required Γ (research-only) | Γ=0 outer covers truth | Γ=0 mean outer width | Empty observed arms | Low empirical overlap warnings |
|---|---:|---:|---:|---:|---:|---:|
| Observed adjustment sufficient | 900 | 0.000 | 100.00% | 0.347 | 0/2,000 | 0/2,000 |
| Observed adjustment sufficient | 1800 | 0.000 | 100.00% | 0.244 | 0/2,000 | 0/2,000 |
| Hidden predictor; randomized given W | 900 | 0.000 | 100.00% | 0.339 | 0/2,000 | 0/2,000 |
| Hidden predictor; randomized given W | 1800 | 0.000 | 100.00% | 0.238 | 0/2,000 | 0/2,000 |
| Hidden common cause | 900 | 0.137 | 98.00% | 0.347 | 0/2,000 | 0/2,000 |
| Hidden common cause | 1800 | 0.137 | 75.70% | 0.245 | 0/2,000 | 0/2,000 |
| Misclassified confounder | 900 | 0.300 | 0.45% | 0.340 | 0/2,000 | 0/2,000 |
| Misclassified confounder | 1800 | 0.300 | 0.00% | 0.239 | 0/2,000 | 0/2,000 |
| Weak but positive overlap | 900 | 0.000 | 100.00% | 0.886 | 0/2,000 | 2000/2,000 |
| Weak but positive overlap | 1800 | 0.000 | 100.00% | 0.686 | 0/2,000 | 1998/2,000 |
| Structural positivity failure | 900 | Undefined | N/A | N/A | 2000/2,000 | 0/2,000 |
| Structural positivity failure | 1800 | Undefined | N/A | N/A | 2000/2,000 | 0/2,000 |

### What larger Γ changes

- The latent-common-cause generator requires Γ ≥ approximately **0.137** to include the simulator-known selection contrasts. Γ=0 is **not** valid in that model; Γ=0 outer coverage falls to **75.7% at n=1,800**. With Γ=0.25 the outer band covered the true effect in **100%** of accepted cases; its mean width at n=1,800 is **0.720**.
- The misclassified-confounder generator requires Γ ≥ approximately **0.300**. The Γ=0 band covered the true effect in **0% at n=1,800**, while Γ=0.25 happened to cover **100%** because its finite-sample band was extremely wide. **That does not validate Γ=0.25**—it is smaller than the known necessary bound. For Γ=0.50 the interval is assumption-adequate for this simulator and had 100% empirical inclusion, but the mean outer band width was **0.987** at n=1,800.
- Weak-but-positive overlap triggered **3,998/4,000 low-cell-count warnings**; although every sampled treatment arm was nonempty, the mean Γ=0 outer interval widths were **0.886 at n=900** and **0.686 at n=1,800**. A wide interval is not a proof of strong identification.
- Structural positivity failure had zero observed observations in a required arm for **all 4,000 datasets**. The conditional Γ-specific interval was refused; no-assumptions Manski point bounds were retained, without claiming 95% sampling coverage for those plug-in point bounds.

### Explicit calibration and selection limits

All simulator-adequate Γ values reached 100% empirical inclusion in this constructed test. **This is serious overcoverage and cannot be called calibrated 95% inference.** It is a direct effect of exact Bonferroni outer bands and the binary low-dimensional simulation. One cohort cell with 1,000/1,000 inclusion has an ordinary Wilson 95% interval of approximately 99.62–100%, which excludes nominal 95%: conservative but not nominally calibrated.

Where Γ is invalid, sample inclusion can improve merely because bands are wider. True Γ (0.137 and 0.300) is available solely to the simulator and is not knowable from observed-only input. Selection into computable cells and missing support remain separate from conditional coverage scoring.

## Safety and provenance audit

| Test | Evidence |
|---|---|
| Complete structural receipts | Cohort A 12,000 datasets / 60,000 method records; Cohort B 12,000 / 60,000 — **PASS** |
| Exact numerical replay | A 300 + B 300 = **600/600**; all five methods per replayed dataset |
| Full independent fixture-byte replay | **24,000/24,000 unique W,T,Y arrays and hashes** reproduced |
| Γ=1 point bounds vs Manski | **20,000/20,000** positive-support cases agree to 1e−12; 0 mismatches |
| Independent linear-program optimizer | 40 arbitrary probability tables + 4 analytically specified families agree to 1e−11 |
| Independent exact binomial checks | 15 Clopper–Pearson comparisons against statsmodels pass to 1e−12 |
| G25I tests | **22/22 passing**, including five supplemental post-holdout adversarial tests |
| Unmodified G25H tests | **16/16 passed** |
| Unmodified G25G tests | **18/18 passed** |
| False automatic causal admission | **0/24,000**; even a supplied user attestation is not independently verified |
| Adversarial receipt tests | Reject forged fixture hash, altered observed counts, forged auto-admission and forged oracle support |

The two frozen audit programs verify every stored numerical result against the stored joint counts, and replay 600 complete datasets. A **separate post-holdout supplement** regenerates all 24,000 full dataset bytes and exact count matrices, to rule out receipt manipulation that might otherwise escape sparse full-data replay. These checks are stronger than a checksum alone, but they are not independent external science replication.

## G25I research acceptance and production decision

- The preregistered narrow screen requires at least 95% inclusion of simulator truth whenever Γ was simulator-adequate, zero automatic causal admissions, no lost/duplicated receipts, and independent method checks. **PASS**: all evaluable adequate-Γ cells passed those narrow conditions (coverage 100%).
- However, the original C14 G25 production acceptance requirements **remain unmet**: serious overcoverage, broad intervals, a binary-only simulation, zero real-world analyst justification for Γ or hidden confounding, no general continuous-covariate sensitivity derivation, and no external statistical-package validation of the complete G25I procedure.
- **NO PRODUCTION PROMOTION.** The G25G stacked variance and G25H double-misspecification findings are not replaced by this study. There is no claim that numeric overlap checks can detect hidden common causes.

## Follow-up tasks (G25J candidates)

1. Obtain defensible sensitivity-parameter elicitation (benchmarked to observed confounder strengths) with explicit provenance and refusal when assumptions are unsupported.
2. Compare less conservative simultaneous bounds or calibrated partial-identification confidence sets (with rigorous proof and holdout simulation), without compensating for bias by blindly widening intervals.
3. Expand beyond a binary W and binary Y; evaluate continuous nonlinear covariates, treatment-effect heterogeneity and missingness using independently specified causal structures.
4. Cross-check calculations with a genuinely independent causal/statistical package and empirical datasets, while preserving the distinction between formula replication and causal identification.
5. Keep production C14 unchanged pending separate explicit authorization and a complete independent validation package.

## Reproduction

At package root: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=tools` followed by:

```sh
python tools/run_g25i.py A
python tools/run_g25i.py B
python tools/audit_g25i.py A
python tools/audit_g25i.py B
python tools/aggregate_g25i.py
python tools/deep_audit_g25i.py
pytest -q tests
```

Run the G25G and G25H regression suites from their unchanged source folders. The archive includes frozen JSON, tool SHA-256 digests, all receipts, machine-readable summaries, complete audit reports, and a file checksum manifest.

## Methodological references

- Manski partial-identification bounds and limits of unconfoundedness: [Imbens and Wooldridge/NBER review](https://www.nber.org/papers/w14251) and [Lee–Weidner, Journal of Econometrics (2026)](https://doi.org/10.1016/j.jeconom.2026.106254).
- Modern sensitivity-analysis principles: [Causal Inference in the Social Sciences, Annual Review of Statistics and Its Application](https://doi.org/10.1146/annurev-statistics-033121-114601).
- Exact Clopper–Pearson binomial confidence limits: [SAS documentation](https://support.sas.com/documentation/cdl/en/procstat/66703/HTML/default/procstat_freq_details37.htm).

> This experiment is not a claim that all real-world confounding is bounded by any chosen Γ, nor that treatment outcomes are identified from observed numerical model convergence. It demonstrates the consequences of **explicit, unverified sensitivity assumptions** and records conservative uncertainty conditional on those assumptions.