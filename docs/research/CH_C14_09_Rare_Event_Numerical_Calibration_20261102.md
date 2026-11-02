# Cognitum CH-C14-09 — Rare-event numerical reliability and calibration

**Date:** November 2, 2026 · **Research-only Linux** · Engineering PASS, scientific production **NO-GO**.

## Frozen evaluation

- `frozen_protocol.json` committed locally before new generated results. SHA-256: `b8ba6417bba1d6c9a949c2ec29a8553a42cb0cf9fb45f059bb2deacf46f76c4c`.
- Four distinct randomized-generative families (rare nonzero, very rare nonzero, rare null, heterogeneous randomized), n=240 and 800, 400 seeds/cell: **3,200 datasets**.
- Five methods each: Wald, Agresti–Caffo, true Newcombe hybrid score, statsmodels score-inversion, simultaneous Bonferroni–Clopper–Pearson outer difference: **16,000 attempts**.
- Existing pinned G25 and CH08 production-free research boundary unchanged. No Lu or Windows changes.

## Measured results

**14,015 issued intervals; 1,985 explicitly accounted numerical failures (all from score-inversion implementation); zero unexpected failures; zero causal certifications or promotions.**

| Family, n | Wald inclusion | Agresti–Caffo | Newcombe | Score inclusion / attempts (failures) | CP outer |
|---|---:|---:|---:|---:|---:|
| Rare nonzero, 240 | 382/400 | 391/400 | 394/400 | 132/400 (263 failed) | 400/400 |
| Very rare nonzero, 240 | **132/400** | 400/400 | 400/400 | **1/400 (399 failed)** | 400/400 |
| Very rare nonzero, 800 | 302/400 | 400/400 | 400/400 | 8/400 (390 failed) | 400/400 |
| Rare null, 240 | 400/400 | 400/400 | 400/400 | 2/400 (398 failed) | 400/400 |
| Heterogeneous randomized, 240 | 382/400 | 388/400 | 386/400 | 286/400 (92 failed) | 400/400 |

All eight cells and all method results are in the frozen output archive. Crucially, score conditional coverage among successfully issued intervals can be 100% while the *overall attempted-case success* is near zero. No silent fallback was performed. The observed failures implicate **this statsmodels numerical score-inversion implementation and its bracketing**, not the entire score-interval family.

Widths in the very-rare n=240 cell: Wald .01171, Agresti–Caffo .04948, Newcombe .06515, Bonferroni CP .07836. Conservative 400/400 inclusion does not demonstrate nominal 95% calibration or satisfy the precision requirement.

## Verification

- **10/10** new tests passed, then passed on independently extracted ZIP.
- Independent audit, without importing the candidate code, checked all **3,200 groups and 16,000 method receipts**, and recomputed **12,800 intervals** for Wald/Agresti/Newcombe/CP; max abs difference **2.78e-17**. Score failure status was structurally checked but its solver was not independently reimplemented.
- All **11/11** payload hashes in the ZIP verified after extraction.
- Full reproducibility archive: `Cognitum_CH_C14_09_Rare_Event_Numerical_Calibration_2026-11-02.zip` SHA256 `e632c57d33b9dc8a5d9da62912736f250b808bec0587e8d6ec07059e7acb8049`.
- Local report: `CH_C14_09/Engineering_Report_CH_C14_09.md`.

## Scientific decision and next work

**NO-GO retained.** This closes a local numerical diagnostic, not all of C14. Coverage/width calibration, observational nuisance-model misspecification, continuous/heterogeneous effects, independent real-world trial provenance, external R Firth equivalence and independent scientific review remain open. `Rscript` is not installed here.

Proposed CH10: predeclare genuine continuous-confounding, rare outcomes, treatment-effect heterogeneity, and positivity stress models; compare simple adjustment, cross-fit AIPW and heteroskedasticity-robust variance, maintaining all attempts/refusals and an independent numerical reference. Verified study design cannot be inferred from synthetic source signatures.
