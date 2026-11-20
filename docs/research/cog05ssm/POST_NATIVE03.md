# COG-05-SSM-POST-NATIVE-03 — Real observed physical dynamics, source provenance, and independent falsification

**Status: PASS for bounded, observational one-step research qualification.** This is not confirmation of an autonomous scientific discovery, identifiable physical law, general calibration, or physical-workstation acceptance.

## Native source-locked qualification

[Run 44837589141](https://github.com/vjmichael/cognitum/actions/runs/44837589141) completed SUCCESS on Ubuntu/Windows Python 3.11/3.13, **29/29 scoped tests on each target**, no failures, errors or skipped cases (116 test executions, 29 unique test cases). Qualification SHA: `9c02f020136744930e3708a2b00f5a1db6d34dd8`. The independently checked [artifact manifest](POST_NATIVE03_ARTIFACTS.json) records four GitHub ZIP artifact digests, six exact source Git blob pins, consistent test inventories and per-platform original fitted KAN snapshot hashes. All embedded receipt JUnit/log SHA256 checks pass. Numerical predictions agree within 1e-10, but the **trained KAN checkpoint SHA256 is not bitwise identical across operating systems**, owing to small numerical differences in least-squares coefficients. This must not be reported as bit-exact cross-platform model reproduction. No changes to the previously verified 391-case SSM-09B and 44/63 POST-NATIVE-02 baseline.

Historical native failures are retained: [run 44837152472](https://github.com/vjmichael/cognitum/actions/runs/44837152472) failed during setup because the custom scientific extra did not install NumPy/SciPy; [run 44837400403](https://github.com/vjmichael/cognitum/actions/runs/44837400403) passed Ubuntu but failed Windows because Git changed JSON manifest LF to CRLF. Explicit NumPy 2.3.5/SciPy 1.17.0/Pytest 9.0.2 and Git LF checkout attributes resolved both **without changing the mathematical test thresholds**.

## Source and license provenance

These are independently published sensor observations with a 10-minute/hourly time coordinate, **not simulated/checkpoint equations**:

| UCI archive | License / provenance | Retained actual observations | Source identity |
|---|---|---:|---|
| [Appliances Energy Prediction, UCI 374](https://archive.ics.uci.edu/dataset/374/appliances+energy+prediction), [DOI](https://doi.org/10.24432/C5VC8G), author Luis Candanedo | UCI CC BY 4.0; cite origin and attribution | First 6,144 consecutive 10-minute readings of T1, T2, T_out, RH_1 and appliance energy | Official source ZIP SHA256 `2fccf354445d886e7917620b0195db1f3e3e34d5a067a93b844694a4c561255a` |
| [Beijing Multi-Site Air Quality, UCI 501](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data), [DOI](https://doi.org/10.24432/C5RK5G), author Song Chen | UCI CC BY 4.0; cite origin and attribution | First 6,144 consecutive hourly Aotizhongxin readings; temperature, pressure, wind and PM2.5 auxiliary | Official source ZIP SHA256 `b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4` |

Original whole ZIP byte archives and independent acquisition receipts preserved in [GitHub Actions acquisition artifact 14678471230](https://github.com/vjmichael/cognitum/actions/runs/44835810983/artifacts/14678471230). The two selected 6,144-row CSV excerpts are committed under `research_tests/ssm_postnative03/data/`, together with versioned `sources.json` listing original archive SHA256 and CSV-member SHA256. **Every one of the 12,288 retained rows was compared with a fresh extraction from the original archive**. The complete building source member additionally matches the [original author's GitHub CSV](https://github.com/LuisM78/Appliances-energy-prediction-data/blob/master/energydata_complete.csv) Git blob `7535108143b2f78a0fbaa38b99ff20be5f475f96`. For Beijing, original ZIP is identified by acquired byte digest and UCI origin, without a second independently signed publisher source. Hashes identify frozen bytes; they do not authenticate an author's signature or guarantee earlier upstream history.

Beijing excerpt retains **nine missing PM2.5 auxiliary values** unmodified; PM2.5 is deliberately not used in the temperature predictors. No missing target/selected forcing was interpolated.

## Prespecified chronological evaluation

For each of the two 6,144-point observed series, separate training, calibration and held-out testing with **3,685, 1,228, and 1,228** usable transitions, excluding boundary-crossing transitions. One-step teacher forcing uses observed state and forcing at time *t*, not held-out observations from *t+1*; this is not a blind long-horizon rollout.

Baselines and scientific hypotheses: persistence (next temperature = last temperature), real one-dimensional linear SSM/ARX fitted on training data only, independently compared SciPy least squares, genuine one-layer Cognitum `kan_trainable.Network` Chebyshev-basis nonlinear residual (train-only; fit snapshot), and the genuine `hdc_algebra.Spec('MAP')` + `hdc_associative.Cleanup` trained candidate bank. The resulting HDC candidates adjust only small train-derived regime residuals; 8/1,228 test queries on each dataset abstain. HDC similarity is neither calibrated likelihood nor proof of physical regime. Wrong-sign dynamics is an explicit negative-control hypothesis. No cross-boundary/future training or test-set model selection.

### Held-out results (lower RMSE is better)

| Dataset / unit | Persistence RMSE | Linear SSM RMSE | KAN-corrected RMSE | Full HDC/KAN/SSM RMSE |
|---|---:|---:|---:|---:|
| Building T1, °C, 10 min | **0.052288** | 0.054006 | 0.053569 | 0.053809 |
| Beijing TEMP, °C, hourly | 1.447853 | 1.453282 | 1.439523 | **1.439502** |

**Falsification:** Persistence outperforms both learned linear SSM and full HDC/KAN/SSM in the indoor building trace. Beijing full HDC/KAN/SSM has a slight held-out RMSE improvement versus persistence (about 0.58%), but the separate block-bootstrap **MAE-gain 95% interval remains negative** in both series (building [-0.00721,-0.00329] °C, Beijing [-0.02399,-0.00837] °C). Therefore, there is no defensible general claim that the combined architecture beats a simple baseline. The wrong-sign dynamics control loses to persistence on both held-out periods.

### Uncertainty and distribution-shift limits

- Nominal 90% split-conformal empirical held-out coverage for **full model**: building **91.61%**, Beijing **86.16%**. Beijing first versus second held-out half **89.25% → 83.06%**, consistent with temporal nonstationarity/shift; do not claim calibrated 90% coverage in that domain.
- Absolute calibration radii (in °C) building **0.09460**, Beijing **1.92594**. Counterfactual +3-radius shift causes near-zero coverage; this is a *synthetic stress of real observations*, not a third measured trajectory.
- Exchangeability and stationarity are unverified. Block bootstrap is descriptive on this small number of temporally dependent segments; it does not independently certify inference validity or conditional coverage. No physical uncertainty calibration, no guaranteed detection or correction of drift.

## Scientific validity and remaining requirements

**Verified bounded scope:** real measured data with explicit CC BY 4.0 metadata and original UCI ZIP digests; row-wise transcript comparison and one external author blob comparison; deterministic chronological split and source-lock; real Cognitum HDC/KAN/SSM runtime composition; native Python runs on hosted Linux and Windows; no actuation. These do *not* establish physical causal dynamics, independent energy-conservation discoveries, symbolic equation identification, general scientific autonomy, robust multi-site forecasting, zero-shot domain transfer, or hardware-independent byte-identical learned models.

Research gaps: evaluate independent **multiple** sensor sites/periods, genuine multi-step state propagation, matched nonlinear and autoregressive baselines, calibrated dependent-time-series intervals, physically grounded interventional data/structural scientific hypotheses, uncertainty decomposition and signed publisher provenance where available. Physical Radeon/FPGA workstation qualification remains separate.

**Research capability ledger:** all 72 DS rows remain `PARTIAL`, none promoted by two pilot datasets. Explicitly preserve failed hypotheses and the non-authorizing `execution_authorized=False` state. The prior 391-case native and 44/63 post-native acceptance source locks remain unchanged.
