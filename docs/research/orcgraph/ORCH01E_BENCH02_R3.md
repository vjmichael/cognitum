# COG-ORCH-01E-BENCH-02-R3 — preregistered independent observational cohorts

**State: source candidate; local 47/47 R1+R3 tests passed (including the original archived R2 source control). Not four-platform accepted, and no new KSEA/KDEN/KATL original source has been acquired.** The accepted BENCH-01 and BENCH-02-R2 source/result are unchanged.

## Immutable independent site selection before results

The selected new physical observation locations are **KSEA (Seattle), KDEN (Denver), KATL (Atlanta)** in that exact order, distinct from the already inspected KMCI source-contract demonstration. No convenient site replacement, score-dependent window movement or additional site after heldout evaluation. The original [JSON preregistration](ORCH01E_BENCH02_R3_PREREG.json) is SHA-256 **fd0b6a372ee5cd9ee8870ad20c475261460a069daf4fd52f56e8dcc2961a5104**, frozen first in independent source commit **2dcd67df515e65d9da0cccb5c3e6b08736716573**. If scientifically necessary later, a preregistered successor must preserve this original contract and any negative outcomes rather than modifying the old protocol.

Source: NOAA/NWS Aviation Weather Center official METAR JSON per fixed station, query ids=ICAO&format=json&hours=240. Refuse any response with **400 or more rows** as potentially truncated by the API; source must fit under **2,000,000 original bytes**. Keep original byte SHA, complete source-order reports, site identity, observation clocks and reported AWC receipt clocks. NOAA AWC is not a directly signed original weather instrument.

## Fixed hourly window and temporal folds

Anchor at **first acquisition start**, not a favorable data outcome: exclusive study end = floor(capture_start_UTC_hour) minus two hours. Exactly **192 complete UTC hourly bins** precede that end. Indices 0–114: **train 115 hours**; indices 115–152: **calibration 38 hours**; indices 153–191: **heldout test 39 hours**. Three prediction horizons: **1, 3 and 6 elapsed hours**. Five lag features: **0, 1, 3, 6 and 24 hours**; forecast origin at end of the current hourly bin. A target must remain inside its origin's fold. Insufficient 24-hour input history is counted, not imputed. All **3 sites × 3 horizons = 9 cases** stay reported even with zero eligible samples.

Each original METAR observation maps to floor-UTC-hour; finite Celsius temperature converts by adding **273.15** to Kelvin. Missing hour, null temperature and any duplicate/correction/SPECI with more than one report in the same hour each cause explicit ineligibility and counters; retain all originals rather than choosing a favorable version. Late receipt, future first-capture, target beyond fold and target/feature missingness also have explicit refusal counters. No silent intersection to successful models.

## Two separate availability profiles, no retroactive promotion

**Descriptive retrospective proxy:** for every lag feature, original observation time and AWC-reported receiptTime must be at/before forecast origin. This is NOT independently attested public availability. **First-capture-bounded as-of:** additionally require the actual first-seen capture time at/before the origin. A historical snapshot newly downloaded in 2026 cannot be used to pretend the observer already knew it hours or days earlier. Consequently a historical batch can legitimately yield **zero strict as-of origins**; do not weaken gates to create positive metrics. Even captured-first-seen is a host report, not an independent protected signed timestamp or MEL authorization.

R3 emits per-site fixed window and fold denominators, detailed reasons, exact origin/target UTC clock pairs and hashes, source and frozen protocol identifiers. It emits **no numeric heldout targets, models, predictions, RMSE/MAE or rankings**. R4 must freeze model parameters and measure matched original cohort IDs, including losses.

## Qualification and remaining work

Implementation: tools/orcbench02/cohorts.py. New tests: tests/test_orc_bench02_cohorts.py. Local pytest with the original R2 archived data and inherited R1 availability tests passed **47/47** (19 inherited R1 local tests, 28 new R3 tests, zero skip/error/failure). Previous R2 native acquisition tests and full four-platform R3 have not been rerun in this task. The new workflow is **manual-dispatch only** while old queued R2 run #44868881226 is unresolved: no CI stacking or new model experiment.

**Next R3 closeout:** reconcile the obsolete queued run, execute a single unchanged-SHA four-platform R1/R2/R3 native cohort, independently inspect ZIP/CRC/JUnit/protocol/original Git SHA and acquire fixed real KSEA/KDEN/KATL site observations under the locked protocol. **Then BENCH-02-R4:** matched direct ridge, ridge-AR24, persistence, SSM and frozen Orc proposals with negative results, dependence-aware uncertainty and explicitly separated retrospective vs strict-causal eligibility. **R5:** scientific and native source closeout. **FIN-01:** protected installed MEL authorization, independent time/custody, OS resource limits and user–AI cooperation study remain open.
