# CH-C14-14 — Offline R preparation and independent base-R Jeffreys check

**Date:** 2026-11-02. **Scoped numerical PASS; independent CRAN package comparison still BLOCKED.**

Three packages recovered from the user Library Delivered folder: Debian R base core 4.5.0-3, Debian brglm2 0.9.2+dfsg-1, and CRAN logistf 1.26.1 source. R 4.5.0 was unpacked into an isolated local directory and run through its R executable without modifying dpkg installation state or Cognitum production source.

An independently authored **base-R** binomial Jeffreys-penalized logistic solver (BFGS followed by finite-difference Jacobian adjusted-score refinement) was executed across all eight immutable CH13 CSV test fixtures. Input SHA256 checks passed. All eight independently generated R coefficients agreed with pinned CH13 Python coefficients to maximum absolute coefficient difference **0.000420224588** (screen <=0.001); all adjusted-score residual infinity norms were <1e-6. Cases included ordinary, complete/quasi separation, all-zero events, single positive and multivariable rare outcomes. This is useful **cross-language** verification, **NOT** an independent `logistf` or `brglm2` package run.

**External dependencies currently missing:** Debian brglm2 depends on R MASS, Matrix, nnet, enrichwith and numDeriv. `logistf` imports mice, mgcv, formula.tools and Matrix, requiring transitive R dependencies and source compilation. Offline apt dependency resolution fails. Do not assert package numerical equivalence until both R packages are installed and the existing CH13 `compare.R` / `check_r.py` 16-reference-fit acceptance is executed.

Local reproducible script-only archive (no redistributed R binaries) `Cognitum_CH_C14_14_R_Offline_Prep_Base_R_Equivalence_2026-11-02.zip` SHA256 `3b58e6bc2d98eb0fea9c173ebfc91eb9e01114da7e7b174f0e792fc5b171b689`, 15 internal payload SHA256 entries checked. No changes to Lu, Windows, pinned G25, production C14. Scientific release remains NO-GO.
