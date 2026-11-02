# CH-C14-24 — Outward-rounded Jeffreys interval branch-and-bound with curvature enclosures

**2026-11-02 · Isolated Linux research prototype · bounded epsilon-optimality demonstrated in 2/3 tiny test boxes; no full R³ global certification; C14 scientific NO-GO.** No Lu, Windows, G25 or production C14 changes.

## Implementation

Built `interval_solver.py` using `mpmath.iv` (55 decimal-digit interval arithmetic, with outward-rounded endpoints) rather than float64 plus guessed tolerances. For a compact 3-coefficient parameter rectangle, derive a row-wise upper bound on the Bernoulli log-likelihood and a positive-semidefinite Fisher-information upper matrix by bounding each possible logistic weight. Use the positive-monotone log determinant with interval arithmetic. A feasible fitted point supplies an interval-enclosed *lower* objective value. Branch-and-bound splits the widest normalized coordinate and maintains the highest unpruned or tolerance-pruned upper bound; the criterion `rigorous_upper - feasible_lower <= epsilon` establishes *objective epsilon-optimality within the stated finite box*, conditional on the trusted interval library, not exact optimizer identity.

Implemented an interval Hessian including the Jeffreys penalty `0.5(tr(I^{-1}I_jk)-tr(I^{-1}I_k I^{-1}I_j))`. A numerical eigensystem chooses an optional coordinate transform Q, but a separate **interval determinant check proves Q nonsingular**, and an **interval Gershgorin test** on `Q^T H Q` proves Hessian strict negativity throughout a box by congruence, when the test passes. A singular/inconclusive interval never certifies curvature. The coordinate transform is a preconditioner, not a source of trusted eigenvalues.

## Frozen research execution

Pre-run protocol SHA256 `5cb55938029b1abbfdea8a1de28d9766999f1743b5170ce60785f7e496e4fb89`; pinned interval solver SHA256 recorded in that protocol; pinned CH23 generator byte-for-byte retained. Three finite-box cases:

| Box | Objective upper - feasible lower | Requested epsilon | Bound result | Interval curvature |
|---|---:|---:|---|---|
| Small rare n=80, neighborhood radius 5e-5 | 0.0010479962 | 0.005 | **epsilon enclosed** | **strictly negative Hessian** |
| Wider rare n=16, radius .004, 30-node cap | 0.0112956217 | 0.002 | **NOT certified** | Inconclusive |
| Tiny radius 1e-5 neighborhood of previously known ambiguous CH21 n=160 fixture | 0.0000855903 | 0.003 | **epsilon enclosed within box** | **strictly negative Hessian** |

**Important:** The CH21 data contains distinct maxima elsewhere. Certification on the tiny box around one local maximum **does not** resolve that dataset's full-domain multi-root ambiguity. All results explicitly prohibit production promotion and full R³ global certification.

## Independent reproducibility

- **12/12** positive and negative unit tests passed, including interval enclosures, invalid boxes, refusal for unclosed objective gap, source pins, curvature classification and prohibition on global certification.
- Independent 90-digit *point-oracle* audit of raw objective values (separate from the interval-bound implementation) checked 3 result records, **108 sampled points**, feasible lower bounds and upper enclosures. Audit **PASS**. These sampled comparisons are sanity checks; mathematical enclosure relies on derived interval formulas and `mpmath.iv`.
- ZIP `Cognitum_CH_C14_24_Verified_Interval_BnB_2026-11-02.zip`, SHA256 `1337946d3c77ef9f6f6a743db50bde8ca58c4e9c405e29fac3975b0a2280d8fe`; ZIP integrity and **13/13 payload SHA256 checksums** verified. Self-contained research code includes pinned CH23 generator and CH21 fixture/results, frozen protocol, recorded outputs, independent audit, tests, report and README.

## Precise limitation

This is a **working, interval-arithmetic-based prototype**, *not* a formally verified implementation. It trusts correctness of the mathematical bounding argument and the mpmath interval backend; no external directed-rounding reference or proof assistant verified the machine operations. No result claims a global optimality certificate outside the finite box, unique stationary point across R³, or a causal-effect confidence interval. Broad boxes still suffer loose bounds and node-limit exhaustion. External R `logistf` equivalence, causal calibration, study provenance and independent scientific review remain open. **C14 scientific release remains NO-GO.**

Next CH25 candidate: interval-Newton/Krawczyk root enclosures, stronger determinant bounds, certified compact-domain search with substantial node budget and independent interval-library checks before reconsidering ambiguous datasets. GitHub is repository/milestone record only; all work executed locally.
