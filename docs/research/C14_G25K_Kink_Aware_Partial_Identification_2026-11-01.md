# Cognitum C14 G25K — Kink-aware partial-identification research

**Date:** 2026-11-01 (America/Phoenix)  
**Scope:** Cognitum-only isolated research. No change to Cognitum production algorithms or Lu. GitHub is the documentation/repository archive, not the test runtime.  
**Decision:** **G25K RESEARCH COMPLETE — G25 SCIENTIFIC ACCEPTANCE NOT MET; NO PRODUCTION PROMOTION.**

## Executive conclusion

G25J's smooth delta-method confidence set with a hard kink guard is highly selective near Γ=0.25. G25K preregistered a derivative-free *m-out-of-n multinomial subsampling* candidate using exact piecewise endpoint recomputation, and held the G25I simultaneous Clopper–Pearson projection as the separate finite-sample reference. The candidate completed **all 4,000 Γ=0.25 exact/local-kink datasets** rather than the G25J delta method's 168 combined cases, while issuing intervals only approximately **75–80% as wide as G25I** in those matched kink cases. But it did **not** deliver reliable nominal 95% simultaneous coverage. The worst two positive cells at Γ=.25 achieved only **92.9%** coverage, with Wilson 95% upper bounds below 95%. That fails the preregistered coverage and compatibility screen; the method is **not deployable**.

The protected G25I exact CP reference covered all **60,000/60,000 supported family/size/Γ attempts** in the simulation. This is conspicuously conservative, not evidence of precisely calibrated 95% intervals. Its guarantee is conditional on correct iid sampling, positive observed treatment arms, and an externally justified sensitivity parameter Γ. It does not verify those causal assumptions.

## Study design and provenance

G25K's preregistration and full source SHA-256 maps were frozen **before the full evaluation seeds**. Source includes unmodified byte-for-byte copies of G25I's `g25i_core.py` and G25J's `g25j_core.py` for reference calculations. The frozen seed ranges are 12,300,001 for Cohort A and 22,300,001 for Cohort B, plus disjoint, preregistered family/size offsets. Each cohort has seven independent SCM-derived observed-table families, n=900 and n=1,800, 500 datasets per family/n cell: **7,000/cohort, 14,000 total**.

Five frozen sensitivity assumptions Γ∈{0,.10,.25,.50,1} and three interval methods imply **210,000 primary method/Gamma attempts**, counting every refusal. The locally generated observed (W,T,Y) counts follow each family's analytically derived 8-category probability table. Simulator ATE, true selection contrast and full population identified set are available **only for evaluation**, never passed to the interval methods. The local-kink generator is a triangular-array design with its mean near the kink by 0.20/√n, not a fixed SCM held constant as n changes.

Primary target is simultaneous containment of **both endpoints of the population sensitivity-identified set**. This is distinct from a single partially identified causal parameter's confidence interval. A valid sampled interval cannot prove that Γ is appropriate, that exchangeability holds, or that hidden confounding is absent. Structural-zero support is a negative control and no conditional interval is issued there.

### Experimental method

For each observed sample n, use B=199 conditional multinomial draws of size m=floor(n^0.8). A subsample lacking an observed treatment/W arm is invalid; all 199 draw outcomes are retained. If fewer than 190 are valid, refuse. For each valid draw, recompute the exact piecewise population-set *formula* at the draw's empirical distribution, not a smoothed Jacobian. Form the one-sided max-error statistic

`T* = max(sqrt(m)*(L*_m - Lhat), sqrt(m)*(Uhat - U*_m))`,

then take the upper empirical 95th percentile and divide by sqrt(n), yielding `[Lhat - c/sqrt(n), Uhat + c/sqrt(n)]` clipped to [-1,1]. This is an exploratory approximation: **there is no finite-sample or uniformly local-kink-valid theorem for this exact configuration**. In particular, the selective validity threshold and m/n choice have not been externally validated.

## Main kink comparison at Γ=0.25

| Model | Original G25J delta completed | G25K subsampling completed | G25K set coverage, conditional | Exact CP set coverage | G25K / matched CP width |
|---|---:|---:|---:|---:|---:|
| exact_kink, n=900, Γ=0.25 | 69/1,000 | 1,000/1,000 | 93.80% | 100.00% | 0.748× |
| exact_kink, n=1800, Γ=0.25 | 16/1,000 | 1,000/1,000 | 93.40% | 100.00% | 0.799× |
| local_kink, n=900, Γ=0.25 | 69/1,000 | 1,000/1,000 | 93.40% | 100.00% | 0.748× |
| local_kink, n=1800, Γ=0.25 | 14/1,000 | 1,000/1,000 | 92.90% | 100.00% | 0.799× |
| rare_binary, n=900, Γ=0.25 | 20/1,000 | 1,000/1,000 | 92.90% | 100.00% | 0.738× |
| thin_positive, n=900, Γ=0.25 | 0/1,000 | 575/1,000 | 95.65% | 100.00% | 0.808× |
| thin_positive, n=1800, Γ=0.25 | 313/1,000 | 999/1,000 | 96.50% | 100.00% | 0.791× |

For the n=1,800 local-kink model, 929/1,000 intervals covered both endpoints: **92.9%** (Wilson 95% CI **91.14–94.33%**). For the n=900 rare-binary Γ=.25 cell the result was also **92.9%**, again excluding nominal 95% within Wilson uncertainty. At n=1,800 exact-kink Γ=.25, observed coverage was **93.4%** with Wilson upper bound **94.78%**. These numbers are not a multiple-comparison-corrected confirmation of systematic undercoverage, but the preregistered per-cell screen is violated and no production inference is justified.

