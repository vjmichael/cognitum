# CH-C14-11 — Cluster-blocked cross-fitting, Jeffreys/Firth-like nuisance logistic, cluster-sandwich verification

**November 2, 2026 · Linux standalone C14 research · ENGINEERING PASS / SCIENTIFIC NO-GO.** No modifications to pinned G25I, production C14, Lu or Windows.

## Provenance and reproducibility

- Frozen initial protocol SHA256: `5a6ae55f41adb9f4bdfe6f5fcc8cdcedcc3b7e53737578f6f31efc3669a7edd8`
- Study estimator source SHA256, frozen **before** independent-seed confirmation: `6d06d3f34f7305aeb8f609b3877c67281edcc563895cc6674ec4682201eddef8`
- Frozen confirmation protocol SHA256: `437107209a4e519bdb39d688c113a5a091f08191597c263c9668c85e95d79b5c`
- Initial holdout: 4 SCMs × n=400,800 × 30 seeds = 240 datasets × 2 methods = **480 attempts**.
- Untouched-source independent-seed confirmation: same cells × 100 new seeds = 800 datasets × 2 methods = **1,600 attempts**.
- Combined **1,040 datasets, 2,080 attempts**. All **1,792 issued results + 288 single-class nuisance-fold refusals** accounted for. All completions/refusals carry false certification/promotion flags.
- Archived local source, full case-level JSONL receipts, protocols, code tests and independent audit in `Cognitum_CH_C14_11_Cluster_Crossfit_Firth_Research_2026-11-02.zip`; ZIP SHA256 `60924119586aef511b3e207b873e96a6036ffba19d40bc8a1a2c7ac1856d791e`; all **16 archive manifest entries** checked after ZIP creation. GitHub records provenance; work conducted locally.

## Research implementations

1. Nuisance models use group-disjoint two-fold cross-fitting; group leakage checked as zero per issued interval. Grouping is in the sample generator, not inferred from outcomes.
2. Baseline regularized logistic nuisance outcome fits reject all-one-class training arms; no hidden fallback.
3. Candidate Jeffreys/Firth-like logistic outcome fits maximize binomial likelihood + 0.5 log|XᵀWX| with analytic score; intercept-only all-zero-arm and analytic-gradient numerical tests pass. **Not yet externally equivalent to R `logistf` or `brglm2`.**
4. Cross-fitted AIPW influence-function mean and CR1 cluster-sandwich variance with t(G−1) intervals; control comparison with `statsmodels.OLS` clustered covariance agrees at numerical precision. Independent-rare outcomes are evaluated conservatively in artificial groups of 10; do not claim iid-normal inference calibration.

## Independent-seed 100-case-per-cell confirmation

| Family | n | Ridge issued / truth included | Firth-like issued / truth included | Firth-like mean CI width |
|---|---:|---:|---:|---:|
| Cluster heterogeneous | 400 | 100 / 94 | 100 / 94 | .1964 |
| Cluster heterogeneous | 800 | 100 / 96 | 100 / 96 | .1350 |
| **Cluster rare** | **400** | **22 / 21** | **100 / 95** | **.0541** |
| Cluster rare | 800 | 74 / 72 | 100 / 95 | .0380 |
| Independent rare | 400 | 18 / 18 | 100 / 93 | .0499 |
| Independent rare | 800 | 61 / 57 | 100 / 94 | .0337 |
| Hidden-cluster confounding | 400 | 100 / 46 | 100 / 46 | .2157 |
| **Hidden-cluster confounding** | **800** | **100 / 15** | **100 / 15** | **.1490** |

Confirmation method completion: **Firth-like 800/800 vs ridge 575/800**, with 225 refusals due to single-class outcome folds in ridge. No unexpected numerical failures in this cohort. This is a **completion improvement** in these low-dimensional generators, not general nominal coverage certification. Both models fail under unmeasured confounding.

## Independent tests and audit

- **12/12** new tests pass: source pin, determinism, group-disjoint splits, all-zero-event Firth-like fit, intercept-only Jeffreys binomial check, analytic score vs finite differences, cluster-sandwich CR1 vs independent statsmodels cluster covariance, permutation invariance, insufficient-cluster refusal and negative cases.
- Read-only audit of all **2,080** results checks unique IDs, no missing records, interval arithmetic, truth inclusion, recorded fold count and zero shared training/test clusters. Does **not** independently recompute every nuisance regression from scratch.
- Initial 30-seed cohort issued 417/480 and refused 63/480; 100-seed confirmation issued 1,375/1,600 and refused 225/1,600.
- Monte Carlo simulator truth based on 400,000 observations. Truth approximation uncertainty not carried into the reported intervals. Only 100 confirmation replicates per cell and no R/external estimator equivalence.

## Release disposition

**C14 scientific release remains NO-GO.** External R Firth-equivalence, more independent methods and sample/cluster configurations, bias and coverage under misspecification/weak overlap, real-world auditable cluster provenance, independent scientific review, and G25N's pre-existing 12/12 failed interval-width gates remain unresolved. Firth-like fitting does not repair causal identification, CH09 score-inversion solver issues or hidden confounding. All changes stay in isolated research artifacts, not production.

**Next task:** obtain numerical equivalence to independent R `logistf` / `brglm2` and run preregistered broader cluster-size, rare-event and model misspecification holdouts; preserve all refusals.
