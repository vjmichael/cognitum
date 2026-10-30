# C14 P4E G9 — Calibration of bootstrap, AIPW and Wald intervals

**Status:** Offline synthetic-method comparison, not a production scientific or Lu host certification.  
**Baseline:** C14 P4E G8 immutable source archive (verified before copy).  
**Date:** 2026-10-28  
**Design:** 5 scenarios × 2 sample sizes (N=300, N=900) × 200 paired seeds (1001–1200) = **2,000 datasets**. 399 paired-observation bootstrap resamples per dataset (where valid). Known population ATEs supplied by the generator, not inferred from observations. Nominal interval confidence 95%.

## 1. What was compared

1. G8 stratum-standardized **population-mix Wald** (original formula reused unchanged).
2. Whole-observation, nonparametric bootstrap **percentile**, **basic**, **BCa** (bias corrected / accelerated), and **bootstrap-normal** intervals. Each replicate preserves the Z/T/Y triple. BCa jackknife acceleration uses eight equivalent binary contingency-cell classes.
3. Two-fold **cross-fitted augmented inverse probability weighting (AIPW)** with stratified nuisance predictions estimated on the opposite fold and an empirical influence-function standard error, capped to the binary-effect support. Propensity/outcome predictions are Laplace-smoothed. Robustness applies only under identification assumptions and at least one suitable nuisance model; it is not protection from hidden confounding.

The SciPy `bootstrap` BCa procedure was executed independently on a representative synthetic fixture. Because SciPy and the contingency-count sampler consume different random-number sequences, the numerical validation compares interval scale and method behavior, not equality of resamples. Separate brute-force leave-one-out jackknife arithmetic matches the BCa acceleration formula exactly on a test fixture.

## 2. Calibration results, paired with G8's seed grid

### Heterogeneous effect, 300 observations — G8 undercoverage focus

| Method | Coverage | 95% Wilson MC interval | Mean width | Completed |
|---|---:|---|---:|---:|
| G8 population-mix Wald | 91.5% | [86.8%, 94.6%] | 0.2312 | 200/200 |
| Paired-rows percentile bootstrap | 91.3% | [86.5%, 94.5%] | 0.2301 | 196/200 |
| Paired-rows basic bootstrap | 90.3% | [85.4%, 93.7%] | 0.2301 | 196/200 |
| Paired-rows BCa bootstrap | 92.9% | [88.4%, 95.7%] | 0.2308 | 196/200 |
| Paired-rows bootstrap-normal | 91.3% | [86.5%, 94.5%] | 0.2326 | 196/200 |
| Cross-fitted AIPW influence-function Wald | 90.9% | [86.1%, 94.2%] | 0.2486 | 198/200 |

### Heterogeneous effect, 900 observations

| Method | Coverage | 95% Wilson MC interval | Mean width | Completed |
|---|---:|---|---:|---:|
| G8 population-mix Wald | 94.5% | [90.4%, 96.9%] | 0.1355 | 200/200 |
| Paired-rows percentile bootstrap | 94.0% | [89.8%, 96.5%] | 0.1340 | 200/200 |
| Paired-rows basic bootstrap | 96.5% | [93.0%, 98.3%] | 0.1340 | 200/200 |
| Paired-rows BCa bootstrap | 94.5% | [90.4%, 96.9%] | 0.1343 | 200/200 |
| Paired-rows bootstrap-normal | 95.0% | [91.0%, 97.3%] | 0.1353 | 200/200 |
| Cross-fitted AIPW influence-function Wald | 93.5% | [89.2%, 96.2%] | 0.1385 | 200/200 |

### Homogeneous effect, 300 observations

| Method | Coverage | 95% Wilson MC interval | Mean width | Completed |
|---|---:|---|---:|---:|
| G8 population-mix Wald | 93.5% | [89.2%, 96.2%] | 0.2424 | 200/200 |
| Paired-rows percentile bootstrap | 93.5% | [89.2%, 96.2%] | 0.2417 | 200/200 |
| Paired-rows basic bootstrap | 92.5% | [88.0%, 95.4%] | 0.2417 | 200/200 |
| Paired-rows BCa bootstrap | 93.5% | [89.2%, 96.2%] | 0.2422 | 200/200 |
| Paired-rows bootstrap-normal | 93.5% | [89.2%, 96.2%] | 0.2446 | 200/200 |
| Cross-fitted AIPW influence-function Wald | 94.0% | [89.8%, 96.5%] | 0.2587 | 200/200 |