The G25K subsampling procedure did not impose a kink-distance refusal. That gives 100% completion in the moderate-support kink cells but is **not equivalent to 95% coverage**. The alternative G25J delta method retained its original proximity and sparse-cell refusals and undercovered sharply among the tiny selected exact-kink samples (e.g., 7/14 in local-kink n=1,800 Γ=.25); those selection-conditional rates must not be promoted to population estimates.

## Across all positive-support acceptance cells

There are six positive-support families × two sample sizes × five Γ settings = **60 acceptance cells**, 1,000 attempted datasets/cell pooled across cohorts. The preregistered screen requires ≥99% completion, ≥93% set coverage among completed datasets, 95% compatible with its Wilson interval, and matched mean width ≤95% of exact CP. G25K passed **41/60** screens, failed **19/60**; G25J delta passed **28/60** under the same research screening rule. This is exploratory comparison, not a head-to-head multiple-testing-adjusted superiority claim. Cohort-specific numbers, Wilson intervals and refusal categories are preserved for every cell in `results/G25K_AB_aggregate.json`.

Across the 12,000 positive-support datasets, each Gamma was attempted once by each method. G25I CP produced 60,000 conditional reference bands, G25J delta computed **39,684**, and G25K subsampling computed **57,870**. All 2,000 structural-zero datasets appropriately received no conditional interval under any method. The positive-support thin-positive n=900 family had G25K completion of just **575/1,000** cases: even a computationally stable kink-aware scheme can be unreliable under thin positivity. Total invalid subsample draws were **11,112** out of **2,388,000** attempted across the 12,000 positive-support datasets (199 per case); they were never dropped without recording them or the affected dataset refusal.

The CP bands' 100% observed coverage is an indication of conservatism in these samples, not a guarantee of 100% future coverage; the G25I mathematical guarantee comes from the Bonferroni union bound applied to seven Clopper–Pearson binomial intervals. Γ is a bounded risk-difference selection contrast, *not* a Rosenbaum odds-ratio sensitivity parameter.

## Verification and independent audits

- **14,000/14,000 complete numerical exact replays** of each frozen primary receipt, both cohorts, including all five Γ settings and all three methods (210,000 method/Gamma outcomes); the original initial stratified audit had also checked 168 receipts/cohort.
- Every receipt independently regenerated from its seed and frozen SCM probability table; count arrays, population table hashes, simulator-only effect values, coverage flags, method statuses, invalid-subsample accounting and forbidden causal-admission labels validated.
- **2,160 independent SciPy HiGHS linear-programming comparisons** of the population/empirical sensitivity-bound endpoints, numerical maximum absolute discrepancy ≤1.12e-16. **720 independent G25I reference equivalence checks** matched the original CP projection.
- **23/23 G25K local tests** passed; **43/43 unchanged G25J unit/adversarial regression tests** passed with the proper baseline `PYTHONPATH`; **10/10 deliberately tampered receipt tests rejected**. Tests cover deterministic resampling, signed one-sided max-error quantile, exact/local-kink behavior, no-support refusal, hash integrity and no causal-admission output.
- Full rerun of Cohort B's 7,000 numerical replays was executed separately after a combined full-replay process exceeded its local execution timeout. A had already completed 7,000 exact replays before that timeout. **No evaluation, source, seed or threshold changed**; the first interruption is an audit-orchestration event, not a new scientific cohort.
- Both evaluation cohort receipt files, frozen protocol hashes and every primary receipt SHA-256, independent audit and aggregate hashes are retained. No external R/Firth/partial-identification package was executed. The independent LP checks validate mathematical endpoint construction, not a general uniform inference theorem.

## Scientific acceptance decision

**FAIL / NO PRODUCTION PROMOTION.** Kink-proximity refusals can be avoided by derivative-free computation, but the chosen m-out-of-n procedure is still too liberal in several key cells. True identified-set coverage and refusal rates must both be satisfied; no single pooled performance number can rescue a failed Γ or model family. The present results are not proof that a different m-selection rule, bootstrap statistic or interval construction would be uniformly calibrated. Any subsequent method must be preregistered and tested on *new* seeds rather than tuned to these receipts.

## Next engineering proposal: G25L

Evaluate mathematically justified projection of a **simultaneous observed-law confidence region** through the non-smooth identified-set map, potentially using a joint multinomial score/LR region or a rigorously valid finite-sample region. Unlike naïve kink bootstrap, an outer projection inherits simultaneous coverage when the underlying region covers the true observed law; optimization/globality and small-cell behavior must be verified. Compare set coverage and width against the conservative G25I exact CP baseline. Keep sensitivity assumptions and causal certification separate. Require independently audited new causal structures, ≥1,000 datasets per positive cell, external statistical review, and separate user authorization before any production algorithm change.

## Reproduction and source notes

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q tests/test_g25k.py`, then (from package root) `python tools/run_g25k.py A`/`B` using the immutable frozen configuration and `python tools/audit_g25k.py A`/`B`. The archived two complete audit JSONs reflect the stronger `audit(cohort, replay_per_cell=500)` invocation; re-running the CLI defaults to the initial stratified 12-per-cell audit and does not overwrite the source cohorts. Use `python tools/g25k_independent_numerical.py`, `python tools/g25k_postholdout_adversarial.py`, `python tools/aggregate_g25k.py` to regenerate the independent checks and summaries. The frozen source map is embedded in both `G25K_Frozen_*.json` files. Post-holdout numerical, report and adversarial scripts are explicitly separate and were never used to tune any evaluated estimator.

**Reference methodology:** Chernozhukov, Hong & Tamer (2007), *Estimation and Confidence Regions for Parameter Sets in Econometric Models*; Stoye (2009), *More on Confidence Intervals for Partially Identified Parameters*. These support inference distinctions but do **not** validate G25K's exact subsampling configuration.