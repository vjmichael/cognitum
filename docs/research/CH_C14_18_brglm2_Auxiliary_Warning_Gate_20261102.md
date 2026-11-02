# CH-C14-18 — brglm2 auxiliary-warning replay and guarded classification

**2026-11-02 · Research-only engineering PASS; scientific C14 NO-GO.**

Ran actual offline **R 4.5.0** with external **brglm2 0.9.2** on eight pinned CH13 numerical fixtures, each with both ordinary and explicitly-zero-offset logistic regressions (**16 fits**). All 16 returned main-fit `converged=TRUE`. Ordinary fit showed algorithm-nonconvergence **only for the all-zero fixture**; explicit offset eliminated that algorithm warning for that fixture. All 8 coefficient triples agreed ordinary versus offset to R printed precision (maximum delta 0); the two fit specifications differ only by a zero offset. This corroborates CH17's identified recursion through an auxiliary intercept-only null-deviance fit started at `qlogis(0)=-Inf`.

An independently implemented **Python/SciPy Jeffreys score audit** inspected all eight immutable fixture SHA hashes, sample/event counts, R convergence flags, coefficients, duplicate/missing results and warning provenance; maximum adjusted-score infinity residual `1.9751973923e-05`. This is a diagnostic, not an independently calibrated acceptance tolerance. **10/10 new tests pass**, including negative tests for false convergence, forged warning, changed coefficients and missing/duplicate records. Some other R warnings occur; do not conflate absence of this algorithm warning with no warnings of any kind.

**Production safeguard unchanged:** no warning-based override to CH16 fail-closed policy, no promotion, no causal certification. This narrowly explains the observed R 0.9.2 auxiliary-fit warning; it does not establish nominal coverage or valid identification.

**logistf equivalence remains blocked:** the CRAN `logistf` source is available, but `mice`, `mgcv`, `formula.tools` and transitive dependencies are not installed. Neither `logistf` nor the full two-package 16-fit equivalence was run. No Lu/Windows/production changes.

Reproducible diagnostic ZIP: `Cognitum_CH_C14_18_brglm2_Auxiliary_Convergence_Gate_2026-11-02.zip`, SHA-256 `85d299b1ec5181dd90f6fc9152250f501963b67a6dc6070d1e51731709cd7489`; **7/7** payload SHA hashes reverified after packaging. Includes R runner, raw 16-fit CSV, independent audit and 10 negative/positive tests. Requires the previously isolated R runtime and immutable CH13 fixtures, not redistributed inside ZIP. Local development; GitHub is repository/milestone record only.
