# COG-05-SSM-POST-NATIVE-05-R4 — Genuine elapsed-time HDC/KAN/SSM and physical-system OOD falsification

**Status: BOUNDED FOUR-PLATFORM NATIVE PASS FOR TRUE ELAPSED-TIME SCIENTIFIC BENCHMARKING; FALSIFICATION AND REPRODUCIBILITY LIMITS PRESERVED.** The original POST-NATIVE-05-R3 exact 4-target accepted SHA `127672af94fb126163efd51057dfd5adf0f9bb4e`, 15 tests/target, is unchanged. This R4 source is an independent branch. The full scientific scope is not considered complete by writing code or seeing one successful platform.

## Independent observational custody

- Previously source-locked **NOAA-CO-OPS partner water-level irregular series**: 34,099 original records, 18 conflicting rows excluded, 34,081 admitted. This is hosted by NOAA but supplied by a partner; upstream physical unit and signed instrument provenance remain unverified.
- **DOI-USGS/loadflexBatch Raccoon River at Des Moines, Iowa**: 3,653 consecutive daily discharge observations from Oct 1998–Sep 2008, original publisher-hosted `Hirsch_sites/input/Q/Rac.csv` Git blob `0277bb41d84dc49d85b9a016fbfbce4f4ac59ed7`.
- **DOI-USGS/loadflexBatch Muskingum River at McConnelsville, Ohio**: 3,652 consecutive daily discharge observations from Oct 2001–Sep 2011, original publisher-hosted `Hirsch_sites/input/Q/Musk.csv` blob `964a615050252f4a05ebca9d69caffed847444d1`.
- Official DOI-USGS example metadata `Hirsch_sites/input/siteInfo.csv` blob `174a59d509ceb3a56d6b7c44f38cb687ed24648d` labels both as **Discharge, cubic meters per second (cms)** and supplies names/locations. The official repo includes CC0/public-domain LICENSE.md; its `EGRETtoANA.R` shows these examples were **converted from EGRET eList research objects**, not freshly downloaded or independently signed raw stream-gage archives. No claim of cryptographic original sensor attestation or independent validation of upstream sensor QA.
- These are two independent geographic river processes from **one** USGS publishing source, contrasted with the separate NOAA partner-record source. No station is mislabeled an independent publisher.

## Registered model and scientific controls

1. **True continuous-time SSM**: a stable scalar residual latent dynamic `dz/dt=−z/τ` relative to an observed-data-fitted seasonal or tidal harmonic, discretized with exact `A(Δt)=exp(−Δt/τ)` for the actual elapsed forecast seconds (not row indices). Independent SciPy matrix-exponential witness checks the scalar transition. Harmonic coefficients and a finite grid of stable decay times are selected using **training observations only**. The seasonal mean and astronomical tidal harmonic are *phenomenological* and do not constitute a discovered conservation law, proven hydrodynamic transport equation, or independently inferred force term.
2. **Real Cognitum KAN**: `kan_trainable.Network(Layer('chebyshev',...)).fit_linear()` trained on at most 1,536 *training* one-step SSM residuals; checkpoint hash preserved. Out-of-training input ranges explicitly abstain.
3. **Real Cognitum HDC**: `hdc_algebra.Spec('MAP',256)` binding/bundling and `hdc_associative.Cleanup` trained on KAN-adjusted training residuals, with two empirical prototypes and margin/threshold abstention. Both components are queried only on forecast-origin observations; future measured targets are never inputs. Learned residual correction is clipped and scaled conservatively; this is **empirical**, not physical-causal extrapolation.
4. **All outcomes on the same held-out origins**: persistence, seasonal/tidal harmonic, train-only lagged direct ridge, time-aware SSM, HDC+KAN+SSM, SSM+KAN without HDC and SSM+HDC without KAN. Source-specific horizons NOAA 5/30/120 **minutes**, USGS 1/3/7/30 **days**. Models are fitted only on the first 60%; baseline is selected on 20% calibration **without test cherry-picking**; final 20% is untouched until reported. Test-set performance differences and uncertainty failures are never re-trained away.
5. **Falsification**: matched-error nonoverlapping genuinely consecutive-time block bootstrap for MAE improvements relative to calibration-selected strongest baseline; 90% block-max intervals with empirical origin, simultaneous block, split-half drift and `+3×radius` *synthetic* counterexample; missing sensor records simulated in held-out gaps and top-decile outcome-dependent censoring reported retrospectively with **no imputation**. No unconditional 90% coverage or source independence claim.
6. **Out-of-domain**: differing NOAA tidal/irregular and USGS hydrologic/daily domains, train-only target-site fitting; independence is **between scientific physical systems/publishers, not an unsupported one-model zero-shot success claim**. USGS Raccoon↔Muskingum zero-shot transfer and independently signed upstream raw observations remain separately required for any assertion of universal transfer.
7. **Safety and scientific authority**: zero Lu/Maj Vaj changes, no user data access or execution/actuation authority, no discovered physical laws, and all 72 comprehensive research mathematical capability groups remain **PARTIAL**.

