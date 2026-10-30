# C14 P4D — Bounded temporal stationarity and structural-change diagnostics

**Date:** 2026-10-28  
**Status:** functional Linux Python reference invoking the actual installed `statsmodels` API; not a causal identification engine, not Lu-integrated or Windows security-attested.

## Scope and baseline

Adds `proto/cognitum/causal/v1/temporal_advanced.proto` and independent, compiler-derived `causal_temporal_advanced_pb2.py` without changing any P4C wire fields. `cognitum/causal_temporal_advanced.py` implements exactly three established statistical diagnostics for regularly sampled observed numeric series:

1. `statsmodels.tsa.stattools.adfuller`, with fixed caller-selected ADF lag 0–3, intercept regression, `autolag=None`. **Null: unit root.** Rejecting suggests evidence against a unit root in the specified model; non-rejection does not prove a unit root.
2. `statsmodels.tsa.stattools.kpss`, intercept/level specification, automatic Newey-West-style lag selection. **Null: level stationarity.** Rejection suggests evidence against that stationarity assumption; non-rejection does not prove stationarity. KPSS p-values outside the lookup range are boundary-clipped by the reference library and explicitly flagged.
3. `statsmodels.stats.diagnostic.breaks_cusumolsresid`, with mean-only/intercept residuals and one fitted parameter. **Null: stable mean/intercept in the specified OLS model.** Rejection is a structural-instability *screen*, not changepoint localization or proof of physical intervention or causality.

The request embeds an unchanged P4C timestamp/sample request, so existing strict bounds (100–500 rows, 2–4 named variables, 1–3 declared P4C lag, trace, finite samples, monotone timestamps and explicit `familywise_alpha`) are reused. P4D then checks actual `declared_interval_ms` cadence, rejecting all gaps/jitter and never filling observations. It does not automatically convert nonstationary series or tune hyperparameters after looking at p-values.

## Interpretation and multiplicity

Bonferroni controls the nominal familywise threshold across `3 × variable_count` tests. The p-values describe different null hypotheses and do not constitute independent confirmation. Joint ADF/KPSS outcomes are categorized as evidence patterns (`PATTERN_COMPATIBLE_WITH_LEVEL_STATIONARITY_NOT_PROOF`, `PATTERN_OPPOSES_LEVEL_STATIONARITY_NOT_PROOF`, `CONFLICTING_NULL_REJECTIONS`, `BOTH_NULLS_UNREJECTED_INCONCLUSIVE`). Stationarity is **never verified** by accepting a null hypothesis, and a statistically well-behaved series is never proof of a particular causal direction.

The supplied series may violate assumptions behind these asymptotic tests (finite-sample distribution, autocorrelation treatment, lag choice, regime changes, nonlinear behavior, unmeasured confounders). Means, dynamics, and causal relationships are different concepts; only a mean-stability CUSUM is in this slice. Flags are diagnostic and conditional, not conclusive.

## Contracts, security and reproducibility

- Host authorization and a second capability enable switch are both required; model-controlled request fields do not grant permission.
- Strict canonical Protobuf decoding, bounded frame and runtime, deterministic serialized results, request SHA-256 binding, metadata-only receipt; no private observations in telemetry.
- `temporal_advanced_receipt` recomputes with the **same statsmodels implementation** and validates the entire outcome except elapsed time. This is **not independent mathematical proof**, does not verify statistical assumptions, and does not attest the operating-system sandbox.
- The `causal-temporal-advanced` dependency extra is optional. Missing `statsmodels` returns explicit `BACKEND_UNAVAILABLE` rather than silent fallback. No workers run in a privileged/unconfined process from Lu; this is a library reference engine and must remain inaccessible to untrusted model calls pending native host integration.
- No live Tigramite PCMCI evaluation. PCMCI/PCMCI+ can support conditional-independence tests with time-lag assumptions, but its result types and methods require a separate version-pinned, permission-checked worker and data/graph comparison suite. See https://jakobrunge.github.io/tigramite/ .

## Reproducibility

```bash
PYTHONPATH=.:tests python -m unittest tests.test_c14_p4d_temporal_advanced -v
PYTHONPATH=.:tests python tools/run_c14_p4d_smoke.py
PYTHONPATH=. python tools/verify_protobuf_schemas.py --require
```

Statistical methods: https://www.statsmodels.org/stable/examples/notebooks/generated/stationarity_detrending_adf_kpss.html ; https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.breaks_cusumolsresid.html

## Unresolved production gates

Actual native Win64 Job Object/handle/process containment; authenticated Lu tool admission; signed offline dependency lock and wheel audit; genuine DoWhy/EconML/causal-learn/Tigramite workers; time-series method comparisons under measured known mechanisms; large unbiased Lu+Cognitum quantization-controlled LLM efficacy benchmarks. Passing focused synthetic tests only validates bounded reference behavior.
