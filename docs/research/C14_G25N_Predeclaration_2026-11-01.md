# Cognitum C14 G25N — New confidence-region construction and inversion research

**2026-11-01, before held-out runs.** Independent Cognitum-only research. No production estimator change; no changes to Lu. All findings, including adverse performance, retained.

## Scientific motivation

G25M proved a no-go only for G25L's *hybrid CP joint region*: even its best possible sharp projection could not beat the G25I width by 5%. G25N must not tune that old region's error allocations using G25M holdout outcomes. Instead, study two genuinely different inferential ideas:

1. **Nonparametric Dvoretzky–Kiefer–Wolfowitz (DKW) multinomial confidence region.** Fix the lexicographic eight-category ordering (W,T,Y) before sampling; for n iid categorical draws use epsilon=sqrt(log(2/alpha)/(2n)), alpha=.05. The 7 cumulative frequency constraints intersect with the eight-simplex to define a joint 95%-or-better confidence region. No assumptions of smooth causal sensitivity endpoints. Compute rigorous mathematical ratio extrema via Charnes–Cooper linear-fractional programming over this *different* nonrectangular polytope; then apply the monotone G25L sensitivity-bound outer enclosure at Gamma=.25. LP numerical optimality remains a solver-precision risk requiring independent cross-checks. Missing observed W/T arm fails closed. A zero denominator *possible within the region* causes a conservative [0,1] ratio range, never numerical extrapolation.
2. **Pointwise Monte Carlo likelihood-ratio inversion research.** At a fixed candidate eight-cell law q, the deviance T=2*sum k_i log(k_i/(nq_i)) is ranked against B=199 independent Multinomial(n,q) null simulations. The p-value (1+#simulated T>=observed T)/(B+1) is superuniform by exchangeability at the true q, including sparse and boundary cases. This is NOT a production confidence region: an exact global inversion and projection over all q is not implemented. Use simulator-known q only in the research validity evaluation and never in the deployable DKW interval.

## Frozen holdout design

- Two disjoint cohorts, A starting seed 97,000,101 and B 98,000,101, with family*100000 and size*20000 offsets plus i=0..499; development/pilot seeds 88,111,001 and 88,225,001 are excluded.
- Seven independent synthetic families inherited exactly from frozen G25L: exact_kink, local_kink, rare_binary, thin_positive, asymmetric_hidden, rare_reversal, structural_zero. n=900 and 1,800; 500 datasets per family/size/cohort = **14,000 total**, of which **12,000 positive** and **2,000 structural-zero negative controls**. Per positive family/size, 1,000 cases across two cohorts.
- Gamma fixed to 0.25, alpha fixed at 0.05. Every original dataset, null simulated rank p-value, DKW containment, returned interval or refusal, reference width, estimated-set truth and simulator hash recorded; all attempts count in denominators. No method changes after SHA-256 freeze.
- Primary new-region acceptance: 99% method completion, full population identified-set inclusion >=93%, Wilson 95% confidence interval compatible with nominal 95%, and mean width <=0.95 of the **matched G25I conservative reference** in *every* positive cell. Structural-zero refuses 100%. No automatic causal confidence certification.
- MC-LRT pointwise-calibration diagnostic: empirical false-rejection rate should be near 5% in each family/sample-size cell (Wilson uncertainty includes .05; no statistical power claims from these null-only experiments). Candidate true q is simulator-only; MC test does not issue intervals.
- Independent numerical cross-checks, exact structural audits, bounded numerical replays, adversarial receipt verification, computational cost accounting, independent source review and explicit production authorization are separate gates.

## Decision rule

An unfavorable result is not a reason to change alpha, the fixed cell ordering, model families or seeds. Report all rejection/coverage/refusal rates, even if the method is too conservative or the MC approximation is too noisy. The DKW region coverage theorem is a mathematical conditional statement about a fixed iid multinomial law; it does NOT establish identifiability, validity of Gamma, absence of hidden confounding, or valid causal inference in arbitrary observational data. No algorithm promotion without passing all broader G25 gates and explicit user authorization.