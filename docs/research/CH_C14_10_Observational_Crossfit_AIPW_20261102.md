# CH-C14-10 — Cross-fitted AIPW, robust variance and observational scientific stress tests

**2026-11-02 · Linux research · Engineering diagnostic PASS / Scientific release NO-GO**

## Frozen source and cohorts

- Initial protocol SHA256: `0d5d86876ca51aa8d30ddd597d58c870efc33b9a0637f627e53483bd5bd62103`; 7 SCM families × n=500/1000 × 32 seeds/cell = **448 new datasets and 1,792 attempts**.
- Separately frozen confirmation protocol SHA256: `75a53089d1447bb9cc989669bc868334e2f6e82c92ee7b49255b03e2f7ac0ea9`, pinned original candidate source SHA256: `d02488ab6eec551a4d3bd186a41a534f1d26b6a52a7f9e604cca59db660f92ca`. 160 **new** independent seeds/cell = **2,240 more datasets and 8,960 attempts**. No hyperparameter adjustments.
- Families: smooth measured confounding; nonlinear measured confounding; heterogeneous treatment effect; rare outcomes; unobserved U confounding; severe weak overlap; shared-cluster outcome effects.
- Methods: unadjusted two-arm Wald; two-fold cross-fitted AIPW with linear nuisance logistic models + influence-function empirical variance; cross-fitted AIPW with quadratic interactions + same SE; cluster-aggregated IF sandwich for the clustered family only. This is **HC1-like influence-function variance, not a proven finite-sample HC3 correction.**
- Ground-truth effect is separately approximated by 500k-draw Monte Carlo of the SCM's potential-outcome mean, **not** used during fit. Reference has finite MC error.
- Hard refusals for single-class rare-outcome folds, insufficient arms, numerical error, or fitted propensity below .015/above .985 too often. No silent fallback and no causal certification.

## Larger independent confirmation findings

The following numbers are truth-containing intervals out of **160 attempted datasets per cell**; do not compute nominal coverage by dropping refused fits.

| Family, n | Unadjusted Wald | Cross-fit AIPW linear | Cross-fit AIPW quadratic |
|---|---:|---:|---:|
| Smooth, 1,000 | **93/160** | **151/160** | 149/160 |
| Nonlinear, 1,000 | 155/160 | 156/160 | 150/160 |
| Heterogeneous, 1,000 | **49/160** | **151/160** | 151/160 |
| Rare, 500 | 151/160 | **121/160 issued and containing; 39 refused** | **121 issued, 120 containing; 39 refused** |
| Rare, 1,000 | 147/160 | **154 issued / 145 containing / 6 refused** | same |
| Hidden confounding, 1,000 | **0/160** | **0/160** | **0/160** |
| Weak overlap, 1,000 | 3/160 (unadjusted still issued) | **160/160 refused** | **160/160 refused** |
| Clustered, 1,000 | 143/160 | 147/160 | 150/160 |

For cluster-aggregated AIPW quadratic: 154/160 truth inclusion at n=500 (mean width .190) and 148/160 at n=1,000 (mean width .129), but the split is **by observation, not by cluster** and not independently acceptable as cluster-robust scientific evidence.

**Confirmation totals:** **6,310 issued, 2,650 refusals**. Refusal decomposition: 1,920 predeclared noncluster/method incompatibilities, 640 AIPW weak-overlap policy refusals, 90 rare-outcome single-class nuisance folds. All **8,960 attempts** were uniquely accounted for, all no-certification and no-promotion flags false. A command time limit interrupted the final clustered cell; the sole partial case was removed then recomputed, without changing source, protocol, seed or previous completed results. No duplicate or missing cases remained.

## Verification

- **10/10** fresh component tests PASS.
- Initial independent audit validated all **1,792** records and recomputed **30 AIPW estimates/SE** by separately written models and formulas, max difference **0**.
- Separate confirmation audit verified **8,960** unique case/method receipts, each interval arithmetic and truth-inclusion, not independent recomputation of every interval.
- Local archived research package: `Cognitum_CH_C14_10_Crossfit_AIPW_Observational_Validation_2026-11-02.zip`; SHA256 `e3a7c04493d3d43f749acb9621ebd3eec7e952777c22add030cbae790d3fafb2`. **15/15 payload SHA256 hashes** verified after ZIP creation. Complete per-case results, source, protocols, tests, independent audits, README and engineering report included.
- No production estimator / pinned G25 / Lu / Windows modifications.

## Scientific interpretation and next gates

Measured-confounder adjustment can strongly improve observational estimation compared with unadjusted associations in known generators; it **cannot resolve hidden confounding**. AIPW fails closed under extreme observed overlap and when rare-outcome nuisance folds contain only one class; refusal rates must remain in the assessment. Quadratic nuisance complexity often worsens width. 160 datasets/cell and Monte Carlo truth are still inadequate for broad nominal coverage guarantees.

**Scientific NO-GO unchanged**, including G25N's 12/12 scientific width failures and outstanding R Firth, external protocol provenance and independent statistics review. Next CH11: group-blocked nuisance splitting and correctly derived cluster sandwich, rare-event penalized/Firth-like nuisance fitting with external R validation, larger preregistered misspecification/positivity families, and independent statistical review. Evaluate any training-data benefits in a *separate* paired LLM experiment; no evidence of improved training here.

This is a standalone Cognitum research artifact. GitHub is repository and milestone record only, not the development environment.
