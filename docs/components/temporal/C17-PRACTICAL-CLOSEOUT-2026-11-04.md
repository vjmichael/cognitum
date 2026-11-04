# C17 — Practical temporal state-space and learned sequence closeout

**Date:** 2026-11-04. **Status:** bounded implementation committed to PR branch; exact-head real Windows/Linux SciPy/scikit-learn acceptance pending. This is NOT C07 canonical event state or Lu's memory.

## Established libraries and practical scope

This component starts with the existing exact portable scalar Decimal Kalman random-walk `cognitum/temporal_filter.py`, preserving its original Protobuf contract, 26-test reference and limitations. New capabilities use maintained NumPy, SciPy and scikit-learn, not a hand-written neural S4/Mamba core.

**P0: typed temporal evidence and trained artifact.**
`temporal_statespace.py` contains bounded chronological, source-identified sample sequences (1–4 declared unit channels; 3–512 samples, missingness and source/observation IDs). Timestamps must be strictly increasing, with no hidden future initialization, finite numeric values and explicit provenance quality declarations. The filter never writes canonical Lu/C07 state. `temporal_learned.py` provides an immutable typed learned artifact with architecture, source ID, strict training end timestamp, training input SHA-256, train count, sampling interval, dimensions, coefficients, normalization, residual variance, min/max ranges and canonical artifact SHA-256. A digest is a corruption check, **not** an authenticated signature or permission.

**P1: actual conventional and learned baselines.**
- `temporal_statespace.py`: local-level and constant-velocity multichannel state-space filters, Joseph-form covariance update, SciPy covariance eigenvalue diagnostics, missing-observation prediction, source lineages, innovation-based anomalous observation abstention, bounded step intervals, forecast mean/variance, and explicit `ood` marker.
- `temporal_hidden.py`: 2–8-state categorical HMM using SciPy log-sum-exp probability recursions; handles caller-declared transition/emission matrices, missing categories, strict timestamps, impossible-evidence refusal, bounded state probabilities and thresholded change alerts. A state-mode change is **not proof of a semantic contradiction** in historical records.
- `temporal_learned.py`: opt-in trained scikit-learn Ridge autoregressive model (1–8 lags, regular data only). Uses strictly earlier data, standardization, Ridge regularization and recorded source/checkpoint lineage. Learned forecast supports up to 64 recursive steps, heuristic widening residual variance and OOD abstention. This is a genuine learned temporal reference challenger, **not a neural SSM/Mamba model, probability calibration, or an automatic Lu base-model update**. Training requires a host admission seam; a Boolean is not itself security authorization.
- `temporal_evaluation.py`: strict chronological one-step held-out comparison of no-model last-value persistence, conventional Kalman, and optional independently trained Ridge. Reports MAE, RMSE, mean wall-time, OOD counts, and descriptive 90% Gaussian coverage when a variance exists. Held-out labels are used solely to score already-produced predictions; no training on future labels.

**P2: adversarial and safety.**
Strict chronology, source and observation IDs, bounds on samples/dimensions/horizon, missingness and finite values. Refuses unknown units, duplicates, out-of-order timestamps, invalid transitions, impossible emissions, hostile or noncanonical Protobuf, corrupt or altered learned checkpoints, altered training lineage, accidental train/evaluation overlap, unapproved training, nonfinite state covariance and divergent forecast. Warnings for unverified source, measured-unverified vs synthetic provenance, model-assumption variance, change-point false positives and OOD. `ood` is a heuristic alert, not certified generalization failure. No hidden replacement of C07 event/snapshot memory or training on private traces.

**P3: reproduced baseline and evaluation.**
`tools/c17_temporal_benchmark.py` executes genuine SciPy/scikit-learn training on fixed synthetic history, 80 training and 40 held-out future points, and records actual temporal errors versus last-value and Kalman; it also evaluates a clearly synthetic categorical regime-change sequence using the HMM. Real CPU wall times are measured; no invented GPU VRAM, energy, user-task accuracy or empirical generalization claim. Multiple train/test windows and external real sensor datasets remain separately required for external production claims.

## Native typed surface

`proto/cognitum/temporal/v1/practical.proto`, `cognitum/proto/temporal_practical_pb2.py` and `cognitum/temporal_practical_wire.py` provide canonical typed Kalman/HMM requests/responses, explicit present-vs-missing masks, source/time lineage, trajectory state and uncertainty outputs, request SHA-256 correlation and numerical reexecution/verification. No executable code, network I/O, camera acquisition, user-content training, shell commands or Lu tool grants.

The learned checkpoint/training interface is implemented through host-owned Python **and typed Protobuf** in `cognitum/temporal_learned_wire.py`: `TrainRequest`, `LearnedArtifact`, `TrainResult`, `ForecastRequest`, and `ForecastResult`. `execute_train` requires a trusted-host-only `host_admitted=True` method argument and refuses requests by default; **the request itself cannot grant training**. The frozen model and its training data digest are checked during prediction and independent recomputation. `verify_train_result` verifies checkpoint structure and hashes but deliberately never retrains without renewed explicit admission. The Boolean method argument is an integration seam, not actual Lu host authentication. Lu/C02/C04 controls remain responsible for any future exposed model tool and source privacy/retention policies.

## Native CI

`.github/workflows/c17-practical.yml` requires actual NumPy/SciPy/scikit-learn Windows/Linux × Python 3.11/3.13, separate native compiler-produced Protobuf descriptor parity, legacy exact Decimal C17 reference tests, contemporary Kalman/HMM/Ridge/heldout test suites, malformed-wire/replay/identity tests, host-gated trained-checkpoint round trips, forged checkpoint refusal, and a real timed synthetic future-holdout benchmark. Optional C17 packages remain non-core extras; a minimal core regression may skip the new statistical engine, but **the dedicated native acceptance is not allowed to skip it**.

## Closeout rules and non-claims

1. Current PR-head cross-platform and relevant full-suite checks must pass; PR must be mergeable, and then merged before declaring CI-verified source closure.
2. Real-user temporal accuracy, trusted measurement provenance, calibrated forecast uncertainty, continuous online adaptation, GPU sequence performance and matched Lu model A/B are **not established by synthetic CI**.
3. Mamba/S4 and neural SSM training are research challengers, not mandatory to deliver useful correct classical predictions. No C14-style open-ended neural architecture research is included in bounded practical closeout.
4. Later Lu interface requires host user consent, OS isolation, independent training budgets, data retention controls, hard cancellation and separate routing/intent validation. C17 never silently modifies Lu memory or chosen model weights.

**Practical code complete is not equivalent to verified tests or production task efficacy.**
