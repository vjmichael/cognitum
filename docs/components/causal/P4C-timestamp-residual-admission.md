# C14 P4C — Timestamp admission and bounded residual diagnostics

**Checkpoint:** 2026-10-28. Offline Linux Python 3.13 functional-reference slice. Not certified on Windows x86-64; not registered with authenticated Lu host; no actual controlled device intervention, causal identification or LLM benchmark was run.

## Scope and standards-first references

P4A computes conditional fixed-lag *predictive* F screens but receives only a declared interval, not observation timestamps. P4C makes that limitation concrete by adding actual timestamped rows and rejecting unsupported data paths before constructing an optional P4A **candidate** request. It is deliberately separate from P4B, which computes mathematical interventions *only inside a fully supplied structural causal model*.

- `proto/cognitum/causal/v1/temporal_diagnostics.proto` and compiler-derived `cognitum/proto/causal_temporal_diagnostics_pb2.py`: request, typed cadence and diagnostics statuses, per-variable whiteness check, bounded replay receipt.
- `cognitum/causal_temporal_diagnostics.py`: host-default-denied, bounded parsing and finite data validation; strict increasing timestamps; declared cadence actually compared to observed intervals; missing regular-grid slots and off-grid jitter reported without interpolation; no fixed-lag regression on irregular or gapped series.
- For exactly regular data, estimate a small linear multivariate lag model (bounded 2–4 variables, lag 1–3, 100–500 samples). Calculate an approximate Ljung–Box residual autocorrelation statistic with a correction for fitted lag order. Apply a Bonferroni adjustment across the variable targets. A rejection **blocks** the optional bridge; non-rejection never establishes residual independence, stationarity or causation.
- `make_screen_from_regular_timestamps` constructs a P4A candidate only if the original diagnostic result matches a same-algorithm request-bound numerical replay, reports exact regular cadence and has no residual-autocorrelation rejection. It **never** grants Lu permission to run the P4A operation, and P4A still defaults to denied.
- `TemporalDiagnosticReceipt.numerical_replay_checked` means same-algorithm deterministic replay, **not independent proof**. The tests include an actual independent software comparison to `statsmodels.stats.diagnostic.acorr_ljungbox` (statsmodels 0.14.6 installed in the test environment). This baseline comparison is not part of lightweight core runtime dependencies.

## Numerical and epistemic limitations

- Model: ordinary least squares linear vector-autoregressive screening with finite Gaussian-style diagnostic approximation. No nonlinear effects, high-dimensional sparse models, latent confounding, causal identification, learned structural mechanisms or instantaneous effects are claimed.
- For fitted residuals, use `Q = n(n+2) * sum_{k=1}^h r_k^2/(n-k)` and chi-square degrees of freedom `h - max_lag` as a diagnostic approximation. Its p-value is not a calibrated statement that residuals are independent. Finite-sample, missing-data, mixed-rate, heavy-tailed and model-misspecification scenarios require more sophisticated methods.
- An *irregular/gapped* observation series gets a valid diagnostic result **without interpolation** and with an explicit blocked fixed-lag screen flag. It is not rejected as an invalid data set; rather, standard fixed-lag Granger-style analysis is unsupported on those inputs. No claim of performing irregular causal discovery is made.
- A consistent timestamp grid still cannot establish stationarity, correct lag order, no measurement error or no confounding. Passing the preflight only permits generation of an *unexecuted* request candidate. The `statistical_assumptions_verified` and `causal_directions_verified` fields are hard-false.
- Future P4C extensions: optional pinned stationarity/structural-break diagnostic worker (ADF/KPSS and complementary tests with explicit nulls); time-interval-aware or continuous-time model, missingness mechanism assessment, and optional Tigramite/PCMCI reference after approved isolated installation. Never claim a time-series association implies a causal intervention effect.

## Assumption and reference survey

1. statsmodels Granger documentation explicitly disallows missing values and tests a predictive lag null, not an identified structural intervention: https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.grangercausalitytests.html
2. statsmodels published diagnostic methods and caveats on specification and model assumptions: https://www.statsmodels.org/stable/diagnostic.html
3. Tigramite/PCMCI has time-series causal discovery and mask support, but its runtime is not installed, reviewed or verified for this milestone: https://jakobrunge.github.io/tigramite/
4. Bahadori & Liu (2012), *Granger Causality Analysis in Irregular Time Series*, illustrates why unequal sampling violates assumptions of conventional fixed-step analysis: https://doi.org/10.1137/1.9781611972825.57
5. Contemporary research on irregular temporal causal discovery remains experimental and is not silently adopted as a mature runtime backend: https://arxiv.org/abs/2607.18226 (2026).

## Focused tests and negative cases

- 31 new P4C unittest methods: regular, gapped, off-grid, jitter, alternate origin, false interval, duplicate/out-of-order timestamp, malformed/floating invalid, insufficient data, ill-conditioned regression, synthetic AR(2) residual-autocorrelation rejection, tampered result/claim/p-value, host denial, disabled operation, correct P4A bridge, P4A remains unauthorized by default, oversized/noncanonical input, and actual statsmodels baseline equality.
- 5 new P4C smoke scenarios: valid regular, missing slot, off-grid, host denied, forged causal claim rejected.
- C14: 285 run, 280 passed, 5 optional dependency skips, 0 failures. C13: 141 run, 139 passed, 2 skips, 0 failures. 58 core/benchmark/proto tests pass. Independent Protobuf source-to-binding comparison 39/39; C03 smoke 10/10; original C14 smoke suites pass. Python compileall passes. Broad full historical regression was **not** run.

## Integration/security gates remain OPEN

Lu authentication and C02 Windows containment have not been exercised; local Python boolean gates are scaffolding only, not real authority. P2B/P3C DoWhy 0.14, EconML 0.17.0, causal-learn 0.1.4.8, and Tigramite actual worker execution remain unavailable/unverified here. No Windows Job Object, offline approved wheelhouse, model selection or LLM inference was tested. Comprehensive performance/research comparative benchmarks remain deferred under the Cognitum engineering standard.
