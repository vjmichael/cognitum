# Cognitum C14 G25K — preregistered kink-aware partial-identification research

**Frozen before any full held-out cohort.** Research-only. G25J/G25I baseline calculations are preserved byte-for-byte. No Cognitum production estimator, Lu source, native execution tool, policy decision, or causal-admission routing changes.

## Scientific question

Does m-out-of-n *multinomial subsampling* of the non-smooth sensitivity-bound endpoints reduce G25J's intermediate-Γ kink refusals without unacceptable coverage or width degradation relative to G25I exact Bonferroni–Clopper–Pearson bands? This is a **research candidate**, not a proved finite-sample or uniformly kink-valid interval. G25I's projection of simultaneous exact conditional binomial confidence intervals remains the finite-sample reference, conditional on the analyst's Γ restriction and sampling assumptions.

## Distinct inference targets

For a *fixed, externally supplied* Γ, the target is simultaneous coverage of the entire **population identified set** [L(P,Γ),U(P,Γ)], not merely the simulator's true treatment effect and not pointwise coverage of one partially identified parameter. Coverage is scored as `outer_lower <= true_L AND outer_upper >= true_U`. A Γ assumption may be false even when the identified set itself is correctly estimated; the Monte Carlo simulator's true ATE and required Γ are diagnostic-only and NEVER certify causality. Numerical success never establishes absence of hidden confounding.

## Frozen generators and seeds

Seven newly specified synthetic families, each independently constructed from W,U,T,Y causal equations and sampled as the induced observed joint multinomial P(W,T,Y): (1) smooth measured W independent of U in outcome/treatment; (2) exact sensitivity kink at Γ=.25; (3) local-to-kink triangular-array family with distance 0.20/sqrt(n); (4) hidden joint confounder U; (5) rare binary Y; (6) thin-but-positive treatment support; (7) structural-zero treatment support. All seven are independent of G25I/G25J's generator parameters. Structural zero is a negative control; thin positive and rare outcome are stress controls and included in attempted denominators. For the local-to-kink family the population changes with n by construction; do not describe it as one fixed population.

Cohorts A and B use **disjoint** seed starts 12,300,001 and 22,300,001, respectively. Each of seven families × n∈{900,1800} × 500 cases per cohort yields 7,000 receipts/cohort or 14,000 total. Methods: G25I CP reference, original G25J correlated-normal two-endpoint delta method (with unchanged refusals), and G25K m-out-of-n subsampling. Γ∈{0,.10,.25,.50,1}. Exactly **210,000 method/Gamma attempts**; no discarded datasets. B=199 subsamples, m=floor(n^.8), common seed per case, same resamples reused for every Γ. Invalid resamples must be counted. At least 190/199 valid subsamples required to compute an interval; otherwise refuse. True missing W/T arm is an unconditional refusal for conditional inference. No a posteriori choice of Γ, m, B, acceptance threshold, or sample seeds.

For valid bootstrap draws, use the exact nonlinear sensitivity endpoints, *not the G25J smooth gradient*. For a draw of m, calculate `T* = max(sqrt(m)*(L*_m-Lhat), sqrt(m)*(Uhat-U*_m))` and select the empirical 95th percentile (higher order statistic); output `[Lhat-c/sqrt(n), Uhat+c/sqrt(n)]`, clipped to [-1,1], with `c=max(0,quantile(T*))`. Sign convention protects both identified-set endpoints. **The m-out-of-n method is not a mathematically established uniformly valid finite-sample procedure near a kink** and must be rejected if its calibration evidence fails.

## Predeclared screen (no automatic promotion)

For each positive-support family/n/Γ cell, both cohort-pooled and cohort-specific rates must be reported. Screening requires >=99% method completion, >=93% set coverage on all completed datasets, Wilson 95% interval compatible with nominal .95, and matched mean width <=95% of G25I on the exact same accepted datasets. The 95% nominal target must be examined per cell and never salvaged by pooled averages. No promotion for any procedure merely because it is wider. Structural-zero controls require zero conditional intervals. Near-kink cases may run without an arbitrary proximity refusal, but any Monte Carlo undercoverage defeats promotion. G25I CP failures to cover endpoints on supported cases are audit-critical. Report coverage conditional on success separately from unconditional issued-interval rate and refused-case counts.

## Independent verification

- Numerical equality with legacy scalar G25J identified-set evaluator and legacy G25I exact reference.
- Independent deterministic population, case-count and hash regeneration for every receipt; full refusal and coverage accounting; at least 12 stratified exact numerical replays per family/size/cohort.
- Independent statistical checks for standard errors, reference projections, and adversarial tampering of counts, Gamma statuses and method coverage flags.
- The G25K source, preregistration, tests, audit source and baseline SHA-256 are hashed in freeze JSON *before* the evaluation datasets are generated.
- Record machine resources, duration, operational changes and any protocol deviation. No research result can authorize production; require mathematical justification, external methodological review, additional independent SCMs and separate user authorization.