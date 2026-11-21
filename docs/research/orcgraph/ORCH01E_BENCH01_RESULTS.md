# BENCH-01 — Actual real-observation Orc Graph vs direct ridge results

**Status: BOUNDED HISTORICAL OBSERVATIONAL COMPARISON QUALIFIED; NO CONSISTENT RIDGE SUPERIORITY ESTABLISHED.** This is a real, already archived historical-source comparison, not fully new/untouched independent publishers, original signed sensors, operationally attested availability, or a CH⊕aT user study.

**Prerequisite source protocol:** [Pre-result registration and transparent failed preflight amendment](ORCH01E_BENCH01_PREREG.md). Three nonduplicate physical observation series: hourly UCI Beijing Changping temperature converted °C→K (Song Chen, UCI 501, CC BY 4.0), and two originally Git-blob-pinned USGS EGRET-derived daily discharge rivers: Raccoon and Muskingum (m³/s). For each, first 1,920 historical observations, exact 60% train, 20% calibration, 20% heldout test, forecast 1/6/24 natural sampling intervals, original 01B as-of cohort and identical heldout origins. Historical publication availability and weather timezone are declared assumptions. Original source hashes and units reverified, no interpolation or silent matching.

## Source-locked native acceptance

[GitHub Actions run 44865667216](https://github.com/vjmichael/cognitum/actions/runs/44865667216) completed **SUCCESS** at unchanged SHA `8d0b1d2d8d05b7496ec159b241e3f8c7fac3dba9`. Ubuntu/Windows Python 3.11/3.13: **436/436 tests each, 1,744 native case executions, zero failure/error/skip**. All four original ZIP archives independently downloaded and verified SHA-256 and CRC. Their JUnit test inventories are identical, all 42 canonical source Git object identities match the authoritative original commit, and all 9 real heldout target/prediction tables have independently recomputed MAE, RMSE, signed ridge gains and already-frozen method identities. See [four-archive scientific manifest](ORCH01E_BENCH01_NATIVE_ARTIFACTS.json) for exact digests. Original ORCH-01A–E, MEL and R4 accepted algorithms were not altered.

## Actual matched heldout forecast RMSE

RMSE is in each row's stated native unit. **Signed gain = direct Ridge RMSE minus selected method RMSE. Negative is worse than Ridge.** Entries reflect Ubuntu Python 3.11; all four native platforms agree within small floating-point tolerance.

| Fixed series/horizon | Heldout origins | Direct ridge RMSE | Default Orc choice | Default signed gain | Research-opt-in choice | Research signed gain | Calibration-selected strong classical comparator |
| --- | ---: | ---: | --- | ---: | --- | ---: | --- |
| Changping 1h (K) | 383 | 1.2893 | direct_ridge | 0.0000 | direct_ridge | 0.0000 | ridge_AR24 (0.9769) |
| Changping 6h (K) | 378 | 9.2891 | persistence | +3.2585 | persistence | +3.2585 | ridge_AR24 (3.7789) |
| Changping 24h (K) | 360 | 4.9698 | persistence | +1.6789 | persistence | +1.6789 | persistence (3.2909) |
| Raccoon 1d (m³/s) | 383 | 21.7241 | persistence | -1.6167 | ssm_hdc | -1.4768 | persistence (23.3409) |
| Raccoon 6d (m³/s) | 378 | 69.2142 | persistence | -6.0901 | ssm_hdc | -4.0684 | persistence (75.3043) |
| Raccoon 24d (m³/s) | 360 | 97.8021 | timeaware_ssm | -6.7743 | ssm_kan_hdc | +2.4658 | timeaware_ssm (104.5764) |
| Muskingum 1d (m³/s) | 383 | 48.7885 | direct_ridge | 0.0000 | direct_ridge | 0.0000 | ridge_AR24 (49.1083) |
| Muskingum 6d (m³/s) | 378 | 164.6360 | timeaware_ssm | -12.2557 | timeaware_ssm | -12.2557 | timeaware_ssm (176.8917) |
| Muskingum 24d (m³/s) | 360 | 174.3431 | timeaware_ssm | -34.5004 | timeaware_ssm | -34.5004 | timeaware_ssm (208.8435) |

## Prespecified macro summary and scientific interpretation

Cross-domain averages are **dimensionless** fractions of each dataset's own direct-Ridge RMSE, never an average mixing kelvins with m³/s. Across 9 tasks, default Orc beat direct ridge on **2**, lost on **5**, and tied on **2**, mean fractional RMSE gain **+2.0511%**. Explicit research-opt-in Orc beat ridge on **3**, lost on **4**, and tied on **2**, mean fractional RMSE gain **+3.4970%**. This positive mean is concentrated in specific horizon/domain tasks, not a consistent advantage. The observed research SSM+KAN+HDC improvement on Raccoon 24d is bounded to one task; calibration selection otherwise sometimes chose candidates that *lost* heldout to ridge. The alternate strong classical AR24 and lag24 baselines often beat both direct ridge and Orc's narrower default candidate set.

**Do not claim general Orc enhancement over ridge** from this comparison. Ordinary method selection can sometimes help but cannot replace stronger matched baselines or independently justified mechanisms. This is evidence for the pipeline's ability to make and record fixed, falsifiable choices—not proof of superiority. All nonpositive results are preserved.

## Dependence, cost and remaining external validity holds

Original 01D nonoverlapping 24-origin block bootstrap / 90%-nominal block maximum sensitivity diagnostics were emitted for each fixed choice, **descriptive, not conditional confidence or universal statistical coverage guarantees**. The default 24d Muskingum selected SSM suffered RMSE -34.5004 m³/s compared with ridge; the paired MAE sensitivity interval was negative in this single task. All COG-01E parameter decisions were frozen before reading the heldout targets. Source publication times are **ASSUMED**, not publisher attested, so this retrospective cannot certify true operational as-of knowledge. Distinct physical datasets had been used in earlier Cognitum scientific research, so there is no unseen-source generalization claim.

Per-platform `perf_counter` records actual *wall clock* for input parsing, model fit/cal, decision and test scoring; `tracemalloc` records *partial Python allocator* peaks, not NumPy-native/OS RSS or enforced system resource limits. Example Ubuntu 3.11 across nine tasks: median source parse ~0.247s; train + calibration ~0.748s; two policy proposals ~0.581s; holdout score + evidence ~1.256s; median Python tracked peak ~3.62MB. Windows 3.13 mediants are higher and not cross-machine controlled. No method-specific wall clock or energy efficiency superiority follows from these coarse figures.

Source instrument signature/rights outside archived declarations, truly observed reporting latency, prospective independent site data, HDC/KAN snapshot bitwise portability across OS, actual memory/resource quotas, installed native execution, human-authenticated overrides and task-specific CH⊕aT synergy remain separate unfinished work. All 72 broad SSM DS capability groups remain PARTIAL.

**Next independent science:** commission a new unseen-source/actual-availability benchmark if predictive generalization is required, plus consolidate accepted Orc source for installed production acceptance separately.
