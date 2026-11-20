# COG-05-SSM-POST-NATIVE-04 — Independent multi-site observational systems and multi-horizon uncertainty

**Current status: LOCAL SCIENTIFIC CANDIDATE, NOT NATIVE-QUALIFIED.** Source bundle and independent original ZIP are available as the conversation artifact `COG_POST_NATIVE_04_LOCAL_CANDIDATE.zip`. The upstream repository has the exact verified multi-site source manifest and source acquisition code, but the new 19.9 KB research engine and test files have **not** yet been installed in this branch, so no new native gate has been run. The previously accepted 29-case POST-NATIVE-03 four-target source lock `9c02f020` and 44/63 native POST-NATIVE-02 scope remain unmodified. No CI run was started.

## Why we changed the target variable
The inherited UCI Beijing multisite file has hourly meteorological temperature values replicated across distinct air-quality sites: Changping/Dingling are byte-identical in the 6,144-row temperature excerpt, and Aotizhongxin/Guanyuan also share the same weather series. Repeating these as "independent temperature observations" would invalidate cross-site independence. The *pollutant* PM2.5 readings differ by station and are the declared primary multi-site target. Each of the three stations has 6,144 published hourly rows; no forecast window that overlaps an unavailable PM2.5 value is evaluated.

## Source integrity, rights and limits
- [UCI 501 Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijing+multi+site+air+quality+data), DOI https://doi.org/10.24432/C5RK5G, CC BY 4.0; original data by Song Chen and collaborators, air-quality monitoring site data.
- Official outer ZIP SHA256 `b04da438b2f331ac0ffd45aebdfec0d20d2367feb5f6948c4b1f7ce1191e33c4` (remove visual space after `dfe`); embedded 12-station ZIP SHA256 `d1b9261c54132f04c374f762f1e5e512af19f95c95fd6bfa1e8ac7e927e3b0b8`.
- Exact source manifest under `research_tests/ssm_postnative04/data/sources.json`: SHA256 `3f47ec84d49d9a169124f3c9778a87c42f10f910b334a4faf906bf76774112f3`. Each of the 18,432 derived rows was re-extracted and verified from the retained original UCI ZIP via `tools/ssm_postnative04/acquire.py --archive ORIGINAL.zip`; source member and excerpt hashes verified. Missing PM2.5 values: Changping 33, Dingling 133, Guanyuan 100; no hidden imputation, and temperature/wind forcing contains no missing values in this excerpt.
- All three stations belong to the **same UCI publisher collection and Beijing geographical system**. Independent locations, not independent publishers/weather systems, not randomized interventions. Original source byte digest proves replay identity but not an independently signed publisher attestation.
- Original independent building source UCI 374 (CC BY 4.0, Luis Candanedo) remains an additional distinct thermal domain. Its 10-minute horizons are 1,6,12 steps, while pollutant horizons are 1,6,24 hours. Do **not** pool PM2.5 concentrations with air temperatures as one prediction variable.

## Predeclared model comparisons
Fixed 60/20/20 chronological split with train/cal/test separated by complete horizon and lag history; only fully observed source/target forecast windows are retained. All prediction origins have only prior target history, calendar time, and origin-time exogenous conditions; future weather and true targets are not provided. Strong baseline alternatives: persistence, prior-day seasonal naive, train-only ridge AR24 recursive model, direct horizon-specific ridge regression, train-only diurnal relaxation, constrained wind-attenuation approximation (NOT atmospheric transport/chemistry simulation); the building adds a simplified Newtonian frozen-outdoor-temperature baseline. The full candidate additionally contains recursive authentic Cognitum SSM state coefficients, train-fitted Chebyshev KAN correction and fixed-at-origin MAP HDC/Cleanup candidate retrieval, with KAN out-of-domain fallback and HDC/ KAN ablations; **those native-only integration tests are not executed**.

Dependence-aware diagnostics: independent whole-consecutive-block calibration maxima (24 hourly PM observations or 36 building ten-minute observations), nominal 90% finite rank radius, empirical per-origin and simultaneous-block coverage, split-half drift, 256 deterministic moving-block bootstrap samples for MAE improvements, and `+3×radius` distribution-shift counterexample. Overlapping forecast origins, weather/site correlation, missing-observation selection, seasonal/nonstationary shifts and limited block count mean **no unconditional 90% coverage guarantee**.

