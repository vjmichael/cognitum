# CH-C14-13 — Source-level cluster safety fix, R/Firth handoff, expanded calibration

**November 2, 2026. Linux research; engineering priorities 1 and 3 scoped PASS; external R priority 2 BLOCKED. Scientific release NO-GO.** No production C14, original CH11/G25, Lu or Windows modifications.

## Priority 1 — source-level low-cluster repair: PASS in isolated research candidate

The original CH11 estimate function used `clustered=G<n and G>=25`, silently changing grouped observations with <25 unique clusters to individual-level IID folds and IID inference. CH13 contains a copied but explicitly **modified research candidate** that detects grouped observations `G<n` and refuses those with `G<25`, emitting `refused_insufficient_clusters`; inconsistent vector lengths also refuse. No silent IID fallback remains in the CH13 candidate. Original CH11 source remains pinned `6d06d3f34f7305aeb8f609b3877c67281edcc563895cc6674ec4682201eddef8`, CH13 source `3ebb75ac4bdb5b264ebd1c6b1040e955b3c0b842f4114ec7ab5ad1f9af68e36d`. **Not merged into default production or upstream CH11.**

**10/10 local tests**, then **10/10 tests on independently extracted ZIP** passed. Tests cover cluster count 24 and 25 boundaries, independent observations, independent clustered covariance against `statsmodels`, group-disjoint train/test folds, deterministic SCM data, exact input lengths and Jeffreys score under separation.

## Priority 2 — external R/Firth numerical equivalence: BLOCKED (partial independent numerical check)

No local `Rscript`, R `logistf` or R `brglm2` available. CH13 exports **eight distinct immutable CSV fixtures**, with Python reference coefficients and input hashes (regular, complete/quasi separation, all-zero outcomes, single-positive, scaled predictors, multivariate rare and ordinary). A *separate* Python Jeffreys adjusted-score root solver, independently initialized at all zeros, converged on **8/8 fixtures**; max absolute coefficient difference `6.353e-05`, residual score norms <1e-6. **Not R validation**.

Included runnable `r_equivalence/compare.R` invoking both R implementations and `check_r.py` to verify **16 external R fits** against the reference (screen tolerance 1e-3). This code has **not been executed**, so formal numerical equivalence is **not established**. Run the fixture package in a Linux R environment with those two packages and return CSV; then compare convergence and numerical differences. Do not claim R PASS until executed.

## Priority 3 — preregistered expanded holdouts: SCOPED ENGINEERING PASS

Frozen initial protocol SHA256 `6072a2094e1089389c58dcccbb8c6924bbe31e5985df367fac3b5b04df0be0e7`; 8 families × n=400/800 × 24 independent seeds × ridge/Firth-like = **768 attempts**. Confirmation protocol with **80 new independent seeds per cell**, separately frozen before results, pinned unchanged estimator + generator source digests; **2,560 further attempts**. The study varied cluster size 5/10/20/40, rare and very-rare event probabilities, nonlinear outcome misspecification, severe weak overlap, common outcomes and unmeasured cluster confounding.

**Total 3,328 attempts:** 2,010 intervals issued; 624 refused fewer than 25 clusters; 373 refused extreme overlap; 321 refused single-class nuisance folds; **zero unexpected failures, causal certifications or production promotions.** An independent *read-only* audit verified all unique case/method records, refusal accounting, group-disjoint cross-fit receipts, interval arithmetic, cluster-CR1 variance type on all issued intervals, and source/protocol pins. It does not separately refit all nuisance regression estimates.

Selected confirmation results (80 attempted per method per cell):

| Family, n | Ridge issued / truth included | Firth-like issued / truth included |
|---|---:|---:|
| Rare, cluster size 5, n=400 | 33 / 33 | 80 / 77 |
| Rare, cluster size 20, n=800 | 53 / 49 | 80 / 75 |
| Rare, cluster size 40, n=800 (20 clusters) | **0 / 0** | **0 / 0** |
| Very rare, cluster size 10, n=400 | **2 / 2** | **80 / 73** |
| Nonlinear outcome, cluster size 10, n=800 | 80 / 78 | 80 / 78 |
| Weak overlap, cluster size 10, n=800 | **3 / 3** | **3 / 3** |
| Hidden confounding, cluster size 10, n=800 | **80 / 7** | **80 / 7** |

These inclusion counts include attempts in denominators and therefore combine numerical-fit refusals and interval coverage. For hidden confounding the model is not identified; no causal confidence claim follows. Only 80 confirmation seeds per cell, fixed hyperparameters and Monte Carlo truth approximations; **not** broad scientific 95% calibration certification.

## Reproducibility

Research package `Cognitum_CH_C14_13_Cluster_Safety_R_Firth_Holdouts_2026-11-02.zip` SHA256 `a4173c80dcd32b39be921e59729dca9851930d9950ce51f356168de50eefd2f5`. **32/32 payload hashes verified** and source tests rerun **10/10 PASS after independent extraction**. Contains actual modified candidate code, R fixture generator + CSVs, R runner and Python comparator, initial/confirmation frozen protocols, 3,328 case-level receipts, independent read-only audit, tests and full engineering report. Local development only; GitHub is repo/milestone archive.

## Honest gate state and further work

**Priority 1 research fix: PASS; priority 3 expanded research holdout: PASS scoped; priority 2 R numerical equivalence: BLOCKED pending external R execution.** C14 scientific production release remains **NO-GO**: rare-outcome calibration is not universally resolved, hidden confounding/identification remains, real-world provenance is not established, G25N's 12/12 previous width/calibration failures remain open, and independent external statistical review has not occurred. Completing R equivalence does not on its own authorize promotion.
