# COG-05-SSM-POST-NATIVE-05-R4 — Genuine elapsed-time HDC/KAN/SSM and physical-system OOD falsification

**Status: SOURCE-PINNED RESEARCH CANDIDATE, NATIVE QUALIFICATION PENDING.** The original POST-NATIVE-05-R3 exact 4-target accepted SHA `127672af94fb126163efd51057dfd5adf0f9bb4e`, 15 tests/target, is unchanged. This R4 source is an independent branch. The full scientific scope is not considered complete by writing code or seeing one successful platform.

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
