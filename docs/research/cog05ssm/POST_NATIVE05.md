# COG-05-SSM-POST-NATIVE-05 — Publisher-separated observational dynamics, dependent uncertainty, missingness and falsification

**Disposition: SOURCE-PINNED RESEARCH CANDIDATE; NOT YET NATIVE QUALIFIED.** No claim of causal physical-law identification, guaranteed conditional coverage, approved scientific truth, external execution authority, or universal HDC/KAN/SSM superiority.

## Immutable independent upstream custody

Two data-publishing government organizations, neither UCI, have been admitted to a separate source-locked research branch, preserving the original CSV file bytes (identical Git blob to the source organization). This establishes publisher separation at the Git repository level, **not** signed author/original instrument provenance.

1. **NOAA CO-OPS**: `NOAA-CO-OPS/CO-OPS-Tidal-Analysis-Datum-Calculator` at `data/test_timeseries_uneventimesampling.csv`, source blob `8421af63a839c767555a53af74b71106ee68241e`. The upstream source project's `data/info.txt` describes the data as an RA partner-station timeseries provided by Paul Fanelli, approximately four months, with intentionally uneven sampling. The exact series has 34,099 timestamped rows, April 25 to August 27, 2025; the input's second column is simply `val`, and **the physical units and original sensor QA are not independently certified**. Nine timestamps occur twice with discordant measurements (18 rows); *both* entries at each conflicting instant are quarantined, leaving 34,081 admitted observations. Time gaps and non-five-minute intervals remain present. This is partner-provided sensor data hosted by NOAA, not independently proven NOAA-operated or signed instrument measurements. NOAA repo license statement covers government software; redistribution rights for third-party partner measurements should still be clarified.
2. **DOI-USGS**: `DOI-USGS/OWDI-Lower-Colorado-Drought-Vis` at `src_data/NaturalFlow.csv`, source blob `2f986df07dce96b800829856e751b247e4179aaf`. This source contains 110 annual **natural-flow reconstructions** above Lees Ferry for 1906–2015; second Imperial column contains blank recent values and is not silently used. USGS repository has a CC0 license file. Flow units and independent documentary chain from original hydrologic derivation remain to be fully verified. This is not a raw instantaneous gage trace.

These source families differ in publishing organization, dynamics, frequency, and methodology; their observations **cannot** be pooled or reported as jointly independent random samples of one physical system. Neither is a randomized or controlled intervention.

## Preregistered comparisons and safeguards

- Fixed chronological **60% training / 20% calibration / 20% test** partitions; all lag observation timestamps and target timestamps are required to reside inside their own fold.
- NOAA predicts at **5, 30 and 120 real elapsed minutes**, not 1/6/24 array rows. Train-only baseline candidates: persistence, ridge direct lag+tidal-phase regression, train mean, and a non-causal NOAA-specific harmonic tide regression with four prescribed periods (M2 12.4206h, S2 12h, K1 23.9345h, O1 25.8193h). Known clock phase at the future target is permitted, but future measured tide height is not.
- USGS predicts **1, 3, and 5 years** ahead with train-only ridge lag regression, persistence, and train mean. The series is too short for credible high-capacity HDC/KAN identification or dependence-valid finite-rank block calibration; refusal is a scientific result, not a software test failure.
- Candidate baseline *selection* uses **calibration MAE only**; report all candidates' fixed held-out RMSE/MAE rather than choosing the test winner.
- Dependence diagnostics use only consecutive-actual-time, nonoverlapping 24-origin NOAA or 4-origin USGS blocks; require 20 calibration blocks and 10 held-out blocks, finite-rank 90% block-max radius, per-origin/simultaneous-block and split-half empirical coverage. **No unconditional, exchangeability-based or conditional 90% guarantee.** Test-only +3-radius shift is a clearly labeled *synthetic counterexample*, never a measured physical intervention.
- Missingness sensitivity separately reports complete-case, simulated periodic outages, and retrospectively censored upper-tail outcomes; the latter deliberately uses held-out outcomes **only as a missingness-stress diagnostic**, never as a predictor.
- Byte corruption/source swap must refuse. Repeated timestamp conflicts are quarantined rather than merged, guessed or silently repaired.

## Direct falsification of existing HDC/KAN/SSM hypotheses — required scientific distinction

The inherited Cognitum fixed-step HDC/KAN/SSM comparison requires a uniform-rate, sufficiently long observed trajectory with valid step semantics. NOAA's actual uneven timestamps and conflicting duplicates cannot be treated as uniform frames. USGS's 110 reconstructed annual values cannot support high-capacity KAN/HDC training and the required dependent-calibration block count. This stage therefore **refuses unsupported HDC/KAN/SSM performance comparisons on these two sources**, instead of resampling without disclosure or comparing incommensurable time steps. It is a direct *applicability/precondition falsification*, **not** completed out-of-domain model superiority/performance falsification.

To close the full task, add an independently traceable long, regular *measured* system from a new data publisher, or qualify a genuinely time-aware `Δt` native SSM/KAN/HDC path on uneven observations, including train-only fit, genuine ablations, stronger source-specific baselines, preregistered superiority criteria and same-source Windows/Linux native receipts. If confidence intervals cover zero or performance regresses, preserve the negative result; do not promote an unqualified hypothesis.

## Source and scope

- New module: `cognitum/research/ssm_independent_publishers.py`
- New tests: `research_tests/ssm_postnative05/test_publishers.py`
- Frozen data: `research_tests/ssm_postnative05/data/`
- Previous closed acceptance remains `POST_NATIVE04_R1.md` at `6160e322ba24f8ec4d8f4a7d90ad885daeb32c92`; original POST-NATIVE-03/02 source locks remain untouched.
- All **72** comprehensive mathematical capability groups remain **PARTIAL**, not promoted. No Lu, Maj Vaj, autonomous hardware, or external tool permissions changed.

### Acceptance status
Native Windows/Linux four-platform POST-NATIVE-05 acceptance is not asserted until terminal workflow conclusions and downloaded source-pinned JUnit/log receipt integrity have been checked. Do not equate research-only baseline passing with full task closure.
