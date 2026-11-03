# CH40-B Engineering Acceptance — Independent Coupled, Taylor and Interval-Newton Bounds

**Date:** 2026-11-03  
**Branch:** `cognitum/ch-c14-40b-independent-coupled-taylor-newton-20261103`  
**Input:** The original externally SHA-256 pinned CH39 full reproduction ZIP containing 15 frozen CH23 cases.  
**Scientific result:** `NO_GO`; no unrestricted or finite-box 0.05 gap proved.

## Independent mathematical work

1. **Likelihood–Fisher coupling.** For a symmetric strictly positive definite rational matrix Q, logdet F is upper-bounded by trace(QF)-logdet Q-d. The logistic log-likelihood plus Fisher-weight surrogate is strictly concave over each p in (0,1), allowing a global supporting-line upper. Numeric tangent selection is not proof input. The CH40-B implementation uses `Fraction` for matrix geometry and SPD conditions, `Decimal` directed operations and widened transcendental intervals. No old MPFR/Jet/coupled routines are imported.
2. **Full Firth objective derivatives.** Computes interval-valued analytic gradient and Hessian, including derivatives of the Fisher matrix determinant. A Cauchy–Binet positive lower determinant certificate is intersected with an independently formed interval determinant to improve the inverse enclosure. A second-order Taylor enclosure was checked on a tiny interior box near the incumbent on each of the 15 original cases. Numerical derivative cross-checks additionally tested one original case using independently evaluated mpmath finite differences.
3. **Krawczyk interval Newton.** Independently forms a Krawczyk enclosure from original-data score and Hessian intervals. Tests root exclusion, contraction and no-gain for small interior boxes. Original CH29 certificates had zero Newton proof events; no test box contracts the frozen search domain. Forged too-narrow contraction and false exclusions are rejected.

## Measured research acceptance

- 15/15 frozen original case checks PASS (127 nodes/case, 64 leaves/case: 1,905 partition nodes, 960 independently recomputed coupled upper enclosures).
- 766/960 leaf coupled upper bounds tighter than CH40-A's independent **direct** bounds (not the legacy producer bounds).
- 15 independent Taylor bound checks around original incumbents, and 15 Krawczyk test boxes: 5 `CONTRACTED`, 2 `NO_STATIONARY`, 8 `NO_GAIN`.
- 20/20 mathematical, adversarial and source-integrity unit tests pass on development Linux host; optional high-precision numerical derivative test requires `mpmath`.
- All original cases remain scientifically unresolved; no production release authorization.

## Known remaining gaps

- Producer CH27/28/29 specialized local certificate values are often tighter; a conservative independent CH40-B bound does not certify a smaller producer-specific upper or disprove it. Independent replay of exact producer strategies, including tailored Taylor models, still required.
- CH40-B analytic Taylor and Newton are tested locally on independent original-data boxes, **not all nodes in original 15 archived trees**. No original Newton exclusion or contraction existed to replay, so those must instead be prospectively frozen and independently generated.
- Full mathematical independence in attestor CH39 requires a new protocol, cross-account lifecycle tests, proof-cert format extension and one-shot witness binding. None of this is integrated in production.
- Work is finite-box; it neither resolves objective behavior outside the frozen root nor proves global optimality. No novel scientific certainty should be inferred from cryptographic or consistency passes.
- Windows CH40-B execution not yet performed. The separate prior CH25–31 native Windows MPFR benchmark passed 113/113 portable scheduled checks and is a distinct acceptance record.
