# Cognitum P23b — Input-dependent selective temporal-memory training

**Date:** November 2, 2026. **Scope:** Linux research-only. No Lu modifications, no Windows work (P15 and all Windows tasks deferred). GitHub is the repository/documentation record, not the development hub. **NO production promotion**.

## Design and actual training
- Train a **physics-informed, input-dependent gated velocity estimator** (99 trainable parameters), and a separate **GRU-8** (321 parameters). The selective gate weights a noisy velocity observation based on current inputs and state and is zero when occluded. This is **not Mamba or a full selective SSM**, no 3D/video perception.
- Synthetic one-dimensional velocity obeys `v[t]=rho*v[t-1]+0.30*u[t]+eta[t]` with hidden target velocity as *label only*, input `[u,observed_if_visible_else_zero,visibility_mask]`. Nominal train rho 0.92, process noise 0.04, sensor noise 0.12.
- Train on 900 independent length-32 sequences (seed 43001), select only on 250 length-32 validation sequences (seed 43002), 450 AdamW steps, 96 sequences/minibatch, weighted missing-observation MSE, fixed seeds. Both best checkpoints were at step 450. Save exact, bounded SHA-256-pinned research-only JSON weights and a separate training receipt; no optimizer state.
- Compare against frozen P23 four-state diagonal LTI SSM, nominal physics-aware Kalman filter, last-sensor persistence, and new GRU. Kalman uses the known nominal simulator, fixed rho 0.92 even for OOD; no withheld truth or actual test rho is supplied to estimators.

## Frozen held-out audit
Nine test families, 180 independent sequences each, 1,620 total, 32–256 steps, fresh seeds 68001–68009. Values are RMSE in synthetic velocity units; lower is better.

| Family | Gated P23b | GRU-8 | Frozen P23 | Kalman nominal | Last sensor |
|---|---:|---:|---:|---:|---:|
| nominal 32 | 0.0922 | 0.0917 | 0.1379 | 0.0888 | 0.3041 |
| nominal 128 | 0.0815 | 0.0799 | 0.1158 | 0.0773 | 0.3346 |
| deep occlusion 96 | 0.0933 | 0.0939 | 0.1250 | 0.0898 | 0.4875 |
| unseen drag 128 | 0.1509 | 0.1509 | 0.2353 | 0.1574 | 0.3021 |
| unseen high persistence 128 | 0.3058 | 0.3945 | 0.5861 | 0.3455 | 0.3633 |
| midstream switch to drag 128 | 0.1250 | 0.1249 | 0.1934 | 0.1290 | 0.3172 |
| midstream switch to persistence 128 | 0.1910 | 0.2330 | 0.3474 | 0.2132 | 0.3407 |
| corrupted sensor noise 128 | **0.2364** | 0.1788 | 0.1944 | 0.1790 | 0.5010 |
| long outages 256 | 0.1749 | 0.1708 | 0.1798 | 0.1742 | 0.5075 |

Selective recurrence improves over frozen P23 in eight of nine test families, particularly unseen persistent dynamics, but is **significantly worse** under unmodeled sensor corruption and does not beat a nominal Kalman filter in routine conditions.

Paired 2,000-resample bootstrap at the **whole sequence** level, conditional on this simulator:
- unseen high persistence: gated minus P23 delta -0.2804, 95% CI [-0.3047,-0.2569]; gated minus Kalman -0.0398 [-0.0444,-0.0356].
- sensor corruption: gated minus Kalman +0.0574 [+0.0536,+0.0609] (gated worse).
- long outages: gated minus Kalman +0.0007 [-0.0002,+0.0016] (no clear advantage).

## Reproducibility, security boundaries, and decision
- Gated checkpoint SHA256 `04244e4782e3225e86da76bed32b9dbd855b5474d883eb8380ab59593d7730e7`; GRU checkpoint SHA256 `625e3f9ee5091f6221306dd66519ac80708dde5183e742f6cb528c7bdbfa7fbe`.
- Frozen P23 checkpoint SHA256 `1a82524f7aebc36d4c81c4b2e793d3fe6c211db1f6f8990b121cd26665103543`.
- Separate full retraining reproduced both checkpoint JSON blobs and training receipt **byte-for-byte**. P23b training receipt SHA256 `2ad65bf5229e0a823257eb71989ad67b1b466df03dc198113b50c7ccc3a50b41`.
- State-continuation and chunk equivalence for 1/7/32/64-step splits, state reset, causal no-future-leakage, invalid inputs, tamper and production-flag rejection checked.
- **92/92** selected new/inherited component tests passed (two expected malformed-archive fixture warnings); isolated wheel install plus 128-step streamed smoke test succeeded.
- **Independently extracted artifact:** archive checksum manifest verified; all **92/92** tests passed with P23 and P23b receipts separated, and all audit and bootstrap JSON files matched the originals byte-for-byte.
- Verified archive **`Cognitum_P23b_Selective_SSM_Temporal_Memory_2026-11-02.zip`**, 376 entries, SHA256 **`38e60f46aff8ab2a2fa47e03b830b601c175947168310f58230bd0f168be2b1b`**. Includes source tree, both new checkpoints, frozen P23 baseline, original P23 receipt, case-level audit, bootstrap intervals, tests, experimental wheel, detailed local report, reproduction README, and checksum manifest. Experiment code and model weights are in this downloadable local overlay, **not merged into the GitHub repository production source**.

**Research PASS; deployment NO-GO.** The model remains a scalar simulator-trained observer, not actual visual object/actor tracking, real scene state or a safe physical controller. A conventional nominal Kalman filter is preferred for correctly modeled dynamics. Next P23c: confidence-aware sensor quality and robust filtering baselines against severe faults, on newly held-out generators. Do not tune on P23b test cases.

Open unrelated gates: Linux OS-supervised containment/recovery, combined-suite intermittent hangs and C14 causal uncertainty. Windows deferred, Lu unchanged.

