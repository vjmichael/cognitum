# CH-C14-23 — Larger prospective ambiguity holdout and compact-box global bounds

**2026-11-02 | Research engineering scoped PASS; globally certified optimum 0; scientific C14 NO-GO.** Local Python/Linux experimentation; GitHub used only as repository/milestone record. No production C14, G25, Lu, or Windows modifications.

## Frozen protocol

SHA-256 `31cd3f5d01e40e496e59d48b4160a9a3a4894645509eca9eae4cdcaf3e618bde` was frozen before simulation. Prior CH22 source pinned at `02de1d5bc17c5b8ea630b639b119ce2420e6cc2401dba57747bf42ff466debee`, with a new CH23 six-start schedule and disjoint seed namespace. Six families × n=80/160 × 16 new seeds = **192 datasets**. Each tested at six starts with BFGS and L-BFGS-B: **2,304 attempts**.

## Observed results

- **2,298/2,304** optimization attempts met adjusted-score (<1e-4) and negative-Hessian-eigenvalue (<−1e-5) *local* conditions; 6 invalid attempts retained.
- **3/192** datasets had two distinct validated local maxima and were refused: two zero-imbalanced n=160 and one rare-1%-probability n=160. All three realized **zero observed outcome events**.
- **189/192** had a single *observed* validated local maximum. All remained research-only, with no global uniqueness certification or causal promotion.
- CH22's 4/96 is contextual only; different deterministic starts/budgets prevent treating CH22/CH23 as directly matched prevalence trials.

## Stronger bounded-optimality method, honest limitation

Implemented a mathematically conservative Jeffreys-logistic objective upper bound **on compact 3-parameter boxes**: endpoint upper bound on each Bernoulli log-likelihood contribution plus the log determinant of an information matrix formed from each observation's largest possible `p(1-p)` weight within that box. The latter is a valid Fisher-information Loewner upper bound in exact arithmetic. A 250-node branch-and-bound procedure on `beta0 ∈ [-10,1]`, each slope `[-5,5]`, ran on 12 prespecified datasets (one for each family/sample-size cell). **0/12 searches closed the upper-minus-incumbent objective gap**: remaining gaps **1.978 to 43.325**.

This is **not a certified global optimizer**: bounds are calculated with ordinary float64 (not verified outward-directed interval arithmetic), node budgets do not close, and a compact box cannot prove uniqueness over all real coefficients. It provides independently testable *upper-bounding logic*, and a precise account of where current global guarantees fail.

## Audit and deliverables

Independent generator reproduced and hashed all 192 input datasets; independent formula independently recomputed objectives/finite-difference gradients at all **195 local-maximum representatives**, checked all 2,304 receipts and 720 sampled points against 12 objective upper bounds. Maximum objective difference **4.89e-14**, maximum independent gradient **1.01e-7**. **10/10** regression tests PASS, 12/12 archive payload hashes and ZIP integrity verified.

Reproducibility package `Cognitum_CH_C14_23_Larger_Holdout_Bounded_Global_2026-11-02.zip` SHA256 `4a8c72987b1552a7754dfb43aff4b3b67c40c7a2986832d78c1924ca2eeb5c47` (includes frozen protocol, candidate and pinned code, all case receipts, bound searches, independent audit, tests and engineering report).

**Next gate:** investigate a directed-rounding interval branch-and-bound implementation with verified curvature bounds and explicit finite-domain caveats; expand preregistered heldouts only after freezing objective and thresholds. The externally managed `logistf` dependency/equivalence gate, causal interval coverage and independent scientific review remain open. **Scientific release NO-GO.**