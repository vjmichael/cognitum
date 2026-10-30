# Cognitum C14 P4E G8 — Interval coverage and partial identification

**Date:** 2026-10-28  
**Status:** Bounded, offline research reference. **Not** Windows/Lu production validation or a demonstration of real-world causal identification.  
**Baseline:** immutable C14 P4E G7 checkpoint (SHA-256 `7b70e16bb1f6050415b8350bfa3ec1fcbb30924c79acf9720f469df7f568e8f2`).

## Question and predeclared controls

Can Cognitum distinguish statistical sampling uncertainty in an identified effect from identification uncertainty when key assumptions are unverified or violated? Use the exact G7 Bernoulli synthetic generator, 200 deterministic seeds (1001–1200), sample sizes 300 and 900, and five predeclared scenarios: clean homogeneous, clean heterogeneous, true null, hidden confounder, and deterministic no-overlap. Report *only* the first three in point-estimate interval coverage. Never call hidden-confounder numerical intervals calibrated, and reject point-estimate intervals in the no-overlap design.

## Reference interval — two variants

For each observed covariate stratum z, compute the treatment-minus-control outcome risk difference d_z and weight by observed P(Z=z) to produce a stratified ATE estimator. For iid binary outcomes, the elementary plug-in conditional-on-mix variance is the sum of w_z² × [p_1z(1−p_1z)/n_1z + p_0z(1−p_0z)/n_0z]. A second estimator includes the estimated variance from the *random covariate mix*, namely ∑ w_z(d_z−d)²/n. Both use an approximate 95% normal Wald interval and truncate the limits to the binary ATE's support [−1,1]. These are not guaranteed accurate at small samples or in the presence of confounding. Numerical estimates use Cognitum's previously independently cross-checked exact rational standardization.

### Results — 200 seeds per cell, nominal 95% coverage

| Sample N | Scenario | Conditional-mix Wald coverage | Population-mix adjusted Wald coverage | Avg. conditional interval width |
|---:|---|---:|---:|---:|
| 300 | homogeneous | 93.5% | 93.5% | 0.2419 |
| 300 | heterogeneous | 91.0% | 91.5% | 0.2270 |
| 300 | true null | 94.0% | 94.0% | 0.2057 |
| 900 | homogeneous | 94.5% | 94.5% | 0.1416 |
| 900 | heterogeneous | 94.5% | 94.5% | 0.1335 |
| 900 | true null | 96.0% | 96.0% | 0.1200 |

This is *empirical synthetic coverage*, not calibration of a real-world estimator. Observed 91–92% coverage at N=300 is a warning against treating 95% labels as guarantees. Point-coverages across independent seeds are noisy, and no method is promoted based on this single suite.

## Partial identification: binary potential outcomes, treatment and outcomes

With consistency and bounded binary Y(0), Y(1), but **without** unconfoundedness, the population ATE's identification set satisfies:

- Lower: P(Y=1,T=1) − P(Y=1,T=0) − P(T=1)
- Upper: P(Y=1,T=1) − P(Y=1,T=0) + P(T=0)

The *empirical plug-in* bound width is exactly 1, revealing considerable identification uncertainty. It is **not itself a frequentist confidence interval for the true population ATE**. An independently labeled conservative **sampling envelope** uses a one-sided Hoeffding union bound (iid sampling): epsilon = sqrt(log(2/alpha)/(2n)), widening the lower endpoint down and the upper endpoint up, clipped to [−1,1]. The envelope was observed to contain the simulator's population effect in all 2,000 scenarios; 100% empirical containment in a deliberately broad envelope is **not** universal evidence of perfect frequentist calibration.

These worst-case bounds work even when positivity fails or a latent common cause is declared; they avoid fabricating a unique estimated effect. They do not exploit valid instruments, monotonicity, or other narrowing assumptions. Any such refinement requires a new versioned capability and independent tests.

## Genuine external intervals: a separate, small smoke

Using the exact uploaded/locally built scientific sources, DoWhy `backdoor.linear_regression` produced overall ATE 95% confidence intervals and EconML 0.17.0 `LinearDML` produced CATE intervals for z=0 and z=1. Runs: 4 scenarios × 3 seeds × N in {300,900} = **24 genuine-library datasets**. Each clean scenario comprises six cases. Results in `P4E-G8-genuine-crosslibrary-intervals.json`:

| Clean scenario | DoWhy ATE covered | EconML CATE z=0 covered | EconML CATE z=1 covered |
|---|---:|---:|---:|
| homogeneous | 6/6 | 6/6 | 5/6 |
| heterogeneous | 5/6 | 6/6 | 5/6 |
| null | 6/6 | 6/6 | 5/6 |

**Do not rank methods from these tiny counts.** These estimates have different estimands (ATE vs CATE), nuisance fits, inferential assumptions, and finite-sample behavior. Hidden-confounder outputs are deliberately *not* counted as valid coverage observations. The DoWhy `main` source lacks authenticated v0.14 tag provenance. No worker authorization/Windows security was tested by this script.

## Typed contract and verifier limits

The new `proto/cognitum/causal/v1/uncertainty.proto` defines a bounded binary request, separate partial identification and point intervals, and a request-bound replay receipt. No unrestricted data/paths or external processes. `cognitum/causal_uncertainty.py` denies point intervals when a hidden confounder is declared or a minimum arm count fails, while still providing broad bounds. Replays verify deterministic calculations against a request digest, not causal truth, external signature provenance or Lu authorization. The G8 study's report replays every seeded fixture and recomputes each result; the small external-library evidence verifier checks structure and oracle containment arithmetic, **not independent library execution**. A malicious actor with the ability to modify the report and its manifest is outside this assurance model.

## Gates remaining

- Correctness and coverage against additional methods (bootstrap percentile/BCa, influence-function or doubly robust intervals) and more generator families.
- Independent review of population standardization targets and interval assumptions.
- Authenticated v0.14 DoWhy release and version-locked transitive dependencies.
- Windows x86-64 Job Object/AppContainer confinement and genuine authenticated Lu host integration.
- Real-model comparative benchmarks with quantization and KV-cache controls (deferred).

## Reproduction

From extracted checkpoint root:

```bash
PYTHONPATH=. python -m unittest tests.test_c14_p4e_g8_uncertainty -v
PYTHONPATH=. python tools/run_c14_p4e_g8_uncertainty.py --report docs/components/causal/P4E-G8-calibration-evidence.json --seeds 200 --sizes 300 900
PYTHONPATH=. python tools/run_c14_p4e_g8_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

The **optional** genuine DoWhy/EconML script needs the separately provisioned source/compiled environment and a `--source-root` pointing to the user-provided DoWhy source. Reproduction on Windows is not asserted. Third-party sources and compiled binaries are intentionally not in this Cognitum archive.

Sources consulted: [statsmodels CI documentation](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html), [Manski bounds explanation](https://amertens.github.io/causal-learning-handbook/03-05b-sensitivity-analysis.html), [IV partial-identification review](https://pubmed.ncbi.nlm.nih.gov/31537952/).
