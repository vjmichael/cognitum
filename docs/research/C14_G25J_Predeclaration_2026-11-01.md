# Cognitum C14 G25J — preregistration (before any held-out run)

**Date:** 2026-11-01 (America/Phoenix). **Isolation:** research-only; no Cognitum production or Lu source changes.

## Question
Can an **asymptotic simultaneous confidence outer set for the population sensitivity-identified set** be substantially shorter than the G25I exact Bonferroni/Clopper–Pearson outer interval without materially under-covering, in predeclared smooth, well-populated cells? This is **not** a generally uniform finite-sample proof; conservative G25I remains the validated baseline for its assumptions.

## Fixed study

- Frozen legacy source: G25I `tools/g25i_core.py` copied unchanged to `baseline/g25i_core.py`.
- Six G25I data-generating families: measured; randomized-hidden-prognostic; latent-confounder; misclassified-confounder; weak-positive-overlap; structural-zero-overlap. Same generators as G25I, **fresh unseen random seeds** only; do not claim novel SCM families.
- n=900 and n=1,800, each family/size has 1,000 datasets **per cohort**; A and B each have 12,000 datasets, totaling 24,000 (unmodified frozen seed recipe); five Gamma assumptions: 0,.1,.25,.5,1.
- Two methods per Gamma/dataset (G25I simultaneous exact CP outer set and G25J correlated-normal two-endpoint delta outer set), **240,000 method attempts**. Structural and weak-arm failures retained in denominator.
- Parametric vector is the observed 8-category multinomial joint distribution of binary (W,T,Y). Population identified endpoints are calculated analytically from the generator's probability table; simulator-specific true ATE and minimum necessary Gamma are scoring-only.
- The proposed delta outer set is based on the multinomial endpoint gradient, plug-in covariance, and the bivariate-normal quantile for simultaneous containment of both **identified-set endpoints** (not a confidence interval proven uniformly valid for every possible latent confounding model).
- **Refuse delta method** when an observed treatment/stratum arm is empty, any arm has fewer than 25 observations, any joint category has fewer than 10 observations, any piecewise sensitivity-bound branch is within .02 risk units of a kink, or covariance is degenerate. Keep exact G25I reference wherever its conditional calculation is supported.
- Sensitivity-parameter elicitation benchmark: observed `max_t |E(Y|T=t,W=1)-E(Y|T=t,W=0)|`. This is **only descriptive strength of the observed covariate**, **not** an upper bound, not causal certification, and never auto-selects Gamma. Also calculate plugin point-identified-set sign-tipping Gamma for reference; it is not a statistical bound or true Gamma estimate.

## Predeclared analysis

- Primary scientific estimand for interval **set coverage**: `L_sample_lower <= L_population` and `U_sample_upper >= U_population`, where L/U are population Gamma-indexed sensitivity bounds. Evaluate regardless of whether Gamma suffices to cover the simulator's true causal effect; separately score effect inclusion **only when Gamma is simulator-adequate**.
- Distinguish `set_coverage_conditional_on_delta_acceptance`, unconditional *completion*, and `ATE_inclusion_given_true_Gamma`. Do **not** pool selected cases with all attempts or describe interval covering the true ATE when Gamma is false as valid 95% inference.
- Positive research screen for each eligible strong-support family/size/Gamma cell: at least 95% completion, observed set coverage >=93%, nominal 95% inside Wilson 95% uncertainty interval, and mean matched delta width <=90% of G25I reference. Report failures without tuning the method or thresholds. Weak/structural controls must be refused rather than silently scored.
- Zero forged receipts and zero automatic causal certifications; all attempted datasets auditable. Numerical cross-checks: analytical gradients versus centered finite differences, bound endpoints versus independent SciPy linear programming, bivariate-normal CDF via SciPy, G25I exact CP equivalence, plus no-support refusal tests.
- Empirical performance cannot prove asymptotic uniformity near kinks or positivity boundaries, and is NOT authorization to change production inference; independent external scientific package comparison, extension beyond binary W/Y and independent holdout across new causal structures are still required.

## Methodological distinctions

- This is an **outer-set** coverage procedure, not the shorter Imbens–Manski pointwise-parameter interval. The distinction is intentional and prevents claiming pointwise uniformity without its special assumptions. See Imbens–Manski 2004 and Stoye 2009.
- Asymptotic bivariate normal calibration is conditional on smooth endpoints, interior multinomial probabilities and a fixed Gamma; the fitted threshold exclusions are pragmatic diagnostics, NOT a mathematically proved uniform validity condition.
- Hidden confounding remains **unobservable** and must not be inferred absent from successful numerical fitting. Gamma's scope is a bounded risk-difference contrast, NOT a Rosenbaum odds-ratio Gamma.