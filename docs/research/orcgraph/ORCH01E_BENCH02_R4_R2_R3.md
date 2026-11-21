# BENCH-02-R4-R2-R3 — Original Orc portable near-tie refusal and source-bound numerical identity

**State: pending single source-locked four-platform native qualification.** This work improves the original source-bound method-selection contract **without optimizing already-reviewed held-out scores**.

## Preregistration and research constraints

- First frozen numerical refusal protocol: [PREREG](ORCH01E_BENCH02_R4_R2_R3_PREREG.json), commit `003f6598ca4d85d5fda306708b55844259f5becf`, original Git blob `dcfc11361bee51507cbdbe99f73652755023eb27`. The already-viewed KATL 1h calibration near tie is explicitly disclosed.
- Separate explicitly published **pre-execution receipt-precision only** [AMENDMENT](ORCH01E_BENCH02_R4_R2_R3_RECEIPT_AMENDMENT.json), original blob `d62a05fabbbe5aa7490d046f20382f24d7973d0f`, changes eight-decimal portable **receipt** precision from an earlier nine-decimal plan due closeness to a rounding midpoint. The original selector and all full-precision numerical data continue to use unrounded float64. Original near-tie tolerance 1e-10 K and all model/selection rules unchanged.
- Unchanged original archived NOAA KSEA/KDEN/KATL raw bytes and source hashes, 115/38/39 hourly train/cal/test and 1/3/6h horizons, all nine original original-R3 cohorts and 265 test origin-target pairs. Original R4 negative baseline report and R4-R2 full-native positive/negative results remain in Git exactly. No new weather acquisitions or adjustments to the prior measured target values. New followup is *not blind*, because previous original calibration and heldout results have been viewed.

## Original Orc policy change: opt-in refusal only

The actual original `cognitum.orc_selection.SelectionPolicy` gains an **optional** `portable_near_tie_mae_kelvin: float` limited to finite [0,1e-6]. Default `0.0` retains legacy exact-float ranking. When the explicitly opted-in `1e-10` K policy sees two eligible research-involving competitors whose *calibration* MAEs are within that tolerance of the leading method, **the full proposal ABSTAINS**, with stable `portable_near_tie_abstention` basis and `ambiguous_near_tied_research_calibration` reason. No fallback to another model and no tuning on heldout labels; all original min-gain, availability, source provenance, resource cost and research opt-in admission policies remain. The original `evaluate_frozen_proposal` still independently rederives the selected nonabstaining decision.

This conservative refusal is not accuracy improvement. It is intentionally chosen **without selecting KAN or KAN+HDC by their already-known heldout scores**. Existing fit_training, Chebyshev KAN weights, MAP HDC associative code, source feature transforms, HDC prototypes and OOD behavior are byte-for-byte unchanged.

## Source-bound portable identity is not raw float bitwise identity

A new research-only `portable_source_bound_certificate` binds the actual original NOAA source SHA, derived original source CSV SHA, original train/cal/test pair hashes, prereg and receipt amendment SHA, original policy eligibility and reason vocabulary, selected method/status and bounded eight-decimal *calibration-only* MAE/RMSE records. Round-to-nearest half-bin boundary distance <=1e-12 K **refuses** rather than inventing a source certainty. The certificate's SHA-256 must match **all four independent native runs**. Full-precision original `Decision.decision_sha256`, HDC prototype SHA, KAN snapshot SHA and other native Fitted identities are retained without pretence that their least significant bits are identical.

Across original Windows/Linux Python 3.11/3.13 on the exact same Git SHA, the **separate, independent verifier** must require: all nine source-bound cohort receipts, same portable policy/selection/abstention and certificate hash, candidate MAE/RMSE drift <=1e-10 K, per-same-method heldout forecast drift <=1e-9 K, all 265 original matched observations, recomputed MAE/RMSE, original method-level losses and gains, unchanged original source Git blobs, passing matching JUnit inventories, and complete 4/4 native artifacts. Historical raw decision IDs may differ and are explicitly disclosed.

## Correctness and improvement audit — separate from tuning

The current **original** KAN correction is a single layer Chebyshev degree-2 basis over two measured lags, fitted to train-only stable-SSM residuals via closed-form ridge (`ridge=.5`). HDC uses MAP binary-like 256-dimensional hypervectors, two prototypes grouped by the median of original training origin temperatures, four bins/feature and train-only residual means. This demonstrates use of real KAN/HDC implementation paths; it is **not** evidence that their present representation is optimal, that HDC is a neural forecaster, or that a new physics law is learned. The raw cross-platform native source runs previously showed almost indistinguishable numerical predictions for the same method, even as the near-tied selected method changed.

Further KAN learning curves, alternative basis degrees / regularization and richer HDC encoders, associative noise capacity, regime labels and specialist composition are **separate preregistered experiments on freshly acquired prospective data**. Training or selecting on the existing 265 original test labels would invalidate this retrospective comparison. Native mathematical invariants, snapshot integrity, numerical finite checks and train-only custody remain mandatory.

## Required final dispositions

**PASS eligible:** original 4/4 native jobs and independent four-platform aggregator pass on unchanged source, preserve every original negative result, qualify portable refusal/identity, retire automatic CI, publish exact ZIP and numerical receipts. **FAIL remaining** if portable certificate or method decision differs, native model outputs diverge beyond source-locked tolerances, any original row or source hash changes, or any old safety refusal fails. A passing successor qualifies deterministic research **refusal/identity only**, not full end-to-end installed OrC/COG-06 orchestration, historical live public availability, or proof of KAN/HDC performance generalization.
