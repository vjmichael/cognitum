# P25 — HDC robustness on real optical digit observations (research)

**Date:** 2026-11-02. Linux research only; no Lu changes; Windows deferred. No production source promotion.

## Scope and limits

The UCI HAR motion-sensor archive could not be retrieved in the sandbox, so P25 uses the scikit-learn bundled UCI optical handwritten-digits images as an **interim real-image observation** task. The original 1,797 digit images are real; noise, dropout, shift and rotation are generated. It is NOT a real motion or vibration sensor benchmark. Train/validation/test stratified samples: 1,078/359/360. Writer identities are unavailable, so no writer-disjoint generalization claim is made.

Train HDC bipolar Gaussian random-projection class-centroid encodings (validation-selected 8,192 dimensions); compare logistic regression, RBF SVM, random forest and a matched train-data-augmented HDC and logistic/SVM experiment. Training augmentation: Gaussian noise and pixel dropout applied only to the 1,078 original training samples. Test perturbations are shared across models, and not used in model selection.

## Frozen held-out 360-case results

| Condition | HDC clean-trained | HDC augmented | SVM clean-trained | SVM augmented |
|---|---:|---:|---:|---:|
| clean | 88.61% | 87.50% | 98.89% | **99.44%** |
| moderate pixel noise | 68.33% | 88.33% | 11.11% | **96.39%** |
| severe pixel noise | 31.94% | 71.39% | 10.83% | **75.56%** |
| 50% pixels missing | 63.89% | 68.33% | 56.11% | **71.94%** |
| 1-pixel right shift | 42.22% | 37.78% | 30.56% | **53.33%** |
| 180-degree rotation | 34.44% | 35.56% | 38.33% | **39.44%** |

HDC clean-trained 8,192-bit query classification was stable even when 1,024 individual hypervector bits were flipped: clean 319/360 vs 1,024 flips 319/360. This measures encoding-level bit corruption, NOT physical noise, cryptographic integrity or corrupted SQL records. HDC appeared better than clean-trained SVM for some corruptions; that advantage disappeared once a conventional SVM was trained with appropriate noise. **Research NO-GO for claiming HDC outperforms conventional robust recognition.**

## Reproduction

Local artifact `Cognitum_P25_HDC_Real_Optical_Robustness_2026-11-02.zip` SHA-256 `3b4e5cd7b0c3cf59a0cb7a004a2bfa6668033edfd8c97adf6e69b4bbde3b465f`. Contains independent scripts, test split construction, real-image HDC checkpoint(s), case-level predictions, conventional baseline scores and methodology. ZIP checksum manifest verified and **6/6 tests passed** after fresh extraction. Not a full Cognitum regression and not integrated into production.

Next: acquire the public UCI HAR 9-channel accelerometer/gyroscope dataset; hold out entire subjects; compare HDC and traditional / neural classifiers with matched noise augmentation, sensor-level corruption, calibrated abstention, and task-oriented utility. Keep source data provenance and participant privacy constraints explicit.