## Exact acceptance

`cognitum/research/ssm_timeaware.py`; `research_tests/ssm_postnative05r4/test_timeaware.py`; immutable originals and nested Windows no-EOL-change contract under `research_tests/ssm_postnative05r4/data/`; `tools/ssm_postnative05r4/acceptance.py`. Required four-target Windows/Linux Python 3.11/3.13 fixed-SHA native gate with 25 genuinely executed test identities and archived JUnit/test logs/source and science/receipt SHA256. Preserve the **new** six source blob pins and every inherited P05/P04/P03 original source pin. A workflow start or test merely passing Python syntax is **not** task closure.

## Research limits requiring explicit negative conclusions

- NOAA partner measurement unit, original sensor documentation, and signed custody unresolved.
- USGS-derived EGRET source is published by USGS and documented in cms, but upstream raw instrument record and reproduction rights for instrument-origin proofs not independently attested.
- Exact exponential ZOH and KAN/HDC tools demonstrate valid *algorithmic integration*, not a correct river/tide physical causal law.
- Dependent-block calibration is descriptive and can miss strong drift or regime shift; bootstrap gains are not physical confidence guarantees.
- If native hybrid underperforms calibrated baselines, retain and report it as **falsification** rather than retune on held-out outcomes.


## R4 final bounded native qualification (2026-11-20)

