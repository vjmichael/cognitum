# C13 P4 — Expanded conjugate likelihoods and mature ArviZ chain diagnostics

**Status (2026-10-27): functional offline reference; NOT a general-purpose probabilistic-programming engine.**

## Standards / library-first assessment

- Mature probabilistic programming engines: **PyMC**, **Pyro**, **NumPyro**. PyMC supports NUTS, ADVI, posterior predictive sampling and hierarchical distributions. Their arbitrary-model runtimes, distribution ASTs, automatic differentiation, compositional transformations and robust worker lifecycle require real packaging and verification, not custom approximations.
- Mature diagnostics: **ArviZ** rank-normalized split R-hat, bulk/tail effective sample size, Monte Carlo standard error. **This phase calls ArviZ 1.1.0 directly** on host-provided chain arrays. Diagnostics are not evidence that the posterior model is appropriate or that chains truly converged. A trace can be fabricated; the Lu host must independently authenticate and retain provenance for draws.
- Mature distribution math: **SciPy** beta, beta-binomial, gamma, negative binomial, Student-t. Conjugate algebra is coded as typed bounded templates because no full PyMC backend operates in this runtime. Numeric results are cross-checked using separate sufficient-statistics derivations and scipy.stats distribution moments/quantiles, not formal proofs of the model assumptions.
- PyMC was present but **failed to import** in this test environment (`ImportError: cannot import name 'concat' from 'arviz'`); Pyro/NumPyro not installed. We did **not** patch a shared Python installation, silently downgrade ArviZ, or claim successful NUTS/ADVI sampling.

## Implemented scope

`proto/cognitum/probability/v1/conjugate.proto` and `cognitum/probability_conjugate.py` support three typed families (no code execution):

| Family | Posterior | Posterior predictive |
|---|---|---|
| Beta–Binomial | Beta(a+s, b+f) | Beta-binomial future success count |
| Gamma–Poisson (rate prior) | Gamma(shape+sum counts, rate+sum exposures) | Negative binomial future count |
| Normal–Inverse-Gamma (unknown Gaussian mean and variance) | Updated NIG with mu/kappa/alpha/beta | Student-t future observation; marginal posterior for mean is Student-t |

Credible/predictive 95% equal-tail intervals, posterior/predictive means and variances, and explicit **undefined-moment flags** are included. For Student-t with df<=1 the mean is undefined; df<=2 the variance is undefined; zero must never be interpreted as a defined moment. Strict observation bounds, finite checks, deadlines, disabled-by-default invocation, and metadata-only request-bound audit receipts are implemented.

`proto/cognitum/probability/v1/diagnostics.proto` and `cognitum/probability_diagnostics.py` support multiple named parameters with >=2 complete chains and >=20 draws per chain, capped at 8 parameters, 8 chains, and 2,000 draws/chain. Actual ArviZ APIs compute rank-normalized R-hat, bulk/tail ESS, and MCSE(mean). A constant-chain or otherwise undefined calculation returns UNKNOWN, not verified evidence. Receipts recompute numbers from supplied chain bytes, but they do not authenticate their origin or certify convergence.

Both result envelopes include request digests and bounded verification receipts. Audit records exclude raw data and chains, but timing and metadata are still subject to Lu's privacy and retention controls. JSON is used only in test evidence and checkpoint manifests—not component IPC.

## Non-goals and remaining production gates

- Full PyMC NUTS/ADVI execution: **blocked by environment's PyMC–ArviZ version incompatibility**; keep the P3 host-pinned worker in place for later fixing in an isolated offline environment.
- Pyro/NumPyro runtime backends; generalized model AST, priors/transforms, multivariate sampling, missing-data, nonconjugate HMC/NUTS/VI; and Pareto-k/LOO/WAIC calibration are **not implemented**.
- No Lu-native authorized trace admission; no Windows Job Object sandbox; no hard process kill for these in-process SciPy/ArviZ calls; Python `host_authorized` flags are synthetic test boundaries, not Lu security credentials.
- No model or research backend is enabled by default. Existing C08 and C09 archived research remains deferred. No full model or hardware comparative benchmarks until owner-authorized end-of-portfolio evaluation.

## Focused functional tests

`PYTHONPATH=.:tests python -m unittest -q tests.test_c13_p4_conjugate tests.test_c13_p4_diagnostics`

`PYTHONPATH=.:tests python tools/run_c13_p4_smoke.py`

`PYTHONPATH=. python tools/verify_protobuf_schemas.py --require`

Scientific references: https://docs.pymc.io/ ; https://www.pymc.io/projects/docs/en/stable/api/generated/pymc.sample_posterior_predictive.html ; https://python.arviz.org/en/stable/api/generated/arviz.rhat.html ; https://python.arviz.org/en/stable/api/generated/arviz.ess.html ; https://docs.scipy.org/doc/scipy/reference/stats.html ; https://num.pyro.ai/en/latest/diagnostics.html .

**Next:** C14 causal inference/counterfactuals. Carry unresolved probabilistic runtime issues into a follow-up integration backlog, not a claim of completed PyMC.
