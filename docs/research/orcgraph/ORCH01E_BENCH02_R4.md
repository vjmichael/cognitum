# COG-ORCH-01E-BENCH-02-R4 — matched real-site ridge, SSM and Orc selection-adapter

**State: benchmark source candidate; no scores accepted until unchanged-source four-platform native execution and original prediction replay.** The frozen scientific method recipe was committed *before any R4 heldout scoring* at [R4 original preregistration](ORCH01E_BENCH02_R4_PREREG.json) (commit `2cb66358c0a5d53453f5f7fdf792fc57b25bd018`, original canonical Git blob `1cf7c2ae11e09130ef036f3812ebfb849235f26b`). The already independently qualified original R3 source archive and R3 cohort are unchanged.

## Original-source and cohort identity

Three independent, *previously selected* NOAA/NWS Aviation Weather Center airport series: **KSEA, KDEN and KATL**. Original 762 METAR report rows, 192 frozen hourly bins/site, 115/38/39 train/calibration/test hours, 1/3/6h forecast horizons, original report times and missing/revised-hour exclusions remain fixed and source pinned. All nine site/horizon tasks must report, including poor-performing and abstaining cases; all algorithms must score exactly the same R3 eligible origin and target clock pairs. Five available source-history lags: 0,1,3,6,24h. No imputation, silent sample intersection or future-feature backfill.

The benchmark replays each original byte-pinned R3 NOAA snapshot and cohort SHA-256 and checks the original Git-archived receipt. It rejects a changed source, changed cohort, altered clock, wrong preregistration, missing row or post-hoc policy. The **first-capture-bounded test eligibility remains zero for all nine tasks**; the historical AWC receipt-based proxy can support a retrospective comparison but does NOT independently attest that the observations were public at the respective forecast origins. No live NOAA queries are permitted in R4.

## Methods fixed before evaluating data

- **Direct ridge:** original lag 0 and 1 features, train-only standardization, unpenalized intercept and fixed L2 alpha=1.0.
- **Ridge_AR24:** all five preregistered 0,1,3,6,24h lags, same train-only standardization/alpha; not a new 25-lag feature search.
- **Persistence and lag24 persistence:** respectively predict the origin or exactly 24h-ago temperature.
- **Train mean:** fixed train-fold target mean, all targets within the training fold only.
- **Time-aware SSM:** stable mean-reverting exponential generator, train-only mean, tau candidates 1/4/16/64 hours, choose tau by train-fold MAE and frozen order, then use physical elapsed horizon.
- **Orc default:** use the *actual* `cognitum.orc_selection.SelectionPolicy` thresholds, default eligible method order direct ridge/persistence/train mean/time-aware SSM, and identical original gain and tie rules. A source-locked **R3-fold adapter** is necessary because the original `propose_forecast` assumes its own separate 60/20/20 source split. The adapter is **not** a direct run of `propose_forecast` and no native HDC/KAN specialist is invoked.
- **Orc expanded classical:** same calibration-only selector, adds fixed lag24 persistence and ridge_AR24. This is a **new R3-specific classical expansion, not** the original research HDC/KAN opt-in policy. Avoid attributing any expanded result to actual KAN/HDC.

Selection is entirely based on original calibration MAE with minimum 20 calibration cases, at most 25% omitted nominal calibration candidates, absolute gain >=0.01K and relative gain >=1% compared with direct ridge; ties use candidate MAE, fixed work proxy and candidate order. All expected strongly classical comparators are independently scored even if the Orc default candidate inventory excludes them. No selected method can be chosen after reading heldout errors.

## Two-phase, source-locked falsification

`tools/orcbench02/benchmark_r4.py` first emits `bench02-r4-decisions.json` with all nine calibration-only decisions, precise source/cohort identities and no test scores, then rechecks it byte-for-byte before a separate scoring phase writes `bench02-r4-results.json`. These contain exact original per-origin, per-target forecasts for independent reconstruction. Native acceptance uses Python 3.11/3.13 on Windows/Linux, pinned numpy/scipy/pytest, unchanged R1/R2/R3 refusal and R4 pretest tests, frozen decision file, heldout score file, independent numerical tests, actual native Git source blobs and original JUnit archives.

MAE and RMSE are in Kelvin. Report direct ridge, AR24, both persistence baselines, train mean, time-aware SSM, Orc default adapter and expanded-classical adapter, including per-task negative gains and ties. Across all nine tasks the primary aggregate is mean of each task's fractional RMSE gain relative to direct ridge (not an unfair pooling across series). Paired 6-hour contiguous-origin block resampling (256 fixed-seed samples) is **descriptive only**; refuse uncertainty intervals without at least four nonoverlapping blocks. Report calibration sample size, all original holdout denominators, OOD/abstention and block counts. No model fitting or testing may modify the previous R3/bench01 conclusions.

## Explicit scientific scope hold

R4 tests a frozen, source-bound **Orc baseline selection-policy adapter** against ridge/AR24/persistence/SSM, not an end-to-end original Orc Graph scheduler/authorization/SSM+KAN+HDC engine comparison. An actual full Orc Graph/HDC/KAN experiment on *exact* R3 folds requires a separately source-locked adapter with the original accepted specialist engines, matched calibration, and additional qualification. No claim of production, real-time as-of access, improved CPU/power efficiency, independent publication time, causally generalizable skill, or human–AI collaboration follows even if retrospective RMSE improves.

**Next:** verify the single exact-source native run, independently check four JUnit ZIP archives, test cohorts, original prediction rows and signed gains, publish unedited losses, then decide whether R4's bounded baseline-adapter qualification passes. Independent full-specialist integration and true prospective first-seen design remain future work alongside R5/FIN-01.
