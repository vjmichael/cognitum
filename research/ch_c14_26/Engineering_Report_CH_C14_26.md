# Cognitum CH-C14-26 — Loewner determinant and analytic-curvature frozen CH23 replay

**Date:** 2026-11-02 (America/Phoenix) | **Engineering:** verified search replay | **Global/R³ and C14 scientific release:** NO-GO.

## Scope, frozen inputs and resource plan

This is research-only development on the original 15 CH23 datasets from CH25: 12 predetermined index-0 bounding cases and three independently recorded zero-event ambiguity cases. No regenerated replacement examples, altered outcome tables, modified CH25 evidence or production Lu/Cognitum/G25 changes. The original CH23 dataset hashes are inherited from CH25 provenance audit; each CH26 input is matched byte for byte to its frozen CH25 input SHA-256 and original CH23 identifier.

- Frozen protocol SHA-256: `48d7c5193b806da152a9cc3ec173529333a5af752c278f20238af9a3215d07bc`; protocol was written before any full-cohort solver execution.
- Root box: `[-10,1] × [-5,5] × [-5,5]`; objective tolerance `0.05`.
- Search nodes/case: CH25 `31` → CH26 `127` (~4.10×); MPFR solving/replay: `160` / `224` bits.
- Max Hessian-assisted node calculations/case: 2; only narrow boxes with maximum width ≤ 2.75. The Hessian attempts are optional conservative upper-bound tightenings, independently recomputed on the leaves as needed.

## Mathematical improvements

Let each distinct predictor `x_i` represent `n_i` observations, with `w_i(β)=σ(x_iᵀβ)(1−σ(x_iᵀβ))`. On every parameter box B, directed MPFR supplies `0 < w_i(β) ≤ u_i`. Construct `U_B=Σ n_i u_i x_i x_iᵀ`. Then `I(β) ⪯ U_B`; since the information matrices are positive definite, `det I(β) ≤ det U_B`. The MPFR outward-rounded interval determinant of `U_B` is intersected with the old termwise Fisher/Leibniz and Hadamard determinant bounds. The positive Cauchy–Binet reference minor certifies a strictly positive determinant lower bound, even when naïve interval expansion crosses zero.

The ordinary logistic log-likelihood `ℓ(β)` is globally concave. Therefore each frozen anchor `c` gives a valid tangent upper bound `ℓ(β) ≤ ℓ(c)+∇ℓ(c)ᵀ(β−c)` over the root and every descendant box. Intersecting this with per-observation scalar binomial maxima reduces interval dependence without assuming concavity of Jeffreys-penalized **J** itself.

For interval curvature, analytic identities are `I_a=Σ n_i w_i(1−2p_i)x_ia x_i x_iᵀ`, `I_ab=Σ n_i w_i[(1−2p_i)^2−2w_i]x_ia x_ib x_i x_iᵀ`; hence `∂_a J = ∂_a ℓ + ½tr(I⁻¹I_a)` and `∂²_ab J = −I[a,b] + ½[tr(I⁻¹ ∂²_ab I)−tr(I⁻¹(∂_b I) I⁻¹(∂_a I))]`. The first term is ordinary logistic information, the traced terms are the Jeffreys correction. This code evaluates the terms using directed MPFR interval sums, interval adjugate, and a positive determinant enclosure. It is more efficient than the CH24 2nd-order interval-jet path but its wide-box curvature enclosures remain loose.

## Complete frozen-cohort results

**15/15 cases replayed**; 0 finite-box `0.05` global gaps certified; 15 remain `REPLAYED_BUT_UNRESOLVED`. The first-order and determinant improvements must not be misread as unbounded-global optimization or causal identification.

