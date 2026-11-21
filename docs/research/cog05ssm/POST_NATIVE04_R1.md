# COG-05-SSM-POST-NATIVE-04-R1 — Exact-source integration and native qualification

## Scope and status

**Final disposition: PASS for bounded native Windows/Linux qualification.** [Run 44842101661](https://github.com/vjmichael/cognitum/actions/runs/44842101661) completed SUCCESS on Ubuntu/Windows Python 3.11/3.13, fixed source SHA `6160e322ba24f8ec4d8f4a7d90ad885daeb32c92`; all four environments report 38/38 dedicated and 67/67 combined tests, zero failures/errors/skips. See [independently verified per-target artifact SHA-256 manifest](POST_NATIVE04_R1_NATIVE_ARTIFACTS.json). The native tests include the seven previously unexecuted true HDC/KAN/SSM integrated multihorizon cases.
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

### Required native acceptance — completed
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

## Native receipt and reproducibility closeout

The four JUnit inventories are identical, every recorded test log/XML SHA-256 matches the downloaded artifact, all 10 newly introduced mathematical/test/data source Git blobs and all 6 inherited POST-NATIVE-03 source blobs agree across the four environments, and the original fixed UCI archive reproducibly yields byte-identical Changping/Dingling/Guanyuan excerpts. Each job completed SUCCESS. This is 152 dedicated and 268 combined scoped test executions (38 and 67 distinct test cases repeated on four systems). The native qualification branch is a metadata-only identical-tree successor of the research candidate; the accepted 391-case, POST-NATIVE-02 44/63 and POST-NATIVE-03 29-case source locks remain unchanged. **There are no remaining failing tests in this bounded qualification.**

**Still open:** Bayesian/dependence-valid conditional coverage, uncertainty under changing pollutants, missing-window selection bias, independent publishers/interventional physical observations, trained HDC/KAN/SSM generalization, measured physical causal laws and actual workstation hardware. The imperfect 24h 90% coverage (87.8%, 82.5%, 75.8%) and confidence intervals that include zero are retained unchanged. The method is non-authorizing; all 72 comprehensive mathematical capability entries remain PARTIAL.