### True null effect, 300 observations

| Method | Coverage | 95% Wilson MC interval | Mean width | Completed |
|---|---:|---|---:|---:|
| G8 population-mix Wald | 94.0% | [89.8%, 96.5%] | 0.2060 | 200/200 |
| Paired-rows percentile bootstrap | 93.5% | [89.2%, 96.2%] | 0.2057 | 200/200 |
| Paired-rows basic bootstrap | 93.0% | [88.6%, 95.8%] | 0.2057 | 200/200 |
| Paired-rows BCa bootstrap | 93.0% | [88.6%, 95.8%] | 0.2057 | 200/200 |
| Paired-rows bootstrap-normal | 94.0% | [89.8%, 96.5%] | 0.2085 | 200/200 |
| Cross-fitted AIPW influence-function Wald | 93.5% | [89.2%, 96.2%] | 0.2159 | 200/200 |

Coverage is **empirical** across eligible, completed simulations; it is not guaranteed population coverage. Wilson 95% intervals quantify Monte Carlo uncertainty around the measured coverage fraction, not uncertainty about the causal effect. For bootstrap, completed trials exclude failures (shown explicitly), so conditioning on completion may distort coverage comparisons. **No claim of comparative superiority is justified by 200 seeds.**

### Paired BCa versus Wald discordance

| Scenario | N | Wald-only covers | BCa-only covers | Paired complete | Exact discordance p |
|---|---:|---:|---:|---:|---:|
| observed_heterogeneous | 300 | 0 | 3 | 196 | 0.250 |
| observed_heterogeneous | 900 | 1 | 1 | 200 | 1.000 |
| observed_homogeneous | 300 | 2 | 2 | 200 | 1.000 |
| observed_homogeneous | 900 | 2 | 3 | 200 | 1.000 |

Paired results use only simulations where both methods computed a valid interval. The exact two-sided binomial discordance check (McNemar conditional form) does not support asserting BCa is better than Wald in the undercovered small-sample scenario (p=0.25). This is an exploratory multiple-method study; no multiple-comparison-adjusted discovery claims are made.

## 3. Identification failure and method-specific rejection

- **Hidden confounding:** The causal data generator includes an unmeasured common cause. All estimation methods may return *descriptive statistical intervals*, but their causal coverage is **not eligible or reported**. Mean point bias for G8 Wald at N=300 is +0.1663; cross-fitted AIPW mean bias is +0.1674. More elaborate variance estimation does not repair omitted confounding.
- **No overlap:** All six methods rejected point estimates/intervals in all 200 N=300 and 200 N=900 no-overlap cases. G8's conservative partial-identification envelope is preserved as a separate object; it is not a confidence interval for a point-identified effect.
- **Bootstrap failure:** For the N=300 heterogeneous group, the bootstrap returned intervals in **196/200** trials. Four trials were rejected for insufficient overlap during replicates or BCa jackknife. Invalid replicates are not silently discarded and the nominal confidence level is not asserted on a reduced subset.
- **AIPW failure:** For the same group, cross-fitted AIPW returned **198/200**; two cases failed training-fold overlap or extreme-propensity preflight.

## 4. Doubly robust nuisance-model stress (200 seeds)

The `stratified` nuisance option uses the observed Z covariate; `pooled` ignores Z and is deliberately misspecified in these synthetic confounded/heterogeneous settings. This is a finite-sample demonstration of the *potential* robustness, not proof of general consistency.

### observed_heterogeneous, N = 300
| Propensity nuisance | Outcome nuisance | Mean estimate minus known oracle | Completed |
|---|---|---:|---:|
| stratified | stratified | -0.0038 | 198/200 |
| stratified | pooled | -0.0149 | 198/200 |
| pooled | stratified | +0.0051 | 198/200 |
| pooled | pooled | +0.1981 | 198/200 |

