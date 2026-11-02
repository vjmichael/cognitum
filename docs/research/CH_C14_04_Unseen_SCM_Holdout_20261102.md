# CH-C14-04 — Preregistered unseen causal-SCM holdout: science still NO-GO

**Date:** 2026-11-02. Linux-only research, frozen G25I/G25 release guard unchanged. No Lu, Windows, or Cognitum production estimator modification.

## Study provenance

- Protocol frozen **before result generation**, SHA-256 `1272600affb07a86575ffb3db02586cf87593a43bdd8ae74d29563a417323718`.
- Six new generator families: randomized nonlinear, measured-binary sufficient adjustment, continuously confounded with only binary-coarsened W observed, hidden-U confounding, rare randomized, structural-zero overlap.
- 100 independent seeds in each of six families at n=900 and 1,800: **1,200 datasets**. Fixed analyst Gammas 0 and 0.25: **2,400 guarded report attempts**.
- Exact pinned G25I source SHA `f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4`; guard SHA `3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c`.
- **In-process guard computation** (not worker lifecycle): 3.55 seconds for all 2,400 attempts, 2,000 conditional reports, 400 missing-arm refusals, no crashes and **zero automatic causal certifications**. 8/8 new reproducibility tests PASS; 9 archived payload SHA entries verified after ZIP extraction.

## Discoveries

- True ATE is analytically constant by simulation: +0.10 except rare-event +0.01.
- For cases where Gamma=0 identification actually holds (randomized and measured-W-sufficient), the guarded **outer intervals included truth in 100/100 per cell**, but mean interval widths were **2.6–3.1x** an independent *post-freeze secondary* stratified Wald comparator; thus overconservatism persists. Wald coverage in these cells was 95–98% descriptively (100 cases/cell; not precise formal calibration).
- For hidden confounding, Gamma=0 outer band contained the true ATE **0/100** at each n. Gamma=0.25 contained truth **93/100 at n=900** and **21/100 at n=1800**. Its Gamma assumption is not verified and may be incorrect, so these are **descriptive inclusion rates**, not nominal CI coverage claims. More sample size narrows invalid-assumption intervals without curing bias.
- With continuously confounded X compressed to binary W, Gamma=0 causal identification is likewise not established. Its observed 100% outer inclusion is due to width; it is **not** evidence of causal validity or continuous-covariate support.
- Deterministic T=W structural overlap: **400/400 guarded attempts refused** across two n and Gamma levels, no invented intervals. The Wald comparator also refused.

## Scientific gate disposition

**NO PRODUCTION PROMOTION**. This study does not fix G25N's 12/12 scientific width failures, global LR inversion, calibration or broad continuous and heterogeneous causal models. A narrow Wald CI is not a universal alternative; it also fails under hidden confounding. The standard comparator was analyzed after the G25 preregistration and is clearly marked **secondary post-freeze**, not a preregistered acceptance baseline.

Next work: isolate numerical conservatism from identification failure, preregister new method mathematics **before** any new holdout, compare with robust standard estimators on fresh nonlinear/rare and heterogeneous SCMs and explicit refusal regimes, obtain independent R/Firth and scientific review. Do not retune the G25N 12-cell release threshold.

## Reproducibility

Local artifact: `Cognitum_CH_C14_04_Unseen_Causal_SCM_Benchmark_2026-11-02.zip`, SHA-256 `82c1d2d4df01acbac0588d5ec282f100d7505017398feff062fd181f8099f55b`. The ZIP includes the **protocol, generator and in-process pinned-source caller, complete 2,400-case receipts, summaries, secondary post-freeze comparator, 8 tests, full report and SHA manifest**. Original G25 pinned research modules remain separately in CH-C14-03; they are not duplicated or modified by this archive. Reproduction requires restoring that precise source in the parent CH-C14-03 directory.

**Release decision: RESEARCH ENGINEERING PASS, SCIENTIFIC NO-GO.**
