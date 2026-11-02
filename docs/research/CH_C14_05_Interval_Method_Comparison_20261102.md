# CH-C14-05 — Candidate interval math comparison and 1,440 unseen SCM datasets

**2026-11-02 · Research completed / SCIENTIFIC NO-GO**. Linux-only, no Lu, Windows or production estimator changes.

## Preregistration and provenance
The experiment's `frozen_protocol.json` was recorded before this new dataset's generation with SHA256 `35f1ae51fd32d5432165946287e35dc296c1046261c3735c8e3c70e4fdbc1b8a`. Candidate methods were selected following CH-C14-04 discoveries, so this is an exploratory follow-up, not a fully independent blind method selection. G25I and G25 guard remained byte-identical to pinned source SHA256 `f881ae12bdae90fa4acec0bae9046e5580f5ddad80a1794006c3da5a3f6621e4` and `3480952a031d17061615eaa92597e7b2f0df22495954d5656aeeb6b51322f64c`.

Six new SCM families × 2 sample sizes (900, 1,800) × 120 seeds = **1,440 datasets**, each evaluated under unchanged G25 Gamma=0, G25 Gamma=.25, stratified delta-method 95%, and 199-replicate fixed-arm binomial parametric percentile bootstrap = **5,760 attempts**.

## Fresh results

| Scientifically identifiable family | n | G25 Γ=0 truth inclusion / mean width | Delta truth inclusion / mean width | Bootstrap truth inclusion / mean width |
|---|---:|---|---|---|
| Randomized nonlinear | 900 | 120/120 · .325 | 112/120 · .115 | 111/120 · .111 |
| Randomized nonlinear | 1800 | 120/120 · .228 | 117/120 · .081 | 113/120 · .079 |
| Binary-measured adjusted | 900 | 120/120 · .330 | 117/120 · .123 | 114/120 · .120 |
| Binary-measured adjusted | 1800 | 120/120 · .231 | 118/120 · .087 | 117/120 · .085 |
| Rare randomized | 900 | 120/120 · .098 | 114/120 · .031 | 112/120 · .030 |
| Rare randomized | 1800 | 120/120 · .065 | 115/120 · .022 | 114/120 · .021 |

Delta and bootstrap passed the *predeclared descriptive nominal 95% Wilson-compatibility/width screen* in all **12/12 candidate-method-by-valid-cell comparisons**. G25 Gamma=0 passed no exact-nominal-95% compatibility screens because all 120/120 intervals included truth in each cell, consistent with known overconservatism. **120 replicates per cell and a Wilson screen are inadequate for promotion.** Bootstrap fixes the observed W/T arm counts and omits that source of sampling variance; it can be anti-conservative. This is a candidate diagnostic, not an approved statistical procedure.

**Negative controls:** hidden U made Gamma=0 G25, delta and bootstrap miss the true effect in **all 240/240 cases** at n=900 and 1,800. Continuous residual confounding produced delta truth inclusion **92/120 (n=900)** and **77/120 (n=1,800)**; bootstrap **89/120** and **76/120**, respectively. These numbers are *not* nominal causal CI coverage claims where identification is false. G25 Gamma=.25 contains the hidden-U truth 120/120 and 119/120 descriptively, but analyst Gamma's adequacy is unverified.

Structural-zero cases: **960/960 required refusals** across all four methods. Overall **4,800/5,760 intervals**, **960/5,760 refusals**, no missing records or automatic causal certification.

## Verification
- **8/8** new local CH-C14-05 tests passed, including pin checks, deterministic fixtures, negative cases and stratum invariance.
- Independent audit: **1,440 dataset groups, 5,760 attempts**, complete exact grouping/scoring, checksum, plus **60/60 independently recomputed delta confidence intervals** to 1e-13.
- Frozen protocol and complete case-level receipts + code in `Cognitum_CH_C14_05_Interval_Method_Comparison_2026-11-02.zip`; SHA256 `b5f78121b9f3f575dd7822f046262989174bf4e3235958d3863fa09c5fa8ac62`. ZIP manifest for seven payload files verified. Existing G25 pinned implementation resides in CH-C14-03 restored checkout and is not rewritten/copied into new candidates.

## Decision and next milestone
**Research/engineering PASS; C14 scientific release NO-GO.** Do not use interval width or statistical significance to infer causal identification or to select Gamma. Do not relax G25N's failed scientific gates. Proposed CH-C14-06: preregister a *design-aware mode separation* between externally verified randomized designs, plausibly justified measured adjustment, Gamma-conditional partial identification, and unresolved/invalid identification. Compare independent robust SE and rare/heterogeneous estimators on an untouched new holdout, retaining fail-closed refusals and external review; ensure production promotion is separately authorized.

No Cognitum production estimator, Lu core, or Windows changes. GitHub is a source repository and milestone record only.
