# COG-05-SSM-POST-NATIVE-04-R1 — Exact-source integration and native qualification

## Scope and status
The research candidate has been published as exact original-tested Python/source/observational bytes. The prior POST-NATIVE-03 and POST-NATIVE-02 source-locked accepted native baselines are **unchanged**.

This is bounded multihorizon observational benchmarking, **not autonomous discovery of a physical law**. Research-only; no external actuation rights.

### Source/data pins
- `cognitum/research/ssm_multisite.py`: `9a50fdc893eae88c956ce0ec0bc2a9379725ce9d`
- `research_tests/ssm_postnative04/test_multisite.py`: `c53646d7c06ecca2348f0531ddb7b91885d77ab9`
- `research_tests/ssm_postnative04/test_native_hybrid.py`: `54c1dd874b6000f968740ef4c92680eda209ed9f`
- `tools/ssm_postnative04/acquire.py`: `d1261060d3e7942c4e964c882e9b98cbe9b25c4b`
- `research_tests/ssm_postnative04/data/sources.json`: `bc4f1e632a08c677a861a9208036bf87df63df5c`
- `research_tests/ssm_postnative04/data/acquisition.json`: `67afd02bd74dc6c2e856279f9437392c17f4312f`
- `Changping.csv`: `60162fd7183d4ca62a869ddb4fa47d2eb43c076e`
- `Dingling.csv`: `f083504372ba2ab3083d8518b910a8c1fd850ebd`
- `Guanyuan.csv`: `12c1c4665eaedfc0d314fd4ede22c6bc8e27fff5`
- `.gitattributes`: `e83fceb4c919fb7d0289e28a2727ffd2bc6cea9e` (Windows LF for exact measurement bytes)

Every pin was checked against the actually published Git blob. The original UCI501 outer ZIP SHA256, nested ZIP SHA256, three complete member SHA256 values, CC BY4 license statement, and each derived 6,144-row excerpt SHA256 are in `sources.json`. The original 8.2 MB archive is preserved in the separately supplied local research candidate, and all 18,432 excerpt observations were rederived from that archive. Original publisher signatures were **not** verified.

### Independent local qualification
From the exact ZIP source version, Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 / pytest 9.0.2:
- 31/31 new non-native tests PASS.
- 54/54 with inherited POST-NATIVE-03 locally executable regression tests PASS.
- 7 new genuine HDC/KAN/SSM integrated tests require the full installed Cognitum repository and native runners.
- Source ZIP contains a later bounded PM2.5 nonnegative-baseline output adjustment than an earlier loose local working copy; this exact ZIP version was retested before publication. No weaker tolerances or changed assertions.

### Required native acceptance
The dedicated `.github/workflows/ssm-postnative04-native.yml` workflow targets Ubuntu/Windows, Python 3.11/3.13, and installs fixed NumPy/SciPy/pytest. The `tools.ssm_postnative04.acceptance` gate requires a clean exact SHA, **10 new source/data pins plus 6 inherited POST-NATIVE-03 pins**, matching publisher-derived manifest, 3 × 6,144 preserved observations, **38/38 new cases** and **67/67 combined P03+P04 cases**, no failures/errors/skips. Preserve dedicated and combined JUnit/log SHA-256 with non-authorizing receipt. Do not assert acceptance from a workflow start; verify archived evidence and final four-job conclusions.

### Independent research and falsification
- Forecast horizons 1, 6, 24 hours; measured Changping, Dingling and Guanyuan PM2.5 target sequences, not duplicated station-weather columns. No missing-target interpolation; only fully observed windows are evaluated. This selection can bias estimates.
- Cross-site source weather can be correlated/duplicated across stations; sites share one UCI501 study/publisher. This is **not** transfer to an independent publisher.
- Matched fixed-lag persistence, seasonal, autoregressive, train-only direct ridge and phenomenological relaxation/wind dilution controls. Simplified physical baselines are **not calibrated causal transport or verified PDE models**.
- At 24h, held-out direct ridge RMSE 81.568/78.719/88.701 µg/m³ versus persistence 100.263/96.587/102.646 for Changping/Dingling/Guanyuan. Bootstrap MAE gain intervals straddle zero for two sites; cannot assert universal improvement.
- Block-max nominal 90% interval coverage 87.8%/82.5%/75.8% on those sites. **Dependence-aware descriptive calibration does not imply valid conditional or distribution-free coverage.** Cross-site HDC/KAN/SSM hypothesis superiority remains to be tested natively.
- Tests assert `execution_authorized=False`, domain/prediction reproducibility, missing-data refusal, held-out split isolation, wrong-answer ablations and HDC ambiguity abstention.

### Scientific validity residual
All 72 broad mathematical capability groups remain PARTIAL. Real monitored PM2.5 observations prove measured trajectories, not physical-law identification, interventional causality, reliable per-site dependent confidence coverage, source signing, or general autonomous mathematical science. Do not merge this with production or Maj Vaj control.
