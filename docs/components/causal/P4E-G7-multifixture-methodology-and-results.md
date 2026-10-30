# Cognitum C14 P4E G7 — Multi-fixture cross-library causal validation

**Date:** 2026-10-28. **Status:** offline scientific validation of **unattested uploaded DoWhy `main` source**, real EconML 0.17.0 source runtime, and two established mathematical references. **Not a production security or DoWhy v0.14 release gate.**

## Research question and boundaries

Do independent effect estimators return plausible estimates on synthetic observational data with known intervention effects, and do their outputs expose methodological failures rather than silently certifying causation? G7 extends G6 from one 80-observation fixture to **50 seeded fixtures**: 5 scenarios × 5 seeds `(101,202,303,404,505)` × sample sizes **300 and 900**. Seeds are reused across sample-size conditions, so these are 50 datasets but **not 50 independent random seeds**. All methods within a fixture see identical `(Z,T,Y)` data, while the simulator's latent `U` stays hidden. Dataset digests and simulator oracle values are in the two JSON evidence files; no raw row data is persisted.

The *known* oracle is derived from **the simulator's interventional equations**, not from a fitted observational graph. Population average treatment effect (ATE) uses the Bernoulli(0.5) distribution of `Z`, rather than treating each sample's observed `Z` frequencies as a population oracle. Outcomes and treatment are Bernoulli; the effect is a **risk difference**, not an odds ratio.

## Five predeclared scenarios

| Fixture | Ground-truth ATE | Identifying assumptions / expected stress |
|---|---:|---|
| Observed, homogeneous | 0.24 | Observed `Z` suffices to block backdoor paths |
| Observed, heterogeneous | 0.295 | CATE(Z=0)=0.12, CATE(Z=1)=0.47; regression without interaction can misrepresent heterogeneity |
| Hidden common cause | 0.20 | Latent `U` affects both treatment and outcome; **observed-Z adjustment does not identify the ATE** |
| Null treatment effect | 0 | Negative control with no causal treatment effect in the generator |
| Deterministic treatment assignment | 0.18 | `T=Z` causes positivity failure, so stratified adjustment and downstream estimator runs are blocked |

The hidden-common-cause case is evaluated in two distinct modes: (a) **misspecified graph omitting `U`**, where the algorithms can agree while being biased, and (b) **explicitly declared latent `U`**, where the development harness blocks reporting an identified ATE. This is not the assertion that DoWhy can always identify or refuse arbitrary graphs; it is a documented *Cognitum safety preflight*.

## Genuine methods and comparison fairness

- **Cognitum P2A arithmetic:** exact rational standardization by `Z`, independently checked through P2A's inverse-weighting algebra. This is an exact empirical contrast, not an exact causal truth claim.
- **DoWhy `CausalModel` / `backdoor.linear_regression`:** genuine DoWhy source API with graph identification, observed adjustment and optional 10-simulation placebo diagnostic. The standard linear regression *does not specify a `T×Z` interaction* and should not be compared as a fully heterogeneous CATE estimator.
- **EconML 0.17.0 `LinearDML`:** genuine library run, three-fold cross-fitting, LogisticRegression treatment nuisance and LinearRegression outcome nuisance, fixed RNG, `X=Z`; conditional effects reported at both `Z` levels and aggregated separately.
- **statsmodels 0.14.6 saturated OLS baseline:** formula `Y ~ T * Z` specifies the heterogeneous interaction explicitly; it agrees with the empirical standardization on a positive-overlap two-stratum binary fixture by construction. This controls for a **model-specification mismatch**, not a claim that one library is universally better.

Numerical values for DoWhy standard OLS, EconML DML, and the saturated OLS are different *methods* with potentially different finite-sample errors. Do not rank them from five seeds, compare nominal confidence intervals that were not estimated, or promote regression adjustment to identification when confounding is unmeasured.

## Mean absolute error versus known population ATE

