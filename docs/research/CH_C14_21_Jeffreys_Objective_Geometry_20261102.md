# CH-C14-21 — Jeffreys-penalized objective geometry and competing roots

**2026-11-02 · Targeted post-hoc research diagnostic PASS · Scientific C14 NO-GO.** No production estimator, G25, Lu or Windows modifications.

The original CH20 zero-event fixture `all_zero_n160_s06.csv` was reexamined with its **exact SHA256 `5c046139451ed5c311dcf2bbef6b570d41f5b39193ce3fa9279c83a8f754dd5b`**. This dataset was selected after known nonconvergence and is **not a prospective blinded test**.

## Mathematical mechanism

For a binomial logistic model, the Jeffreys-penalized objective is
`J(beta) = loglik(beta) + 0.5 log det (X' W(beta) X)`, with `W_ii=p_i(1-p_i)`. Ordinary logistic log-likelihood is concave, but the added log determinant need not be concave in beta; this can create multiple stationary points. Solving the adjusted-score equation does not certify a maximum, uniqueness, or global optimality.

| Root from CH20 | Objective | Hessian eigenvalues | Curvature |
|---|---:|---|---|
| A | -0.9873512624 | -1.630371, -0.381259, **+0.042501** | **Saddle** |
| B | -0.9865658459 | -1.626142, -0.377606, -0.055447 | Strict local maximum |
| C | **-0.9814871344** | -2.253395, -0.364716, -0.105666 | Higher strict local maximum |

C exceeds B's objective by **0.0050787115**, making it the better of these two local maxima, **not a certified global optimum**. Eigenvalues remained stable under two central-difference step sizes.

## Independent optimizer experiments

- 120 deterministic starts × two local solver families (BFGS / L-BFGS-B) = **240 attempts**.
- **239/240** satisfied a pre-coded local stationarity/negative-Hessian test; **106** found C and **133** found B.
- Three bounded differential-evolution searches over beta0 [-10,1], slopes [-5,5] found C twice and B once. **These are heuristic bounded searches, not global-optimality proofs**.
- Independent raw-data finite-difference audit exactly reproduced three penalized objectives to max **2.22e-16** and gradient norm max **6.0e-10**.
- **8/8** new automated checks pass.

## Scientific disposition

**Retain original CH20 REFUSAL** for this ambiguous fixture. A higher local likelihood and apparently successful optimizer exit do not establish a globally defensible unique estimator. This investigation is a targeted **post-hoc mechanism analysis**, not a coverage validation or promotion gate.

Reproducible ZIP: `Cognitum_CH_C14_21_Jeffreys_Objective_Geometry_2026-11-02.zip`; SHA256 `9aa60423abc8b84c6c0d222a771b07fa15048d01656ef33cc3a0a7c3034b4d71`; all **11 payload SHA256 entries** verified after writing, ZIP archive integrity passed. Contains original fixture, CH20 candidate references, analysis source, all 240 local attempts, bounded heuristic results, independent score/objective audit, eight tests and engineering report.

Open gates: theoretical/certified global optimization if required; preregistered prevalence and numerical-safety holdout; external `logistf` equivalence; nominal coverage, real study provenance and independent statistical review. C14 scientific release still **NO-GO**. GitHub serves as research repository and milestone record only.
