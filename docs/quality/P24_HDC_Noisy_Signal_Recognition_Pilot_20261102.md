# Cognitum P24 — HDC noisy real-world-style signal pilot (synthetic)

**Date:** 2026-11-02. Linux-only research, Lu unchanged, Windows deferred. This is a standalone experimental pilot, **not** production integration and **not real-world sensor data**.

A bipolar 2,048-dimensional random-projection HDC centroid classifier was trained on 960 synthesized single-channel 256-sample vibration signals, four artificial patterns: normal, imbalance-like, bearing-like and loose-like. Label-blind normalized FFT/window features were provided to all methods. Logistic regression and 140-tree random forest were fitted to the same training examples and features. Each test family contains 400 independently seeded examples.

| Condition | HDC accuracy | Logistic regression | Random forest |
|---|---:|---:|---:|
| nominal held-out | 91.00% | 100% | 100% |
| high sensor noise | 25.00% | 29.50% | 52.50% |
| missing segments | 73.25% | 78.50% | 73.25% |
| unfamiliar signal speed | 27.50% | 28.50% | 38.00% |
| sensor gain shift | 95.75% | 100% | 100% |

HDC encoded-query **bit flips** tolerated moderately: baseline 364/400; 64 flips 359/400; 256 flips 366/400; 512 flips 368/400; 768 flips 333/400. Improvements above the clean baseline at particular flip counts are random, not an advantage. Hypervector corruption is not the same as noisy input observations. Both are unrelated to cryptographic database integrity.

**NO-GO:** This encoding does not beat standard models and drops to chance accuracy under heavy sensor noise. No basis for claims about real equipment faults, multisensor fusion, physical understanding, or NVP Acting Coach performance. No lexical search or database recall roles are proposed for HDC.

Local reproducible research package: `Cognitum_P24_HDC_Noisy_Pattern_Pilot_2026-11-02.zip`, SHA256 `35de91c572d19dc28de226cdfe2a14c77950885a2e22b9a153159b0130cacc5d`. Includes generator, model weights, baseline scripts, confusion matrices, engineering report, 7 tests; archive manifest verified and 7/7 tests passed independently after extraction. Experimental source stays in downloadable package and is not merged.

Next: obtain appropriately licensed real sensor datasets, device/subject-disjoint holdouts, compare robust HDC feature encodings against tuned classical and neural baselines, and study calibration and abstention.
