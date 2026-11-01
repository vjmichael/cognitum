# Cognitum C14 G25M — Frozen research protocol (before held-out seeds)

**Date:** November 1, 2026. **Scope:** independent scientific research, NOT Cognitum production or Lu. No automatic causal admissions; Γ=0.25 is a fixed, analyst-supplied risk-difference sensitivity assumption.

## Research question

G25L's Bonferroni joint/hybrid confidence regions achieved conservative set containment but produced intervals wider than the G25I CP reference. Does *globally sharp* projection of the exact **hybrid joint confidence polytope** have any chance of satisfying the G25L preregistered requirement that mean interval width be at most 0.95 of the matched G25I CP mean width? Test this using a mathematically certified **lower bound on the sharp projected width**: optimize two attainable confidence-region laws in opposite endpoint directions. The span `U(q_high,Γ) - L(q_low,Γ)` is a lower bound for the width of **any** interval covering the entire Γ-identified set for every law in that region.

The scientific conclusion is a *negative feasibility certificate* when the sample-cell mean attainable span exceeds 0.95 times mean G25I reference width, not a claim of sharp global optimization. An independent global branch-and-bound provides valid outward enclosures and openly reports nonzero optimality gaps when unfinished. Γ=1 has an independent exact linear-programming solution on the original eight-cell probability polytope.

## Methods frozen before evaluation

- Hybrid region: eight binomial CP bounds with total α/2, plus seven conditional binomial CP constraints with total α/2, all intersected with multinomial simplex; conditional probability restrictions are encoded as linear inequalities on the original eight joint probabilities.
- Exact reduction to four treatment-arm totals: outcome success probabilities are extremized analytically conditional on arm totals. This preserves all joint constraints.
- Candidate witnesses: SLSQP proposes arm masses, a separate HiGHS linear program repairs any numerical constraint deviation, then the full eight-cell witness is independently checked against every region constraint. Any optimizer failure yields the valid empirical-law witness, never a fabricated point.
- G25I CP reference frozen from G25L baseline; Γ=.25 is the primary gate with no post-hoc Γ selection. Paired comparisons use every attempted dataset. Negative structural-zero controls refuse all conditional inference.
- Both cohorts: 500 new seeds per family/size/cohort. Six positive families: `exact_kink`, `local_kink`, `rare_binary`, `thin_positive`, `asymmetric_hidden`, `rare_reversal`; n=900,1800. A seeds from 55,000,001; B from 66,000,001. **12,000 positive datasets**, 1000 per family/size cell. Additional structural-zero controls: 500 per size/cohort, **2,000 negative cases**. No G25I–L holdout seeds reused.

## Gate requirements

1. Mathematical correctness: region and reduced-space derivation; exact feasibility checks and Γ=1 LP identity; correct outward certificates with explicit optimization gap.
2. Reproducibility: two disjoint frozen cohorts; complete signed-by-hash receipts; no dropped optimizer failure or refusal; independent replay/audit of every positive witness and every negative control.
3. Safety: zero invalid conditional outputs under observed structural zeros; no automatic causal admission; hidden confounding not claimed detectable; no inferred validity of Γ.
4. Scientific screening: ≥99% completion, Wilson-interval uncertainty around empirical population identified-set coverage, ≥93% empirical coverage, nominal 95% compatibility, **mean width ≤0.95 × matched G25I CP**, n≥1000 independent datasets per cell. **One mathematically certified no-go width cell is sufficient to rule out promotion for the current hybrid-region method**, regardless of solver sophistication. Confidence-region guarantee is conservative and distinct from the empirical nominal calibration screen.
5. Independent verification: numerical oracle-independent checks, feasibility witnesses, linear-program verification, held-out families, regression checks and operational cost. External independent scientific review, native R `logistf`/`brglm2` equivalence for the older sparse-logistic milestone, plus separate user authorization would remain required before any production algorithm change.

**Decision rule:** No automatic promotion even if every research gate passes. If any gate fails, preserve failure evidence; do not tune alpha, Gamma, the seed list, thresholds, or resample rules based on holdout results. GitHub is repository/archive only, not the test runtime.