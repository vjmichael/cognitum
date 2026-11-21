# Orc Graph versus ridge — owner-requested post-completion benchmark

**Owner decision (November 20, 2026):** After completing the Orc Graph architecture (ORCH-01B–E), undertake a real independent comparison to measure whether routing actually helps Cognitum over **direct ridge regression**, not merely whether its graph executes. **Status: NEXT SCIENTIFIC EXPERIMENT / NOT EXECUTED.**

## Pre-registered question and distinct effects

1. **Data-pipeline contribution:** same ridge algorithm fitted from old R4 features versus the same ridge algorithm fitted from Orc Graph's new strictly qualified observations/features; identify the effect of data quality/feature construction, not falsely attribute it to learned methods.
2. **Routing contribution:** static ridge against Orc-selected eligible method, selected ONLY on the calibration fold, at matched forecast origins and horizon, with identical permitted covariate availability and compute-budget reporting.
3. **Optional multi-engine contribution:** ridge, standalone appropriately trained SSM, KAN, HDC-as-regime/auxiliary, SSM+KAN/HDC hybrid, and strong mechanistic or statistical forecasting baselines (e.g. seasonal persistence or established domain process model) wherever legitimately eligible. No post-hoc use of held-out test scores to choose routes.

## Required science gates

- Lock dataset bytes and licenses, units and provenance, site identity, timestamps and publication/availability times, model/version/source and raw-source hashes BEFORE testing. Reuse R4 NOAA/Raccoon/Muskingum as historical references only; add independently sourced untouched-site physical observations and validate instrument provenance and rights where achievable.
- Preserve matched 60/20/20 temporal train/cal/test, independently source-held-out targets and rolling as-of features. Training-only transforms, calibration-only model/feature/pipeline selection, test strictly untouched; do not quietly intersect cohorts or restrict to successful forecast periods. Document missing/late/censored cases and their bias.
- Primary metrics: held-out RMSE and MAE against direct ridge per domain and horizon; secondary 90%-nominal per-origin/temporally dependent simultaneous coverage, drift segmentation, stability to missingness, wall-clock latency, CPU/memory and abstention/refusal rates. Interpret intervals cautiously; use dependence-aware paired uncertainty/counterevidence and report negatives.
- Separate **Orc-selected ridge** (equal ridge accuracy, possibly extra execution overhead) from genuinely improved forecasts. System-level benefit can be a lower loss/compute-cost balance, better robustness, safer refusal or correct exact routing, but is NOT automatically an accuracy improvement.
- Make method eligibility (exact deterministic vs learned statistical), source and calibration evidence independently reviewable. Publish source-locked four-platform receipts and actual observed predictions and baselines; do not claim physical-law discovery or universally superior hybrid methods.

## Acceptance outcome

Only claim Orc Graph improves **heldout predictive accuracy over ridge** when a credible matched independent comparison supports it, including drift and dataset limitations. If it does not, report that result, preserve negative outcomes and keep ridge as the selected method where it is best. Orc Graph is not required to win every task. This experiment belongs to **COG-ORCH-01E-BENCH-01**, with ORCH-01D creating the matched-evaluation machinery. No benchmark is run or approved by recording this plan.

## Post-ORCH-01E independent benchmark readiness

The five bounded Orc Graph architecture stages passed source-locked native tests, most recently https://github.com/vjmichael/cognitum/actions/runs/44863332744. This is NOT the independent scientific result: its two synthetic selected methods were persistence and the data were generated. BENCH-01 must source and lock real independently observed datasets with original publisher/licensing/unit evidence, preserve as-of observations and honest missingness, select only on calibration, compare frozen direct ridge, physical/statistical baselines and Orc-selected eligible methods on identical untouched observations and report negatives and dependence-aware uncertainty with actual compute budgets. Original KAN bitwise snapshot differences remain unresolved.


## BENCH-01 locked real observation study

The specific site/feature/cohort/baseline/metric contract is recorded [before any test outcome](ORCH01E_BENCH01_PREREG.md). This new study uses already archived real UCI air-temperature data for three sites with explicit CC BY 4.0 attribution. It is not an unseen-source or original-sensor-attested experiment. Any failures or losses must be preserved in result tables, with no future-label selection.