[Run 44848932899](https://github.com/vjmichael/cognitum/actions/runs/44848932899) completed **SUCCESS** on a single unchanged source SHA `cf78900c4fcec3981b93c842144c53b15cc0d411`; four Ubuntu/Windows Python 3.11/3.13 targets, **25/25 genuine test cases each**, zero failures/errors/skips. This is **100 executions of 25 distinct scoped source tests**, not 100 independent scientific datasets or inferred laws. [Four independently downloaded artifact SHA-256 receipts](POST_NATIVE05_R4_NATIVE_ARTIFACTS.json) preserve verified JUnit/log/science/receipt integrity and 27 unchanged source/test/data Git blob pins (6 R4, 5 inherited R3, 10 inherited P04, 6 inherited P03). All four native JUnit identities match; all three observed datasets' heldout MAE/RMSE agree across targets with absolute difference at most **5.69×10⁻¹⁴**. The Windows data bytes are identical to their DOI-USGS publisher-hosted blob IDs.

**Critical cross-platform limitation:** KAN research checkpoint SHA-256 digests **differ** across Linux/Windows, despite numerical forecast agreement to tolerance. Never claim bit-for-bit KAN parameter checkpoint identity or proven serialized checkpoint interchange; cross-platform canonical checkpoint replay remains open.

### Predeclared held-out scientific falsification

All USGS discharge RMSE below is cubic meters/second (cms), source-traced EGRET-derived daily research data; NOAA water-level values remain in **unverified partner source units**. Hybrid is genuine train-fitted continuous-time SSM with native KAN/HDC residual prototypes, not prompt inference. Baselines use exactly the same held-out origin timestamps, and the strongest comparator for bootstrap is selected only on calibration MAE.

| Source / target | Elapsed horizon | HDC+KAN+SSM RMSE | Direct ridge RMSE | Diagnostic nominal-90% hybrid origin coverage |
|---|---:|---:|---:|---:|
| Raccoon River Q (cms) | 1 day | 53.8334 | **51.4305** | 92.53% |
| Raccoon River Q (cms) | 7 days | 152.0045 | **139.5542** | **85.63%** |
| Raccoon River Q (cms) | 30 days | 181.3872 | **164.1432** | **81.84%** |
| Muskingum River Q (cms) | 1 day | 49.3442 | **45.5123** | 99.59% |
| Muskingum River Q (cms) | 7 days | 159.4129 | **155.7376** | 98.33% |
| NOAA partner water level | 5 minutes | 0.0099 | **0.0088** | 99.53% |
| NOAA partner water level | 30 minutes | 0.0366 | **0.0335** | 97.77% |
| NOAA partner water level | 120 minutes | **0.1173** | 0.1599 | **89.08%** |

**Paired dependence-aware falsification (descriptive, not guaranteed inference):**
- At Muskingum 1 day, the bootstrap 95% interval for hybrid MAE improvement over **calibration-selected direct ridge** is **[−4.2141, −0.3511] cms**. This is a measured negative result and does not establish hybrid advantage.
- At NOAA 5 minutes, corresponding hybrid MAE gain vs calibration-selected direct ridge is **[−0.00104, −0.00069]** in unverified units: again, negative.
- At NOAA 120 minutes, corresponding gain vs calibration-selected direct ridge is **[+0.03446, +0.05986]**, but hybrid nominal 90% interval has only **89.08% origin** and **69.57% simultaneous 24-origin block** coverage, and first/second-half coverage differs (91.41% vs 86.76%). This is evidence of improvement on this held-out regime, **not transfer-proof or coverage certification**.
- At Raccoon 7/30 days, intervals show gains vs the *calibration-selected persistence or SSM controls*, but direct ridge still has smaller RMSE. Do **not** relabel bootstrap comparison as against the strongest post hoc test-set method. Raccoon long-horizon 85.63/81.84% nominal-90% empirical coverage is an explicit calibration failure.

**Missingness sensitivity:** Synthetic held-out sensor outages retain about 84–92% of eligible forecast origins depending on source/horizon, with no hidden interpolation, and change measured RMSE. Retrospective upper-decile target censoring uses held-out targets only for scientific sensitivity diagnostics, never fitting or prediction. Dependence-aware block quantiles do not guarantee conditional time-series coverage under changing hydrology, tides, missingness or nonstationarity.

### Acceptance and residual scientific limitations

**Engineering R4 scoped native task: PASS**, completing genuine `Δt` scientific model integration, source-backed independently documented physical observational domains, native KAN/HDC ablation execution, matched heldout strong statistical and phenomenological scientific baselines, explicit missing-observation sensitivity, block-bootstrap and interval-shift falsification on four native environments.

**Not established:** independent cryptographically signed original instrument data or NOAA partner units; true parameterized river conservation/transport equations; universal across-site or cross-publisher zero-shot model superiority; conditionally valid dependent 90% uncertainty; identical portable KAN checkpoint bytes across operating systems; physical workstation qualification; autonomous law discovery; external actuation rights. No Lu/Maj Vaj production modifications. **All 72 mathematical capability groups remain PARTIAL**.

**Next bounded independent task: COG-05-SSM-POST-NATIVE-05-R4-R1 — Resolve KAN checkpoint determinism/replay, independently attest original sensor metadata and data reuse terms, perform untouched-site zero-shot forecasts with actual source-independent physical process comparators and dependence-valid drift/missingness uncertainty checks.** Keep negative numerical findings intact and require same-source multi-OS acceptance.