| N | Fixture | P2A exact empirical | DoWhy linear | EconML DML | statsmodels interaction |
|---:|---|---:|---:|---:|---:|
| 300 | Observed homogeneous | 0.0304 | 0.0309 | 0.0301 | 0.0304 |
| 300 | Observed heterogeneous | 0.0250 | 0.0595 | 0.0296 | 0.0250 |
| 300 | **Hidden confounding** | **0.1980** | **0.2002** | **0.1986** | **0.1980** |
| 300 | Null effect | 0.0415 | 0.0396 | 0.0435 | 0.0415 |
| 900 | Observed homogeneous | 0.0316 | 0.0332 | 0.0313 | 0.0316 |
| 900 | Observed heterogeneous | 0.0325 | 0.0397 | 0.0329 | 0.0325 |
| 900 | **Hidden confounding** | **0.1438** | **0.1438** | **0.1442** | **0.1438** |
| 900 | Null effect | 0.0145 | 0.0133 | 0.0144 | 0.0145 |

All numbers are averages over **five fixed seeds**, not error bars or inferential confidence intervals. On the 10 no-overlap datasets, all methods were marked **not run** after reference preflight rejection. On the 10 hidden-confounding datasets, the explicit-latent-graph analysis was **blocked**; the omitting-`U` results are shown only to quantify bias under a known assumption violation. The placebo permutation diagnostics were calculated on the observed-homogeneous datasets and carry `DIAGNOSTIC_ONLY_NOT_UNCONFOUNDEDNESS_PROOF` assurance.

The key result is negative: closely matching estimates from several mature methods can still be **materially wrong** when their shared identifying assumptions are false. This is an engineering justification for Cognitum to surface model assumptions and abstain, not evidence that cross-method consensus proves causation. Consult DoWhy's refutation and sensitivity analysis documentation for the intended distinctions, and EconML's unconfoundedness assumptions for DML.

## Validation / tamper resistance

- The G7 runner uses a bounded fixed list of synthetic generators, source root specified by a human developer, and genuine scientific imports; it **does not run inside Lu**.
- Report replay independently regenerates each dataset from seed and sample size; verifies its SHA-256, oracle effects, exact rational estimates, all claimed error metrics, and aggregate summaries; rejects tampered conclusions and simulated production/attested-release claims.
- Two JSON evidence files are replayable without DoWhy or EconML installed; **replay does not authenticate code provenance, establish the causal graph, or verify a scientific runtime was genuinely executed**. That requires separate logs, source hashes, and runtime admission.
- G7 adds no new Protobuf schema and does not change the fail-closed DoWhy production worker. All prior G5/G6 worker boundary tests are retained.

## Limitations, open gates and next work

- Uploaded DoWhy `main` source has package placeholder `0.0.0`. It is **not independently verified as v0.14 release**. Do not bypass version pinning for production.
- Neither a Linux `-I` subprocess nor an isolated Python virtual environment demonstrates Windows Job Object/AppContainer security, authenticated Lu authorization, policy revocation, or process cleanup.
- This is a limited synthetic exploratory fixture family, not validated causal effect coverage, a real-world accuracy estimate, a comprehensive identifiability study, or the final five-tier Lu+Cognitum LLM benchmark.
- Next: wider nonlinear/non-Gaussian and treatment assignment generators; honest bootstrap/interval coverage and power; verified release wheelhouse/licensing; native Windows authorization gates; context-aware Lu orchestration benchmarks.

## Reproduction

From the G7 source root, use the externally prepared scientific interpreter and separately reviewed DoWhy source:

```sh
PYTHONPATH=.:tests /path/to/scientific/python tools/run_c14_p4e_g7_study.py \
  --source-root /path/to/reviewed/dowhy-main --n 300 \
  --report docs/components/causal/P4E-G7-n300-seeded-evidence.json
PYTHONPATH=.:tests /path/to/scientific/python tools/run_c14_p4e_g7_study.py \
  --source-root /path/to/reviewed/dowhy-main --n 900 \
  --report docs/components/causal/P4E-G7-n900-seeded-evidence.json
PYTHONPATH=. python tools/run_c14_p4e_g7_smoke.py
PYTHONPATH=.:tests COGNITUM_DOWHY_SOURCE=/path/to/reviewed/dowhy-main \
  /path/to/scientific/python -m unittest tests.test_c14_p4e_g7_multifixture -v
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c14*.py'
PYTHONPATH=.:tests python -m unittest discover -s tests -p 'test_c13*.py'
PYTHONPATH=. python tools/verify_protobuf_schemas.py
```

No third-party source or compiled library is redistributed in this checkpoint.
