# Cognitum CH-C14-24: MPFR-directed interval branch-and-bound

**Research-only / engineering prototype.** This implementation establishes a **bounded-coefficient-box, epsilon-global-objective-gap certificate** for the Jeffreys/Firth-penalized binary logistic objective, conditional on the MPFR library and the arithmetic/branching implementation. It does **not** prove global optimality over unbounded real coefficient space, estimator identification, a unique maximum, valid causal inference, calibrated confidence intervals, or production-readiness. **C14 scientific release is NO-GO.** No changes to Cognitum production, pinned G25, Lu, DLC, or Windows.

## Recovered CH21–CH23 problem

For binary y and full-column-rank X:

\[
 J(\beta)=\sum_i\left[y_i x_i^\top\beta-\log(1+\exp(x_i^\top\beta))\right]
   +\frac12\log\det I(\beta),\qquad
 I(\beta)=X^\top\mathrm{diag}(p_i(1-p_i))X.
\]

The log information determinant may make J nonconcave. CH21 found two different strict local maxima and a saddle on one all-zero fixture. CH22 found 4/96 ambiguous cases; CH23 reported 3/192. Neither multi-start optimization nor the CH23 ordinary-floating box upper bounds were certified global searches. The CH23 raw fixture/package was not available in the present working runtime; **its previously reported results were not rerun**.

## Dependencies

- Python 3.11+ (standard library at runtime).
- `libmpfr.so.6` (tested on Linux with MPFR 4.2.2). Missing MPFR causes immediate refusal. No Python fallback to ordinary float.
- `mpmath` only for the independent numerical cross-check tests, **not** for the solver or its proof logic.
- Tested specifically in the Linux environment. Windows DLL discovery/ABI, packaging, and physical-machine acceptance are **not** done.

## Usage

```bash
cd CH_C14_24
python verified_bnb.py examples/zero_event_1d_input.json --tol 0.002 --max-nodes 200 --bits 160 --output certificate.json
python verify_certificate.py certificate.json
python -m unittest discover -v -s tests
```

Input JSON uses **decimal strings**, not JSON numbers, for every x and box endpoint:

```json
{
  "rows": [
    {"x": ["1"], "y": 0},
    {"x": ["1"], "y": 1}
  ],
  "bounds": [["-5", "1"]],
  "seeds": [["-0.6"]]
}
```

Only one to three coefficients and full-rank finite designs are accepted. Tolerance is an *absolute objective-value gap*, not coefficient error or confidence-interval precision. Increasing `--bits` raises MPFR precision, not coverage. When the proof tree cannot close its gap within the node budget, status is `UNRESOLVED_REFUSE_CERTIFICATION`.

## Proof outline

1. All source data and box endpoints are interpreted as exact base-10 rational numbers. Midpoints and half-widths are computed exactly with rational arithmetic, **not** rounded Decimal context arithmetic. Integer/rational rank is checked exactly.
2. MPFR sets lower endpoints with `MPFR_RNDD` and upper endpoints with `MPFR_RNDU` for every elementary arithmetic operation, `exp`, and `log`. Invalid/infinite operands, missing MPFR, and failed positive-determinant bounds refuse the computation. Output floats are display fields only; they never control a proof comparison.
3. For every box, Fisher information is strictly positive definite at each finite point. A single exact nonzero Cauchy–Binet minor supplies a **positive determinant lower bound**. Hadamard supplies a safe determinant upper bound. For at most 20 distinct design rows, the full nonnegative Cauchy–Binet expansion sharpens both; grouped sufficient counts are incorporated exactly. The ordinary interval determinant gives another upper/lower enclosure when useful.
4. The likelihood and log-determinant sum are interval-enclosed. The upper bound may be tightened with separate concave Bernoulli likelihood upper bounds (all-zero, all-one, and entropy). On boxes where interval determinant inversion is valid, second-order interval automatic differentiation computes the full Hessian enclosure. Taylor/interval-gradient bounds and Gershgorin/negative-curvature completed-square bounds can improve the objective upper bound.
5. Branch-and-bound splits a node into two **exactly covering** child boxes; an observed feasible point provides a lower bound on the maximum. A box is closed only when its rigorous objective upper endpoint is no greater than that incumbent lower endpoint plus requested tolerance. Every leaf participates in the final gap condition; a budget exhaustion never silently closes a node.
6. The separate `verify_certificate.py` script revalidates the model digest, exact rank, every split/cover, the feasible incumbent, and every leaf upper bound with a higher MPFR precision. It **reuses the same mathematical bound implementation**, so it is a separate proof *replay*, **not** an independently formal-verified implementation. Stored display upper bounds are not trusted. A claimed success that replay cannot establish is rejected.

## Caveats and next gates

- These are finite compact boxes. Establishing a global maximum on all of \(\mathbb{R}^p\) also requires a separately proved exclusion/tail bound outside the box. No such result is claimed.
- An epsilon-gap certificate is not proof of an *exact* unique maximizer. Two distinct maxima may be within the certified gap. Scientific response and production output must continue to refuse ambiguous data.
- MPFR promises correct directed rounding; this Python/ctypes binding has unit and cross-precision audits but has **not** been independently machine-checked or formally verified in a proof assistant. No external arb/MPFI second implementation was cross-validated.
- Performance grows fast with dimension and number of distinct design rows; three-coefficient curvature jets are substantially slower than direct determinant enclosures. Test on small bounded examples first.
- To integrate with CH23 held-out benchmark, recover its exact source/data/digests and run a frozen holdout separately. No claim to have recertified the 192 prior datasets or recovered the pathological CH21 CSV.
- No R `logistf` / `brglm2` dependency or numerical-equivalence gate is discharged here. No causal effect / coverage / interval-width gate is discharged here.