### observed_heterogeneous, N = 900
| Propensity nuisance | Outcome nuisance | Mean estimate minus known oracle | Completed |
|---|---|---:|---:|
| stratified | stratified | -0.0021 | 200/200 |
| stratified | pooled | -0.0052 | 200/200 |
| pooled | stratified | +0.0009 | 200/200 |
| pooled | pooled | +0.1988 | 200/200 |

### hidden_confounder, N = 300
| Propensity nuisance | Outcome nuisance | Mean estimate minus known oracle | Completed |
|---|---|---:|---:|
| stratified | stratified | +0.1674 | 200/200 |
| stratified | pooled | +0.1662 | 200/200 |
| pooled | stratified | +0.1671 | 200/200 |
| pooled | pooled | +0.1851 | 200/200 |

### hidden_confounder, N = 900
| Propensity nuisance | Outcome nuisance | Mean estimate minus known oracle | Completed |
|---|---|---:|---:|
| stratified | stratified | +0.1617 | 200/200 |
| stratified | pooled | +0.1614 | 200/200 |
| pooled | stratified | +0.1616 | 200/200 |
| pooled | pooled | +0.1789 | 200/200 |


**Interpretation:** On the clean heterogeneous N=900 scenario, correct propensity + pooled outcome averaged bias −0.0052, pooled propensity + correct outcome +0.0009, and pooled + pooled +0.1988. But with a **hidden confounder**, even both stratified observed-variable nuisances averaged bias +0.1617 at N=900. Double robustness does not compensate for unmeasured variables.

## 5. Typed interfaces, integrity and security

- `proto/cognitum/causal/v1/interval_comparison.proto` and compiler-derived `cognitum/proto/causal_interval_comparison_pb2.py` express bounded, offline-only study requests, per-method availability and deterministic replay receipts.
- `cognitum/causal_interval_comparison.py` enforces typed requests, resource budgets, request digests, and exact deterministic replay. Research results **never** claim host authentication or verified causality. Known hidden confounding or no overlap prevents methods from publishing usable *causal point intervals*.
- Audit evidence includes exact generator seeds, sample sizes, method statuses and intervals. Results are reproducible but **not signed/authenticated third-party attestations**. Release-stage trusted host admission is still pending.

## 6. Scope and engineering gates

**Passed here:** bounded numerical method tests; independent SciPy BCa comparison; independent jackknife verification; seeded replay of 2,000 scenarios; synthetic nuisance misspecification study; Protobuf compiler/binding parity; selected C13/C14 regressions.

**Not demonstrated:** confidence-interval coverage outside these synthetic data-generating processes; stabilized targeted estimators/TMLE; cluster/time-series bootstrap; strong-overlap violations beyond tested fixtures; authenticated tagged DoWhy provenance; native Windows process confinement; Lu host authorization; real LLM WITH/WITHOUT Cognitum benchmark. Unlike an experimental calibration report, none of these results authorizes model-facing execution.

## 7. Reproduce (Python with NumPy/SciPy installed)

```bash
PYTHONPATH=. python tools/run_c14_p4e_g9_interval_comparison.py --report docs/components/causal/P4E-G9-interval-method-calibration-evidence.json --seeds 200 --sizes 300 900 --resamples 399
PYTHONPATH=. python tools/run_c14_p4e_g9_nuisance_sensitivity.py --output docs/components/causal/P4E-G9-nuisance-sensitivity-evidence.json --seeds 200
PYTHONPATH=.:tests python -m unittest tests.test_c14_p4e_g9_interval_comparison tests.test_c14_p4e_g9_protobuf -v
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
PYTHONPATH=. python tools/run_c14_p4e_g9_smoke.py
```

**Scientific references:** SciPy bootstrap API https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html ; doubly robust assumptions and inferential limitations https://pmc.ncbi.nlm.nih.gov/articles/PMC3070495/ ; inference estimators and bootstrap refitting discussion https://onlinelibrary.wiley.com/doi/10.1002/sim.9969 .
