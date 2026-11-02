# CH-C14-24 — Directed MPFR interval branch-and-bound with curvature bounds

**Date:** 2026-11-02 (America/Phoenix)  
**Disposition:** Small bounded-box engineering prototype **PASS**; complete CH23 ambiguity benchmark not re-executed; global-\(\mathbb R^p\) and scientific release **NO-GO**.  
**Scope:** Cognitum C14 isolated research. No production C14/G25, Lu, DLC, Windows, estimator routing or interval-reporting changes.

## Recovery provenance and gap

Reused CH21/CH22 Engineering Reports saved in the Library and the CH23 results recovered from prior conversation context. CH21 established that on `all_zero_n160_s06.csv`, two locally strict maxima at approximately `[-4.725286,0.261227,0.185059]` and `[-4.927711,0.037144,-0.698231]` coexist, separated by an objective difference of about 0.00508, and a third stationary point is a saddle. CH22 prospectively found 4/96 ambiguous synthetic datasets, all zero observed events, and refused them. CH23 recorded 192 datasets, 2,304 optimizer attempts, 3 ambiguous all-zero-event cases, and 12 compact-box numerical global-bound searches with positive gaps. CH23 identified lack of outward rounding and global-exhaustive bounds as an unsolved obstacle. The CH23 original ZIP/fixture were not mounted in the current runtime and are not in the inspected public `vjmichael/cognitum` main tree. **CH24 does not claim a rerun of CH23 or formal global certification of those cases.**

## Implementation delivered

`mpfr_interval.py` binds the installed **MPFR 4.2.2** via Python `ctypes`. All lower endpoints use `MPFR_RNDD` and all upper endpoints use `MPFR_RNDU` for parsing, arithmetic, `exp` and `log`. Input floats are rejected. Missing MPFR or invalid/nonfinite arithmetic refuses computation. The program never uses Python floats in proof comparisons (only in display and priority scheduling).

`verified_bnb.py` evaluates the exact Jeffreys-penalized logistic objective on one-, two-, or three-parameter finite boxes. It proves full column rank over exact-decimal rationals, groups identical design rows, constructs a strictly positive lower determinant enclosure from a nonzero exact Cauchy–Binet minor, and obtains positive upper bounds from Hadamard and optionally the full Cauchy–Binet sum for ≤20 distinct design rows. A per-group concavity/entropy likelihood cap tightens large boxes. Order-two forward interval automatic differentiation encloses gradient/Hessian. Taylor bounds and certified Hessian Gershgorin upper bounds, including a completed-square bound where all Hessian eigenvalues are certified negative, can sharpen global objective upper bounds. All half-widths/midpoints are exact rational quantities rendered as terminating decimals; no limited-precision Decimal rounding enters curvature proofs.

`verify_certificate.py` separately checks the model digest and exact design rank, feasible incumbent, complete pairwise box splitting, and every terminal leaf's upper bound at **higher MPFR precision**. A prior implementation's untrusted float display bounds are intentionally ignored. A status can be upgraded to `VERIFIED_BOUNDED_GAP` only when it independently recomputes all relevant inequalities. The replay shares the same mathematical bound code; it is **not an independently implemented interval package or a machine-checked formal proof**.

## Local test evidence

**11/11 unittest cases pass**, including directed interval endpoint checks, independent high-precision likelihood/objective samples, numerical derivative agreement with independent mpmath differentiations, Hessian enclosures at multiple interior points, a direct 1D sparse-outcome certificate, a 1D zero-event certificate, 2D compact-box certificate, 3D zero-event curvature certificate, tamper rejection, strict input validation, and required unresolved refusal under an insufficient node budget.

| Exact test fixture | Domain | Absolute objective gap tolerance | Nodes | Local result | Higher-precision verifier |
|---|---|---:|---:|---|---|
| 18 all-zero outcomes, intercept only | β ∈ [−6, 1] | 0.002 | 29 | `CERTIFIED_BOUNDED_GAP` | `VERIFIED_BOUNDED_GAP` |
| 27 all-zero outcomes, 3 predictors; compact local box | β₀ ∈ [−4.04,−3.96], β₁,β₂ ∈ [−.02,.02] | 0.07 | 1 | `CERTIFIED_BOUNDED_GAP` | `VERIFIED_BOUNDED_GAP` |
| Same 3-predictor compact box | same | 0.000001 | 1 | `UNRESOLVED_REFUSE_CERTIFICATION` | `REPLAYED_BUT_UNRESOLVED` |

The certified one-dimensional example had rounded lower/upper objective bounds of **−0.86704190764** and **−0.86610253637**; the recorded gap is **0.00093937**, under 0.002. The small three-dimensional box achieved a **0.05735536** upper-lower gap, under the requested 0.07 but **above** 0.000001. These demonstrations prove only bounds on **the specific input box**, not the scientifically important 3D CH21 pathological case or its unrestricted global maximum. They are engineering smoke fixtures selected during development, **not an independent prospective held-out study**.

## What is not established

- No upper bound on **unbounded** coefficient-space tails; therefore no global optimum across all real coefficients. No uniqueness proof and no resolution of the competing CH21/CH23 maxima.
- No production-grade performance evidence on the 192 CH23 datasets or large three-parameter zero-event studies. Three-parameter interval Hessian jets are expensive and broad boxes often need extensive subdivision.
- No independent formal verification, MPFI/Arb dual implementation, failure-injection or external libmpfr audit. Correctness is conditional on MPFR’s correct directed rounding and source implementation; replay alone cannot substitute for formal proof.
- No external `logistf`/`brglm2` equivalence, causal identification, confidence-interval calibration or preregistered coverage acceptance.
- No Windows packaging/test or cross-platform native solver admission.

## Reproduce

```bash
cd CH_C14_24
python -m unittest discover -v -s tests
python verified_bnb.py examples/zero_event_1d_input.json --tol 0.002 --max-nodes 200 --output /tmp/ch24_certificate.json
python verify_certificate.py /tmp/ch24_certificate.json
python verify_certificate.py examples/zero_event_3d_certificate.json
python verify_certificate.py examples/zero_event_3d_unresolved.json   # exit 2 by design
```

## Recommended CH25 follow-up

Recover the original CH23 source and data receipts into the research workspace, freeze the next held-out box schedule and proof budgets, benchmark MPFR/Arb or MPFI cross-validation, improve 3D Hessian enclosure speed (interval Cholesky / analytic derivative bounds / preconditioning), add rigorous coefficient-tail exclusion, and only then test whether the CH21/CH23 competing maxima can be distinguished by certifiable *global* rather than merely local objective gaps. Preserve mandatory refusal whenever the proof remains incomplete.

**Release decision: engineering proof primitive PASS at small bounded-box scope; C14 scientific/production NO-GO.**