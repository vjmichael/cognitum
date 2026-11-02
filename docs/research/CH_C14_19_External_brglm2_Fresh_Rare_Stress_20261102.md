# CH-C14-19 — New rare-event / separation external brglm2 fit stress

**November 2, 2026. Scoped diagnostic engineering PASS; numerical-fit reliability incomplete; scientific C14 NO-GO.** No changes to production C14, G25, Lu, or Windows.

## Preregistered stress protocol
Frozen SHA256 `6616ab657d6232b1f4b4778f86a15c196d436c4e20a6cac6d1c2378770c1e36e`, written **before** dataset generation and R execution. Five new synthetic logistic-regression families: all-zero responses, one-event responses, stochastic rare events, quasi separation, and imbalanced predictors. Two sample sizes, n=80 and 160, ten independently seeded instances each: **100 generated datasets**. Fit each using actual isolated R 4.5.0 + `brglm2` 0.9.2 `AS_mean`, ordinary versus explicit-zero-offset, yielding **200 R fit records**. Same CSV datasets fitted with pinned CH13 Python Jeffreys/Firth-like research estimator. Zero-offset is a diagnostic variant, **not an independent method**.

## Real results
- Python CH13: **100/100 fits issued**.
- External R: **190/200 converged**, **10/200 returned `converged=FALSE`**. All 10 nonconverged records are from five distinct zero-observed-event datasets, in ordinary **and** offset0 variants.
- Of the 190 converged external fits, maximum absolute three-coefficient difference versus Python `1.6658e-05`; independently recomputed adjusted-score infinity norm `3.4292e-05`. Both below frozen screens of 0.001. **These successful numerical screens exclude every nonconverged fit**.
- Across all 200 records, **27 algorithm-nonconvergence warnings** (22 ordinary, 5 with explicit zero-offset). Zero-offset did not clear the warning or fix convergence on five zero-event datasets.
- Families (40 R attempts each): all-zero 32 converged / 24 warned; one-event 40 / 0; stochastic rare 38 / 3; quasi-separation 40 / 0; imbalanced predictors 40 / 0. All 200 attempts accounted for, 0 errors swallowed, 0 auto causal certifications/promotions.
- **10/10** new data-integrity, refusal-accounting and numerical audit tests passed. Actual `brglm2` warnings were captured rather than filtered out.

## Scientific significance
CH17/CH18's identified **auxiliary null-deviance fit** warning mechanism was correct for their particular all-zero fixture; it is **not a universal root cause or universal fix for zero-event fits**. Other all-zero fixtures produce true main-fit `converged=FALSE` even with an explicit zero offset. Neither a `TRUE` convergence flag with warnings, nor the coefficient screen alone, authorizes scientific validation. Retain research-only fail-closed policy and investigate independent starts/score-controlled numerical recovery separately.

## Archive
Local ZIP `Cognitum_CH_C14_19_External_brglm2_Fresh_Rare_Stress_2026-11-02.zip`, SHA256 `d97f55420a81cf100ab766b21166f4cd616733747248d0f13ccc2176d84763e7`; **112 payload file SHA256 entries** verified from extracted archive. Contains frozen protocol, generated CSVs and source-hash receipts, Python reference coefficients, 200 real R results, independent adjusted-score audit, test suite, scripts and engineering report. Requires previously preserved isolated R and CH13 source to regenerate from scratch; no external binaries redistributed.

**Remaining external blocker:** `logistf` source is present, but `mice`, `mgcv`, `formula.tools` and their dependencies have not been uploaded. Full two-package equivalence and independent external scientific review remain open. C14 release **NO-GO**. GitHub is used only as repository/milestone log, not execution hub.
