# C13 — Probability, Bayesian Inference and Calibrated Uncertainty: practical implementation

**Date:** November 4, 2026. **State:** code implemented on an isolated branch; native SciPy/Protobuf CI, merge, and real-model acceptance pending.

## Engineering choice: established libraries, not a research trap

- SciPy `scipy.special.logsumexp` provides numerically stable discrete Bayesian normalization. Our first-party code implements only the declared likelihood combination, bounds, provenance and explicit status.
- SciPy `scipy.stats.beta.ppf` provides beta posterior credible intervals for Bernoulli count data. We do not implement quantile solvers from scratch.
- Brier score, binary log loss and fixed-bin ECE are small auditable scoring identities requiring actual binary labels; these first-party checks are deliberately limited. Scores are **evaluations on supplied observations**, not universal claims of well-calibrated model uncertainty.

The component does not import a heavyweight Bayesian-network framework to solve a problem already represented by a small conditionally independent finite model. Full conditional-dependency Bayesian networks could use pgmpy when a concrete task calls for them; they are not silently claimed.

## Implemented operation 1 — Discrete observational Bayesian update

`cognitum/probability_bayes.py`: 2–16 finite named mutually exclusive hypotheses, normalized finite priors, 1–32 distinct named binary observations, likelihoods conditional on **each** hypothesis, and explicit signed observed/not-observed values. Requires prior and likelihood **source identifiers** and an explicit declaration of conditional independence given the hypothesis. Repeated evidence identifiers are rejected rather than silently double-counted.

The output uses SciPy log-sum-exp. `OK` returns a normalized posterior and log marginal evidence; `IMPOSSIBLE_EVIDENCE` returns **no invented posterior** where every likelihood path has zero probability; `NUMERICAL_FAILURE` and `UNSUPPORTED` are distinct. Log evidence is retained when direct probability underflows. Conditioning on an observed event is **not** causal inference or a guarantee the supplied prior/likelihood is scientifically valid.

## Implemented operation 2 — Beta-binomial credible intervals

`cognitum/probability_calibration.py`: bounded success/failure counts up to one million trials, positive source-declared beta prior shape parameters, requested credibility 50–99.9%, and SciPy beta quantiles. Returns posterior mean and central equal-tailed credible interval. Requires distinct prior/data source identifiers. A Bayesian credible interval is **not a frequentist confidence interval**, and no actual model calibration/coverage validation is implied.

## Implemented operation 3 — Held-out empirical calibration

`calibration_scores`: 10–100000 labeled binary examples, finite probabilities 0–1, 2–20 equal-width bins, source identifier, and Brier/log loss plus empirical expected calibration error. The boundary does **not** prove the labels came from held-out samples or quantify statistical uncertainty of ECE. ECE is dependent on binning and finite sample size; model confidence cannot be called calibrated merely because the user supplies probabilities.

## Native wire and verification

`proto/cognitum/probability/v1/probability.proto`, descriptor-backed `cognitum/proto/probability_pb2.py`, and `cognitum/probability_wire.py` provide typed `bayes`, `beta`, and `calibration` entrypoints. No model-authored scripts, plugins, network, Lu grants, or filesystem actions are present. Canonical Protobuf frames reject unknown, repeated, noncanonical and oversized input. Request SHA256 binds results to their typed input for correlation, **not authentication**.

The result decoder validates status and numeric ranges and recomputes the posterior, credible interval and calibration scores against the original supplied request; a numerically plausible but forged posterior fails. This is internal numerical reproducibility, **not a proof of source authenticity or independence assumptions**.

## Acceptance evidence and limits

- `tests/test_c13_probability.py`: 1%-base-rate inversion, explicit negative observations, 32 tiny likelihoods with stable log evidence, impossible evidence, duplicate observations, inconsistent priors, invalid NaNs, beta interval checks, perfect and uninformative forecast Brier/log/ECE, missing/invalid labels.
- `tests/test_c13_wire.py`: actual SciPy calls behind typed Protobuf, canonical framing and schema rejection, forged posterior, invalid source/evidence and numerical checks.
- `tools/c13_component_benchmark.py`: five real-SciPy reference cases, each with measured wall/process CPU latency, exact typed result checks, machine-readable JSON; no fabricated results.
- `.github/workflows/c13-probability.yml`: Windows/Linux × Python 3.11/3.13 real optional SciPy library, `pip check`, independent `grpc_tools.protoc` compiled schema parity and full regression/benchmark.
- `pyproject.toml`: optional `probability-stats` extra; the Cognitum core remains stdlib-only.

**No CI success claim is made until the exact branch head passes required native jobs.** Real-model A/B effectiveness, calibration on external held-out tasks, provenance authorization, OS worker isolation, and model-to-formula correctness remain C02/C03/C04/Lu integration acceptance gates.

## Known scope limits and stop rule

No general belief propagation, dependent-evidence Bayesian networks, variational inference, MCMC, automated prior elicitation, evidential source authentication, decision-theoretic utilities, causal interventions, learned uncertainty calibration or GPU inference are in this bounded v1 component. For a validated need, use maintained pgmpy/PyMC/ArviZ or other specialized libraries after a scoped license/platform/performance review. Do not begin a C14-style open-ended research program.

C13 code scope can be frozen after tests are corrected, native CI passes, and PR merge is complete; until then, it is **implementation committed, validation pending**, not independently production-certified.
