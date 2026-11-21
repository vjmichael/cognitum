# COG-05-SSM-POST-NATIVE-05-R3 — Independently verified source-locked native observational acceptance

**Disposition: PASS FOR THE BOUNDED TWO-PUBLISHER OBSERVATIONAL BENCHMARK ONLY.** Scientific objective **NOT FULLY CLOSED**: genuine HDC/KAN/SSM native OOD hypothesis-comparison, independent original sensor attestation, valid dependent coverage under drift, physical-law identification, and data-specific rights/units remain unresolved.

## Exact-source four-platform acceptance

- Native [workflow run 44844570161](https://github.com/vjmichael/cognitum/actions/runs/44844570161) terminal **SUCCESS** at SHA `127672af94fb126163efd51057dfd5adf0f9bb4e`.
- Ubuntu Python 3.11 and 3.13, Windows Python 3.11 and 3.13: **15/15 dedicated tests per environment**, no failures/errors/skips.
- Four downloaded artifact ZIPs independently inspected for 15 matching test identities, identical exact immutable source pin maps, per-target JUnit/log/science.json SHA256 reconciliation and cross-platform agreement in held-out RMSE/MAE.
- 5 source/data custody pins: research module `ffbc2c0f14ec8f8e46c97ee2f1e0bfa9adeef7d7`; tests `adc71996bda0cfec0e01e580b981b236bd533d3b`; NOAA file `8421af63a839c767555a53af74b71106ee68241e`; USGS file `2f986df07dce96b800829856e751b247e4179aaf`; Windows byte-preservation rule `07826903c67f6eb9bd58aa2d84bf200a88659251`. All ten previous POST-NATIVE-04 and six POST-NATIVE-03 source/data pins remain preserved. **No historical source files or original `.gitattributes` changed.**
- First candidate failed on explicit insufficiency of USGS missingness sample. Second candidate repaired that refusal but detected a test assertion name mismatch. Third candidate passed Linux and found Windows checkout CRLF byte drift. Final candidate adds only scoped nested no-EOL-transformation rule and re-pins exact sources. Original NOAA and USGS raw Git blob hashes match on all four hosts.
- [Machine-readable four-target artifact checksum manifest](POST_NATIVE05_R3_NATIVE_ARTIFACTS.json) records ZIP and receipt SHA256; no claimed upstream publisher-signature verification.

## Physically observed and derived system findings (held-out)

**NOAA CO-OPS RA partner-provided water-level trajectory:** 34,099 source rows, 9 conflicting timestamps / 18 rows quarantined, 34,081 admitted timestamps, 1,491 irregular observed intervals. Byte-identical source organization Git blob. Original site instrument attestation, input unit and NOAA's reuse authority over partner data **not independently certified**.

| Actual elapsed forecast horizon | Held-out observations | Persistence RMSE | Direct ridge RMSE | Observed 90% block-max diagnostic coverage for calibration-selected model |
|---|---:|---:|---:|---:|
| 5 min | 5,896 | 0.01515 | 0.00908 | 99.61% |
| 30 min | 5,325 | 0.07893 | 0.03424 | 98.22% |
| 120 min | 3,307 | 0.29731 | 0.16077 | **80.98%** |

These results use the input data's **unverified value units**. At 120 min, nominal 90% coverage declined from **92.20%** in the first held-out half to **69.77%** later. Simultaneous complete-block coverage was only **59.78%**. Thus dependence/drift validity has **not** been established. Synthetic `+3×` radius shift reduces empirical interval coverage to 0, a counterexample not an observed physical event.

**USGS Colorado River natural-flow reconstruction:** 110 years (1906–2015), not a raw discharge instrument trace. Under the 1-year forecast, persistence held-out RMSE **5.070 million** in original but unverified flow units, direct ridge **5.421 million** (worse). At 3/5 years, training-mean baseline held-out RMSE 4.180/4.254 million versus direct ridge 4.366/4.503 million. Only 3–4 calibration blocks were available, versus 20 required, and only 15–19 eligible test origins; both dependence interval and counterfactual missingness-sensitivity diagnostics are explicitly **REFUSED** rather than reported as statistically qualified.

NOAA periodic-dropout and upper-tail-censoring counterfactual checks show complete-case selection can change RMSE (for 120 min, full 0.16077, periodic outage 0.16073, censored high outcomes 0.13413). These are *selection-bias stress tests* using known held-out outcomes only retrospectively, not hidden predictor lookahead and not observational intervention effects.

## Scientific falsification and remaining obligations

1. The native previously qualified HDC/KAN/SSM temporal integration is **fixed-step**. NOAA's genuine irregular timestamps are not a lawful uniform-step input. The module explicitly refuses pretending one array index is one fixed 5-min interval. This falsifies **the applicability assumption** but does **not** measure HDC/KAN/SSM relative forecasting performance.
2. USGS's very short annual reconstructed record cannot supply the previously required high-capacity KAN/HDC training and dependence-block budgets. Preserve a refused scientific trial; do not train/test on fabricated replicated observations.
3. Direct ridge outperforms NOAA persistence, but the simpler USGS controls outperform ridge at several horizons. No universal superiority, discovered physical law, causal parameter identification, coverage guarantee, signed original sensor evidence, or autonomous execution authorization is demonstrated.
4. **Next task: POST-NATIVE-05-R4** — source an independently legally qualified, adequately long directly measured system with traceable units/clock; implement a genuinely time-aware native SSM + HDC/KAN route for uneven observations or qualify a separate regular measured system, and preregister same-origin ablation against stronger physics-derived baselines plus interval drift tests. Preserve negative results and require four-target same-SHA evidence.

All **72 broad dynamical/mathematical capabilities remain PARTIAL**. Scope does not grant any Lu, Maj Vaj, production, or external actuation access. This source SHA remains accepted *only* for its narrowly defined observational mathematics.
