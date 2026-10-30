# C13 P3 — Continuous and hierarchical inference (2026-10-27)

**Maturity:** bounded, typed, numerically verified conjugate Gaussian reference; optional host-pinned PyMC NUTS/ADVI adapter **not live-runtime validated**. No complex probabilistic-language parser, no arbitrary user/model Python code, and no performance claims. This is one substantive classical case, *not* the entirety of mature probabilistic programming.

## Library-first assessment

| Engine | Mature capability | C13 P3 disposition |
| --- | --- | --- |
| PyMC (https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sample.html) | HMC/NUTS, variational approximation, posterior predictive sampling, hierarchical random effects | Pinned optional worker; `pymc.sample` and `pymc.fit(method='advi')` templates; **live unavailable** (installed PyMC import fails on incompatible ArviZ) |
| ArviZ (https://python.arviz.org/projects/stats/en/stable/api/generated/arviz_stats.rhat.html) | Rank-normalized R-hat, bulk ESS, posterior diagnostics | Optional MCMC-only diagnostics; 1 chain and ADVI report *unavailable*, not healthy |
| Pyro (https://docs.pyro.ai/en/stable/inference.html) | HMC/NUTS, SVI, amortized inference, flexible stochastic models | Future optional worker; not installed or tested |
| NumPyro (https://num.pyro.ai/en/latest/mcmc.html) | JAX NUTS/HMC, SVI, accelerated inference | Future optional worker; not installed or tested |
| SciPy/NumPy | Stable Cholesky linear solves, Gaussian matrix conditioning | **Executed** as independent analytical-posterior oracle |

**Decision:** Restrict first continuous model family to a known-variance hierarchical Gaussian random-intercept model, with analytic posterior as its independent mathematical standard. Avoid writing an untested toy MCMC/NUTS algorithm. Add general nonlinear models, unknown scales, nonconjugate distributions, GLMMs, posterior predictive checks against held-out outcomes and genuine NUTS convergence gates as separate C13 features. Do not label raw PyMC output as a certified posterior.

## Specified model and mathematical meaning

`global ~ Normal(global_prior_mean, global_prior_sd)`

`group_mean[j] | global ~ Normal(global, group_sd)` for each declared group j.

`y[i] | group_mean[group[i]] ~ Normal(group_mean[group[i]], known_sd[i])`.

For a future new observation in group j: `y_new[j] | group_mean[j] ~ Normal(group_mean[j], predictive_sd)`.

All standard deviations are **known positive constants**. This is genuine partial pooling: observations in one group affect the global mean and thereby the posterior in other groups. The model is not a learned adaptive empirical-Bayes hyperparameter model and has no causal interpretation.

`cognitum/probability_continuous.py` computes the normal posterior using its **precision matrix** and Gauss-Jordan inversion for the small finite model. Independently, a separate SciPy Cholesky verifier computes the same posterior using **prior-covariance conditioning** on the observations. A reference result receives a numerical check only if the means, variances, predictive distributions and central Gaussian 95% intervals agree (within defined floating tolerance). The "exact Gaussian reference" flag means analytic Gaussian mathematics numerically solved, **not** exact rational floating-point arithmetic or a certified proof for arbitrary models.

Output: global and group posterior means, SDs, equal-tail 95% marginal intervals, and future-observation predictive mean/SD. The P3 interface never serializes the full dataset into the audit record.

## Assurance and deployment boundaries

- `proto/cognitum/probability/v1/continuous.proto` and `cognitum/proto/probability_continuous_pb2.py` are compiler-equivalent native Protobuf contracts. No user/model-controlled executable or generated Python source field.
- Hard resource limits: 16 groups, 128 observations, 20-second declared per-request limit; sample engines 50–2000 draws, 1–4 chains, 0–3000 warmup. The reference is a bounded synchronous Python operation; Python timeout is a checked deadline, **not a preemption guarantee**. A sample backend is a separate pinned child process with forced deadline and output cap.
- Independent SciPy matrix-conditioning verification is **limited to 48 observations**. Larger exact-reference results may be computed, but are *not certified*; verified receipts remain false. No proof-of-convergence flags for a failed, unsupported or uncertain result.
- Host-owned `WorkerPolicy` pins child Python executable, worker source and adapter source by SHA-256 and expected PyMC version. Missing or mismatched files are rejected. This **does not** attest every transitive Python package/wheel. Worker is disabled by default. Linux process-group termination is implemented; Windows Job Objects and authentic Lu permissions are not.
- NUTS and ADVI, **when run in a compatible actual PyMC environment**, are stochastic numerical inference, not mathematical proofs. The verifier checks submitted posterior moments against the independent conjugate solution using coarse sampling tolerances and validates diagnostics fields. Such tolerance checks are not calibration, convergence evidence or proof of distributional fidelity; only analytic reference results can raise the analytic-reference flag.
- Actual runtime state **here**: installed PyMC import raises `ImportError: cannot import name 'concat' from 'arviz'`. ArviZ migration and PyMC packages are incompatible. No genuine NUTS or ADVI output was accepted. This is a **deployment dependency gate**, not a reason to impersonate mature libraries with handwritten sampling. Test for a matching pinned PyMC/ArviZ environment before production.
- This remains Python/Linux functional code, not installed in Lu, Windows packaged, sandboxed, externally benchmarked or tested with a real model; C02 native host authority remains open.

## Functional checks (not performance benchmarks)

```bash
PYTHONPATH=.:tests OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m unittest tests.test_c13_p3_continuous -q
PYTHONPATH=.:tests OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python tools/run_c13_p3_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

The independent oracle compares differently formulated Gaussian posteriors (precision inversion versus covariance conditioning), and the tests include seeded random normal models, prior-only/posterior-predictive invariants, hostile Protobuf inputs, forged results/receipts, integrity mismatches and default-off worker. One optional real-runtime test is skipped because the installed PyMC/ArviZ pair cannot import. See `P3-functional-test-evidence.json` for final group totals and `START_HERE.md` for the active source checkpoint.

## Future research and standards milestones

1. Run real PyMC NUTS/ADVI in a pinned compatible Python environment on Windows; compare outputs with independent analytical results; add posterior predictive draws and actual rank-Rhat/bulk and tail-ESS checks.
2. Implement a typed **general model graph** using mature probabilistic-programming runtimes, with safe distribution/plate/transform allowlists, dimension checks, identifiable priors, censored/missing data handling, GLMM and unknown-scale hierarchical models; no model-authored arbitrary Python execution.
3. Integrate optional Pyro/NumPyro as alternative mature engines, and research amortized variational methods, geometry-aware reparameterization and SMC backends behind the same host permissions, audit receipts and benchmark-ready contracts.
4. Defer broad comparisons, statistical calibration, real-world benchmark datasets and Lu end-to-end performance claims until the Cognitum component portfolio is complete, per user decision.