| Original CH23 case | CH25 gap, 31 nodes | CH26 gap, 127 nodes | Gap reduction | Solver CPU (s) | Replay CPU (s) |
|---|---:|---:|---:|---:|---:|
| `zero_balanced_n80_i00` | 4.8425 | 3.3651 | 30.5% | 41.6 | 10.5 |
| `zero_balanced_n160_i00` | 5.6177 | 4.2134 | 25.0% | 80.9 | 21.6 |
| `zero_imbalanced_n80_i00` | 5.3209 | 3.0590 | 42.5% | 39.7 | 9.2 |
| `zero_imbalanced_n160_i00` | 5.9379 | 3.4857 | 41.3% | 72.5 | 16.5 |
| `one_event_n80_i00` | 8.4297 | 3.8914 | 53.8% | 36.7 | 9.3 |
| `one_event_n160_i00` | 8.2890 | 4.2405 | 48.8% | 79.2 | 22.5 |
| `rare_1pct_n80_i00` | 10.3717 | 4.0850 | 60.6% | 35.5 | 7.9 |
| `rare_1pct_n160_i00` | 12.7388 | 4.9595 | 61.1% | 81.2 | 21.6 |
| `rare_5pct_n80_i00` | 17.1995 | 4.4486 | 74.1% | 35.1 | 10.2 |
| `rare_5pct_n160_i00` | 46.4973 | 4.3248 | 90.7% | 85.4 | 26.0 |
| `quasi_separated_n80_i00` | 59.6543 | 5.3476 | 91.0% | 39.6 | 10.5 |
| `quasi_separated_n160_i00` | 164.2419 | 8.1865 | 95.0% | 81.4 | 21.5 |
| `zero_imbalanced_n160_i05` | 5.5373 | 3.1314 | 43.4% | 73.6 | 16.4 |
| `zero_imbalanced_n160_i07` | 5.8356 | 3.2962 | 43.5% | 74.3 | 17.2 |
| `rare_1pct_n160_i13` | 5.6233 | 4.2038 | 25.2% | 72.2 | 19.7 |

- Mean gap: 24.4092 → 4.2826; median: 8.2890 → 4.2038.
- Improvement: 15/15 smaller than CH25, 0/15 larger. Median relative gap reduction: 48.8%.
- Total cumulative solver CPU seconds (sum across processes): 929.0; higher-precision replay CPU seconds: 240.5. Because searches ran concurrently, summed wall times are **not** elapsed cohort clock time.

- Curvature probes: 30 node-level analytic Hessian evaluations; 0 selected as tighter than the direct objective enclosure. Determinant and likelihood bounds drive improvements if this count is zero.

## Analytic interval curvature timing

Same original CH23 zero-balanced n=80/160 predictor arrays, 160-bit MPFR, narrow test box `[-4.5,-4.49]×[0,0.01]²`. Both analytic derivative enclosures contain the CH24 jet derivative enclosures at the box midpoint. Measured values are for this single local execution, not a general performance guarantee.

| Original dataset | CH24 2nd-order jet (s) | CH26 analytic (s) | Speed ratio |
|---|---:|---:|---:|
| `zero_balanced_n80_i00` | 2.869 | 1.375 | 2.09× |
| `zero_balanced_n160_i00` | 5.808 | 2.203 | 2.64× |

## Verification and limitations

- Each original CH25 input SHA-256 and CH23 dataset identity was checked before evaluation. The prior CH25 independent data-reconstruction audit also passed unchanged.
- Solver uses `max_nodes=127`, directed 160-bit MPFR; verifier reads each of the 64 terminal leaves and recomputes all upper bounds at 224-bit MPFR, checks the partition, data/model digest, fixed anchor, feasible lower incumbent, frozen tolerance and source protocol, then independently decides the bound gap. The verifier uses the same mathematical bounding method, so this is reproducible MPFR replay, not a separate formal-verification proof assistant.
- The numerical gap table uses outward double approximations for *display*; only exact MPFR endpoint comparisons determine certification. No time/energy scaling or bound tightening is extrapolated beyond this finite cohort.
- Historical CH23 refusal remains mandatory on all three ambiguous zero-event datasets, irrespective of within-pair objective ranking. No result proves uniqueness or global optimality outside the finite box. Release status stays **NO-GO**.
- Full source, frozen protocol, 15 original-input references, proof partitions, replays, case CPU/wall receipts, adversarial tests and hashes are bundled. Research branch only; main production untouched.

## Next research gate

Tighten **likelihood–information coupled bounds** and use affine-Taylor/interval Newton contraction selectively near the strongest leaves. Consider independently established tail bounds on the unbounded coefficient domain. Reuse this exact frozen cohort for comparisons; any new acceptance gate or study cohort must be prospectively frozen before running.
