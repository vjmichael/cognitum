# CH-C14-15 — Real external R brglm2 comparison with offline packages

**2026-11-02 · Scoped numerical screen PASS (8/8) · clean convergence 7/8 · logistf BLOCKED · C14 scientific NO-GO.**

User uploaded Debian 13 packages under Library `/Jan Mod - Lu/Delivered`: R 4.5.0, brglm2 0.9.2, MASS, Matrix, nnet, enrichwith, numDeriv and lattice. Extracted privately and successfully loaded all packages without modifying global dpkg or production Cognitum.

Executed actual independently maintained **R brglm2** `stats::glm(..., family=binomial(), method=brglm2::brglmFit, type='AS_mean')` on all eight frozen CH13 logistic fixture datasets, including complete/quasi separation, all-zero outcomes, single-event, and multivariable rare/common cases. Every three-coefficient result is within the prior 1e-3 absolute-difference screen versus pinned CH13 Python estimator; maximum absolute beta difference **0.0004226784** (complete-separation fixture). Independent Python score check recovered all fixture SHA256s and computed Jeffreys adjusted-score infinity norms: max **1.9752e-5**.

**Numerical-quality caveat:** All-zero-event fixture emitted `brglmFit: algorithm did not converge` despite the returned `fit$converged = TRUE`, near-identical coefficients (difference 3.73e-6) and adjusted-score residual 1.48e-6. Increasing maxit to 200 and 500 did not clear the warning. Hence **8/8 coefficient agreement; 7/8 warning-free convergence**, not blanket clean fitting equivalence. Separation probabilities also trigger expected numerical warnings; no suppressing them in reporting.

The CRAN `logistf_1.26.1.tar.gz` source is available, but independent package validation **not run**: `mice`, `mgcv`, `formula.tools` and transitive dependencies/compiler tooling are missing. CH13's full **16-fit two-package** external equivalence remains BLOCKED.

Reproducibility handoff: `Cognitum_CH_C14_15_brglm2_External_Numerical_2026-11-02.zip` SHA256 `8fff9150a16b2724005f8afb183e5ea31bf46515bc4851c2e348186de8ff6f80`, with 7/7 internal payload hashes independently checked. It includes R scripts, CSV results, independent numerical audit, warnings diagnostic and full report. R executables and third-party Debian packages are **not redistributed** in this ZIP.

No Lu, Windows, G25 or Cognitum production change. Research-only external numerics; C14 scientific release **NO-GO**. GitHub is repository/milestone record, local container the development environment.
