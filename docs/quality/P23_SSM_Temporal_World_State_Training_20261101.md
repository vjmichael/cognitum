# Cognitum P23 — Actual SSM temporal-state training (Linux research)

**Date:** November 1, 2026 (America/Phoenix; runtime Nov 2 UTC).  
**Status:** **PASS for actual offline training, checkpoint integrity, long-sequence/chunk equivalence, and research benchmarking. NO-GO for autonomous physical-world state estimation, collision avoidance, or production promotion.**  
**Separation:** Cognitum only. No Lu modifications. P15 and all Windows-specific work remain indefinitely deferred. GitHub is a repository, not a development hub.

## Research question

Can Cognitum's existing **bounded diagonal, time-invariant linear SSM** learn to estimate a scalar moving object's velocity when a noisy velocity sensor becomes unavailable during occlusion, and carry state through sequences longer than its 64-step worker-call limit? Can it generalize to unfamiliar drag dynamics?

This is an **abstract one-dimensional velocity-estimation experiment**. It does not involve video, object detection, image segmentation, 3D motion, material properties, object identity, a real drone, or live sensor readings.

## Synthetic simulator and what the model sees

At each step the hidden scalar velocity follows:

`v_t = rho * v_(t-1) + 0.30 * u_t + eta_t`, `eta_t ~ N(0, 0.04^2)`.

The sensor returns `z_t = v_t + epsilon_t`, `epsilon_t ~ N(0, 0.12^2)`, *only while the target is visible*. The actual model input at each step is `[control_u_t, z_t_if_visible_else_zero, visible_mask]`. The hidden ground-truth velocity is a **training/evaluation label only**, never a model input. Occlusions occur in bursts; one audit family uses longer occlusions. The model's predictions are continuous numerical estimates, not verified world facts.

Train/validation simulator uses `rho=0.92`. Frozen audits include unfamiliar `rho=0.80` (higher drag) and `rho=0.985` (more persistent motion). The latter demonstrates clear out-of-distribution failure.

## Actual training

- Four state variables, three observed input features, one output; exact architecture **diagonal LTI SSM** `h_t = A*h_(t-1)+B*x_t`, `y_t = C*h_t + D*x_t`. **Not Mamba** and not a selective SSM.
- Stable parameters `A=sigmoid(raw_A)*0.999`; model outputs and trained parameters must pass Cognitum's existing `DiagonalSSM.from_mapping` validation.
- Train **1,000 synthetic sequences of length 32** with AdamW, up to **700 minibatch updates** (96 sequences/batch), gradient norm clipping 1.0, occluded-step loss weight 1.5. Use a separate **240-example length-32 validation set** for model selection; selected **step 425**.
- Training uses a differentiable, causal convolution formulation and validates numerical agreement with a literal recurrent scan. Long sequences are evaluated with repeated calls of **at most 64 steps** each, using `final_state` from the prior chunk as `initial_state` for the next.
- The P19 parameter export schema remains unchanged, with `trained:false` **by schema design**. A separate P23, SHA-256-bound, clearly research-only training receipt attests that *this parameter blob was produced by offline optimization*. Neither source nor receipt permits automatic production authorization. No optimizer state is saved and exact training resume is not supported.
- Independent replay: trained parameter JSON SHA-256 **`1a82524f7aebc36d4c81c4b2e793d3fe6c211db1f6f8990b121cd26665103543`**, receipt SHA-256 **`41357d1daf7d96c8b6b6477e516540eb497820c18aa7a64dde6b5ab4e76f2261`**, both **byte-for-byte identical** after full retraining.

## Fresh-seed audit (not used for training or selection)

Each row has **240 unseen synthetic sequences** and the stated per-sequence length, **1,200 sequences total**. RMSE is in the simulator's synthetic velocity units (not metres or metres/second calibrated to real hardware). The baselines are:
- **Kalman_nominal:** an explicitly privileged, conventional Kalman filter given the nominal simulator's `rho=0.92`, control coefficient and noise statistics; remains fixed to `rho=0.92` even in unfamiliar-dynamics audits (not given the hidden true test rho).
- **Last_sensor:** holds the most recent visible noisy sensor reading through occlusion.

| Fresh-seed scenario | Trained SSM RMSE | Kalman_nominal RMSE | Last_sensor RMSE | Fraction occluded |
|---|---:|---:|---:|---:|
| Nominal, 32 steps | **0.1388** | **0.0814** | 0.3026 | 47.1% |
| Nominal, 128 steps | **0.1176** | **0.0785** | 0.3437 | 50.9% |
| Longer occlusion, 96 steps | **0.1266** | **0.0872** | 0.5226 | 70.6% |
| New drag (rho 0.80), 128 steps | **0.2339** | **0.1615** | 0.2957 | 51.1% |
| New persistence (rho 0.985), 128 steps | **0.6113** | **0.3534** | 0.3572 | 49.8% |

The trained SSM beats simple persistence on nominal/occlusion conditions but **does not beat the physics-aware Kalman filter**, and it is **worse than persistence** on strongly persistent, unseen dynamics. These rows do not demonstrate world perception or correct object identity across occlusion.

The Kalman filter has access to the **known simulator family**; this is a legitimate strong physics-informed baseline, not an equal-information learned representation comparison. The observed gap highlights the value of mechanistic priors and adaptive filtering, and the limits of fixed LTI memory under missing observations.

## Engineering checks

- New P23 tests **10/10 passed**, including missing-truth separation, invalid configs, convolution-versus-recurrent agreement, exact Cognitum numerical kernel equivalence, chunk invariance/state restore, strict input rejection, artifact SHA pinning, tampering rejection and absence of production promotion.
- New and inherited artifact tests **20 passed** together (one expected duplicate ZIP warning from a malicious checkpoint fixture).
- Expanded isolated specialist/quality/physics group **87 passed** (two expected duplicate ZIP warnings; no cgroup or worker-host security suite included).
- Built a local `cognitum_core-0.1.0` **development wheel** with the added research module. All `RECORD` hashes verified and a truly isolated wheel install successfully executed 128-step streaming on the trained checkpoint.
- Full training replay reproduced both the exact checkpoint JSON and receipt byte-for-byte. The fresh audit case receipts and metrics are stored separately from training and validation evidence.

## Decision and next experiment

**Research PASS:** real training/save/restore of Cognitum's diagonal SSM, numerical equivalence, state continuation, visible/occluded testing, and failure measurement on unseen dynamics.  
**Deployment NO-GO:** real-scene tracking, film blocking, collision avoidance, drone flight, unsupported safety assertions, or a general physical-world model.

Suggested next P23b: train and benchmark an **input-dependent gated/selective state update** (or small GRU/DeltaNet control) against the same Kalman, persistence, and diagonal SSM baselines. Predeclare new seeds, train/validation/test families and long-occlusion/OOD gates. Preserve the authoritative NVP scene graph and physics engine outside learned state estimation.

The Linux cgroup production gate, independent OS-supervised recovery acceptance, combined-worker-suite intermittent hang, and C14 causal-calibration gates remain open. **Windows/P15 deferred. Lu unchanged.**
