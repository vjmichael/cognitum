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

## Actual unchanged-source R4 experiment: scientific falsification accepted

**Scoped native and scientific acceptance: PASS** on exact original candidate `11ed7697defd2a6df1c75360ddf2e7aca6a890ae`, [GitHub native run 44873223743](https://github.com/vjmichael/cognitum/actions/runs/44873223743). Four original Windows/Linux Python 3.11/3.13 JUnit archives each contain **95 inherited/source/pretest and 9 postscore independent replay cases (104/104)**; total **416/416**, zero failure/error/skip. All four original ZIPs independently downloaded and CRC/SHA-256 verified, identical JUnit inventories, exact original source SHA, six original canonical Git source object pins, and independently recomputed every original heldout row/MAE/RMSE, each signed gain, all nine cohort clocks and default/expanded method decisions. Source-locked native archive identities are recorded in [native R4 artifact manifest](ORCH01E_BENCH02_R4_NATIVE_ARTIFACTS.json). The standalone independent verification artifact is retained as original output; this report does not claim a performance result not supported by that data.

The first attempt [44873151118](https://github.com/vjmichael/cognitum/actions/runs/44873151118) failed before any scoring because importing Cognitum's original `SelectionPolicy` pulled in the cooperative protobuf dependency not installed in the isolated acceptance environment. A **dependency-only correction** pinned `protobuf==6.33.1` to the native workflow, without changing preregistration or benchmark behavior; the next exact SHA ran to completion. The failed original run is preserved, not silently overwritten.

### Every matched original retrospective heldout task

All error figures are **RMSE in kelvin**. Signed gain is `ridge RMSE − selected RMSE`; negative means worse than ridge. Both selector choices are frozen from calibration *before* heldout scoring. N is identical for every method in that task. All missing/ambiguous-hour R3 refusals remain unchanged.

| Frozen site/horizon | Heldout N | Direct ridge | Orc default: selected | Orc default RMSE | Signed default gain | Orc expanded classical: selected | Expanded RMSE |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: |
| KSEA 1h | 21 | 1.0567 | persistence | 1.0036 | +0.0531 | persistence | 1.0036 |
| KSEA 3h | 19 | 2.0848 | persistence | 1.9317 | +0.1531 | ridge_AR24 | 2.0099 |
| KSEA 6h | 17 | 3.4771 | direct_ridge | 3.4771 | 0.0000 | ridge_AR24 | 3.3577 |
| KDEN 1h | 37 | 2.4282 | persistence | 2.7000 | −0.2718 | persistence | 2.7000 |
| KDEN 3h | 35 | 4.3859 | timeaware_ssm | 5.5868 | −1.2008 | timeaware_ssm | 5.5868 |
| KDEN 6h | 32 | 5.4399 | persistence | 7.9716 | −2.5318 | persistence | 7.9716 |
| KATL 1h | 37 | 1.0677 | direct_ridge | 1.0677 | 0.0000 | direct_ridge | 1.0677 |
| KATL 3h | 35 | 3.5984 | direct_ridge | 3.5984 | 0.0000 | direct_ridge | 3.5984 |
| KATL 6h | 32 | 9.1915 | persistence | 4.2507 | +4.9408 | lag24_persistence | 4.9703 |

### Exact prespecified dimensionless macro and all negative outcomes

| Fixed comparator versus direct ridge | Wins | Losses | Ties | Mean relative RMSE gain |
| --- | ---: | ---: | ---: | ---: |
| Persistence | 5 | 4 | 0 | +0.9188% |
| Ridge_AR24 (fixed five-lag) | 5 | 4 | 0 | −20.0082% |
| Lag24 persistence | 1 | 8 | 0 | −81.6098% |
| Train mean | 2 | 7 | 0 | −177.2008% |
| Time-aware mean-reverting SSM | 6 | 3 | 0 | −1.0031% |
| Orc default selection-policy R3 adapter | 3 | 3 | 3 | **−2.1103%** |
| Orc expanded-classical R3 adapter | 4 | 3 | 2 | **−3.0153%** |

All nine original site/horizon tasks are included, regardless of whether the method is selected or performs poorly. The original 265 heldout target rows are compared to exactly 265 predictions for each of the eight fixed method/selector outputs. The signed gain macro gives each of the nine tasks equal weight and does **not** pool raw kelvin RMSE across unequal station conditions.

**Result:** This particular R3-bound Orc calibration-policy adapter did not outperform direct ridge on the nine-task macro. A five-lag AR24 ridge can improve some cases, but suffered substantial losses, so the negative mean is scientifically important. The default Orc adapter's apparent KATL 6h gain is offset by three KDEN losses; no general selection advantage follows. The relative win/loss counts, calibration decision status, individual missing-reason counters and per-origin predictions are preserved in the original native evidence; nothing was tuned to rescue the macro after seeing results.

**Dependence and inference:** The original cohort design uses overlapping horizons and a limited number of heldout origins per site (17–37). Pairwise six-hour contiguous block sensitivity uses fixed 256 bootstrap draws and refuses an interval below four uninterrupted nonoverlapping blocks. KSEA has only 2–3 such blocks for its three horizons and is explicitly refused. No multiple-comparison-adjusted significance, conditional 90/95% confidence, or population-wide accuracy guarantee is claimed.

**Critical scope boundary:** This is a real weather observation test and a faithful original `SelectionPolicy` baseline threshold adapter to frozen R3 folds; it is **not a direct invocation of the entire Orc Graph `propose_forecast` path, native HDC/KAN engines, production MEL, or long-term trusted publication-time custody**. Both Orc variants are described exactly, including the expanded-classical inventory that is not original `allow_research_proposals` HDC/KAN. The R3 first-capture-bounded eligible cohort remains **zero across all nine heldout tasks**. Historical AWC `receiptTime` is self-reported and not independently attested as first public availability, therefore no operational causal forecasting or live superiority claim is justified.

**Closeout:** **BENCH-02-R4 scoped retrospective baseline/selector falsification PASS; full native Orc HDC/KAN scientific comparison, prospective first-seen eligibility and protected installed MEL source custody remain separately OPEN.** Next **BENCH-02-R5** independently consolidate native and science receipts, check cross-platform reproducibility with the frozen original sources and quantify non-generalization limits. **COG-ORCH-FIN-01** installed authorization and separate prospective source collection remain open.
