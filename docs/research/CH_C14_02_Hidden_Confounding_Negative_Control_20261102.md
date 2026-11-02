# CH-C14-02 — Hidden-confounder negative control on existing P18 diagnostics

**Date:** November 2, 2026. **Scope:** Linux research-only, no Lu or Windows changes, no causal estimator modification or promotion.

## Objective
Stress the difference between *observational interval precision* and *correct causal interpretation* with a simulator whose true causal treatment effect is exactly zero. Unlike a new causal method, this is a narrow negative-control experiment reusing the original Cognitum P18 `causal_bootstrap_p18.bootstrap_strata` and `causal_variance_diagnostics_p17` implementation.

## Study and frozen output

- 50 iid synthetic datasets each under randomized treatment and a hidden-common-cause exposure regime, n=1,800 per dataset, 199 bootstrap resamples, independent seeded runs.
- Observed W and hidden U are Bernoulli(0.5). Y depends on U alone: P(Y=1|U=0)=0.10, P(Y=1|U=1)=0.80. T does **not** enter the data-generating equation for Y, so the simulator's ATE=0.
- Randomized T: P(T=1)=0.5. Hidden common cause: P(T=1|U=0)=0.15; P(T=1|U=1)=0.85. W is independently generated and cannot adjust for U.
- Standard output from existing P18 observed-strata bootstrap, not a verified causal interval; treatment assignment and labels are not changed by any inference code.

| Cohort | Attempted / reports issued | 95% percentile intervals excluding 0 | Median interval midpoint |
|---|---:|---:|---:|
| Randomized | 50/50 | 6/50 | +0.001035 |
| Hidden common cause | 50/50 | **50/50** | **+0.489872** |

All 100 research reports retained `causal_identification_proven=False` and `production_interval_authorized=False`. Six randomized noncoverages are included, not filtered. This is **not** a broad nominal coverage validation: 50 cases per regime is too little and the bootstrap estimator presumes an unverified causal assumption.

## Local execution / artifact

- Existing P17/P18 unit tests rerun locally: **16 passed, 0 failed**.
- New synthetic-control tests: **5 passed, 0 failed** (reproducibility; row permutation; misidentified hidden-cause effect; randomized near-zero; invalid input refusal).
- Complete package extracted into a separate directory; SHA-256 verified for all **8** archive manifest payload entries; **5/5** new tests passed again, using **unchanged copies of two P18 research modules**, not production sources.
- Local artifact: `Cognitum_CH_C14_02_Hidden_Confounding_Negative_Control_2026-11-02.zip` SHA256 `fb7dc5ed4c6176a3e5228ae678d26b6b1896c908370d179f6fba6f16d62ba8b2`. Contains generator, case-level JSON, tests, two original P18 modules, report and checksum manifest. Tested code is in this archive rather than merged into the main Cognitum source tree.

## Original G25 nonproduction contract source review

The GitHub source of `research/c14_g25_nonprod/tools/g25_release_guard.py` and `integration/c14_research_host.py` was inspected. Its guarded report requires explicit Gamma, documented assumptions, minimum-arm support, and non-certifying outputs. The JSONL host accepts precisely one of counts or observations, rejects malformed input and duplicate request identifiers, is disabled by default, and refuses oversized requests. Both host and inner result receipts use **non-authenticating SHA-256** and depend on a trusted invoking supervisor.

**No full G25N scientific cohort, G25 guard/supervisor black-box suite, or native production integration was rerun in CH-C14-02.** Existing repository evidence documents 980/980 prior nonproduction E2E cases and 68/68 standalone supervisor tests; these are not new results.

## Decision / next work

**Engineering PASS for narrow P18 negative-control reproduction, scientific NO-GO unchanged.** Do not interpret a narrow observed-data interval as proving the absence of hidden confounding. G25N's 12/12 scientific width/calibration failures, global inversion, external Firth equivalence and independent scientific review remain OPEN.

Next: restore and test the exact G25I/G25 host/guard/supervisor pinned research source and negative controls; identify genuine contract defects; then preregister wide nonlinear/continuous/rare-outcome causal SCM holdouts and compare calibrated standard inference methods. Do not silently weaken refusal gates or promote an estimator.
