# Cognitum C14 G25L — joint confidence-region projection preregistration

**Date:** 2026-11-01 (America/Phoenix). **Scope:** independent, local-first scientific research; no Cognitum production algorithm change; no Lu modification; no automatic causal admission.

## Scientific question

Can a finite-sample, simultaneous observed-law confidence region projected through kinked Gamma sensitivity bounds improve G25K's undercoverage at non-smooth points without sacrificing completion, and how much precision does honest coverage cost relative to G25I's seven-conditional-Clopper–Pearson baseline?

- Main candidate **joint8**: two-sided exact Clopper–Pearson interval for *each* of eight joint P(W,T,Y) cells with nominal marginal alpha/8; intersect the eight intervals with the multinomial simplex. Bonferroni guarantees the true joint law is in the region with probability >= 1-alpha under iid multinomial sampling. Project through the exact piecewise sensitivity-bound map. The implemented projection uses exact marginal linear-fractional ratio bounds for each conditional probability then an outer rectangular enclosure; therefore it can be conservative relative to *sharp* global optimization.
- Secondary **hybrid**: joint8 region at alpha/2 and seven G25I conditional CP intervals at alpha/2, then intersect the coordinatewise parameter ranges. Union bound gives simultaneous 1-alpha coverage of the *combined* restrictions. This too is a conservative outer projection and not a calibrated 95% normal interval.
- Independent reference **G25I exact CP**: original seven Bonferroni conditional intervals with total alpha.
- Exploratory prior-method comparator **G25K m-out-of-n**: original frozen 199 draws, n^0.8 and >=190 valid rule; **not** a validated 95% procedure.

All methods retain all observed arm-missing refusals. Γ∈{0,.1,.25,.5,1} is a user-specified **risk-difference selection bound** and not estimated or verified from observed data. Primary target: simultaneous coverage of *both population identified-set endpoints* when conditional estimation is defined. Coverage conditioned on issuing a result is an empirical metric, **not** the same guarantee as P(issue and miss) <= alpha. No method is entitled to assert exchangeability, unmeasured-confounder absence, or true Gamma adequacy.

## Frozen data / design

Two independent non-overlapping cohorts, A starting seed 33,000,001 and B 44,000,001. Seven families (six supported positive models, one structural-zero negative control): exact_kink, local_kink, rare_binary, thin_positive, asymmetric_hidden, rare_reversal, structural_zero. Both n=900 and 1800, 500 independent datasets per family/n/cohort: **14,000 datasets / 280,000 method-Gamma attempts**, including 2,000 negative-control datasets. No reuse of G25J or G25K holdout seeds. The first four families and negative control reuse fixed generator mechanisms for comparability; asymmetric_hidden and rare_reversal use independently specified new W/U structural models, with explicit parameters in g25l_models.py. No tuning based on evaluation seeds.

## Preregistered acceptance screen

For each of 6 positive families × 2 sizes × 5 Gamma settings, pool both disjoint cohorts (1,000 attempted independent datasets/cell). A research candidate must have >=99% completion (refusals counted), observed full-set coverage >=93% among completed intervals, nominal .95 inside Wilson 95% Monte Carlo CI, mean width <=0.95 × G25I CP reference on the **same completed cases**, zero receipt/corruption mismatches, zero unauthorized causal admissions, and no single failed cell. The width and approximate calibration screens are **experimental candidate standards**, not preconditions for the underlying finite-sample CP union-bound coverage guarantee. A provably conservative but wide method may fail promotion.

Negative controls: structural zero must refuse all conditional intervals; limited observed support must never be relabeled as valid causal identification; Gamma adequacy and true potential-outcome values are simulator-only evaluation fields. Test independent LP (Charnes–Cooper) checks for every ratio optimization primitive and exact LP-based sensitivity endpoint cross-checks. Freeze source/seed configuration SHA-256 before held-out results; archive all failed executions or deviations.

**Production decision:** research acceptance is never automatic authorization to change production estimator. External scientific review and independent full-code replication still required, plus separate explicit user approval.