## Actual held-out local measurements
| Site, target PM2.5 µg/m³ | Forecast horizon | Persistence RMSE | Direct ridge RMSE | Block-calibrated empirical 90% coverage of recursive ridge AR24 |
|---|---:|---:|---:|---:|
| Changping | 1 hour | 18.799 | 18.805 | 98.8% |
| Changping | 6 hours | 51.281 | 49.496 | 95.9% |
| Changping | 24 hours | 100.263 | **81.568** | **87.8%** |
| Dingling | 1 hour | 15.781 | 15.638 | 99.7% |
| Dingling | 6 hours | 47.225 | 45.445 | 95.1% |
| Dingling | 24 hours | 96.587 | **78.719** | **82.5%** |
| Guanyuan | 1 hour | 18.812 | 18.785 | 99.4% |
| Guanyuan | 6 hours | 50.820 | 51.430 | 97.6% |
| Guanyuan | 24 hours | 102.646 | **88.701** | **75.8%** |

Local model fit: 3,216 / 3,262 / 3,102 fully observed training origins and 1,126 / 1,044 / 1,038 held-out origins for Changping / Dingling / Guanyuan respectively. A forecast cannot be evaluated where required measured target values are missing: this *complete-case selection* could itself bias estimates. The displayed interval coverage is for the **recursive ridge AR24**, not for the native-unrun integrated HDC/KAN/SSM candidate.

**Independent block-bootstrap falsification of 24-hour MAE gains (direct ridge minus persistence, positive means ridge improves):** Changping 95% interval `[+2.02,+22.11]` µg/m³; Dingling `[-0.07,+18.10]`; Guanyuan `[-3.43,+16.03]`. Thus the apparent RMSE gain is not accompanied by a strictly positive empirical 95% MAE-gain interval on Dingling or Guanyuan. This is a descriptive moving-block bootstrap of overlapping origins, not a guaranteed inferential confidence interval for a geographically independent climate process.

**Reproducibility pins:** new 31-case JUnit SHA256 `5621da8bcefcbe5d088964fa3bd54531f76205aafd8cc7bf63f062838672f79d`; 54-case combined JUnit SHA256 `9b6fdac06f35787c77dfce4535fc9ecaf5fbcc484a630c24eb7af2d27d197cd9`; local result JSON SHA256 `f83aa0ee177ba76a4a4555b07e1be83fe94294b424eba6837b0dfe8ee3ab308c`. Exact local Git blob IDs: module `f704a2b94d1241252bbc4fd45e218c2c2fa0d443`, new test `c53646d7c06ecca2348f0531ddb7b91885d77ab9`, genuine native test `54c1dd874b6000f968740ef4c92680eda209ed9f`. These source/test Git blobs are **not yet published to GitHub**; preserved as exact bytes in the downloadable local candidate ZIP.

### Independent external site transfer
The **Changping-trained** direct ridge applied with no new fit to **Dingling** had PM2.5 24-hour RMSE **76.898**, compared with target persistence **96.587**. For the unseen **Guanyuan** station, 24-hour RMSE **87.129**, compared with persistence **102.646**. In contrast, its 1-hour transfer is worse than persistence at both sites (16.039 vs 15.781 on Dingling; 19.043 vs 18.812 on Guanyuan). Cross-station performance is **mixed**; do not assert universal transfer.

### Independent building domain
For UCI 374 building T1 (°C), the 12-step (2-hour) held-out direct ridge RMSE was **0.270** vs persistence **0.418**, while simplified Newtonian heat exchange had **0.417**. This is phenomenological thermal forecast benchmarking, not physical parameter discovery. Its original published source archive and source lock are unchanged from POST-NATIVE-03.

## Local qualification and blockers
- **31/31** new locally runnable source integrity, chronological leakage, missing-data, 1/6/24-step multi-site baseline, source swap, cross-site transfer, block-residual and shift-refusal tests PASS.
- **54/54** combined with 23 inherited runnable POST-NATIVE-03 observed-data tests PASS; Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0 / pytest 9.0.2, single-thread BLAS.
- New genuine Cognitum HDC/KAN/SSM integrated multi-step tests are staged in the downloadable candidate but require native full repository and remain **NOT EXECUTED**.
- Repo integration still required: install the exact tested source/test files from candidate ZIP on this branch, create same-SHA 4-target focused CI workflow with fresh original-byte acquisition, run native genuine integration/ablation and replay; reconcile all receipts. No completed new native acceptance may be inferred from the prior source locks.
- **All 72 broader scientific mathematical capabilities remain PARTIAL**, no execution authority, no permission for external actuation or autonomous scientific truth promotion.

## Current next task
**POST-NATIVE-04-R1 — Publish exact tested source and tests, complete the source-locked four-platform native HDC/KAN/SSM multi-horizon qualification, verify receipt inventories and independent UCI archive integrity, then reconcile scientific falsification and uncertainty evidence without overclaiming calibrated dependent-time-series coverage.**
