# G25H preregistration and source freeze — 2026-11-01

Both cohort protocols were frozen before first evaluation. A/B seeds are disjoint from discovery seeds and from G25G. Eight primary cells per cohort? There are **four** family × sample-size cells per cohort, each with 1,000 new datasets and four paired nuisance specifications. Distinct cohorts A/B each have 4,000 fresh datasets; there are 8,000 datasets total, 32,000 fitted specification attempts, 64,000 associated score/sandwich interval attempts, and 8,000 nondeployable oracle diagnostics before refusals. Any change after freeze must be explicitly recorded; none authorized for silent retuning.

Methods: cross-fit AIPW with score-only or finite-dimensional stacked estimating-equation variance; exact same point estimate. Four working-model specifications: full/full, linear propensity/full outcome, full propensity/linear outcome, and linear/linear. Polynomial family is exactly modeled by full working basis; oscillatory family contains out-of-basis nonlinearities, so even full models are working approximations. Negative cases are **not positive coverage fixtures** and are never allowed to issue causal CIs. Simulation truth tags and true propensities are for audits only and unavailable as deployment-side admission signals.

Acceptance *research screen* per cohort cell: at least 990 completed out of 1,000, observed coverage ≥93%, Wilson 95% interval contains 95%, |signed bias| ≤.015, reported SE / empirical estimator SD in [.9,1.1], and zero negative causal admissions. Screens do not confer production authority. The deliberately doubly-misspecified variants may fail; this is an explicit test of limitations, not an acceptance shortcut. Scientific G25 production promotion remains prohibited without independent review and approval.

External R `logistf`/`brglm2` equivalence is not claimed. A separate finite-difference Jacobian derivation tests internal mathematics; it is not an independent external statistical implementation.

Frozen files:
- `tools/g25h_core.py` SHA-256 `958c7217d3d07e38474a7a877a79bc3bc477b2317abfb37a3edf714916bedbd7`
- `tools/g25h_independent_if.py` SHA-256 `d53350f08a4f00ed4210afafa26c74af4038589c0b99ac1192ac2f627db71b5d`
- `tools/run_g25h.py` SHA-256 `4904092e78072a6d1ee80379a664b0f91fda5811d58986dd0bd222bc1eedb895`
- `tools/audit_g25h.py` SHA-256 `806a3bbc2a89094153b4bdc5f67897a859976b42a90f72a1fd9ef9c76940ce4c`
- `G25H_Frozen_A.json` SHA-256 `65deb3ddd067d7915401d8f80b7c16908678b3712c9f963a0da0352eecf7b72e`
- `G25H_Frozen_B.json` SHA-256 `518766c6584cca67c027d2885abf657e911563077c105f59da319eee113acf2c`