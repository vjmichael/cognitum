# Cognitum P22 — Trained KAN physical-dynamics research and negative safety gates

**Date:** November 1, 2026 (Phoenix; local test logs Nov 2 UTC). **Scope:** Linux CPU, research-only, no Lu edits. All Windows-related tasks including P15 remain deferred. GitHub remains a repository and engineering record, not the development hub. **No production promotion.**

## Actual trained model

Using the recovered P19 KAN training-artifact code as a base, P22 trained a **two-layer RBF KAN, 3→8→1, nine radial centers per input** via PyTorch CPU AdamW on 6,000 synthetic input/output pairs for the idealized constant-deceleration stopping distance equation `d = v*t + v*v/(2*a)`. Training ranges: speed 0.2–12 m/s, deceleration 2–8 m/s², response delay .05–.35 s. This function assumes ideal brakes and known conditions and does not represent real drone control, obstacles or other physics. Training: 2,000 random minibatch updates (batch 512), LR .012, seed 71; select best step 1,300 using only 1,200 validation examples. Calibration and test seeds were held back.

P22 includes a weaker one-layer additive **spline KAN** as an architectural control and degree-2/degree-4 polynomial regressions plus the exact analytic baseline.

## Frozen numerical tests

**2,400 new uniform cases**:

| Method | Mean absolute error (m) | Worst absolute error (m) |
|---|---:|---:|
| Trained RBF KAN | **0.0812** | 1.4678 |
| Additive spline KAN | 1.4676 | 12.4789 |
| Degree-2 polynomial | 0.6480 | 7.4414 |
| Degree-4 polynomial | **0.0757** | 1.1082 |
| Exact analytic equation | ~0 | ~0 |

Other disjoint seeds: high-speed/low-braking cases had KAN MAE 0.1817 m. When real deceleration was only 65% of the *nominal declared* acceleration—an unmodeled regime—KAN MAE was 2.9623 m, maximum error **18.2716 m** and it **underestimated** stopping distance in **94.08%** of 1,200 cases.

Nominal one-sided 99% calibration margin of 0.2199 m covered only **98.42%** of the frozen test (versus a 99% target), and only **18.42%** in impaired braking. Unconstrained KAN also violated basic monotonicity on independently seeded directional probes (1,500 each): **39** speed-increase violations, **125** deceleration-increase violations, **125** delay-increase violations. Such outputs are unacceptable for physical safety.

Warm CPU vectorized latency for 2,400 examples: exact analytic .0325 ms, loaded KAN 1.7555 ms, KAN including checkpoint decoding 2.9560 ms. Batch figures, not controller timing.

## Source, tests, and artifact

- New P22 tests: **14/14 passed**; combined inherited P17/P18/P19 relevant component/decoder tests **42/42 passed**, with two expected duplicate-member warnings from malicious fixture tests.
- Trained NPZ, fitted spline NPZ, P19 exact-SHA training receipt and test CSV were **identical byte-for-byte after independently repeating the entire training pipeline**.
- P19 bounded NPZ loader, checkpoint SHA pinning, receipt verification and protobuf API passed; out-of-domain and explicitly unmodeled conditions refused. **Cannot detect falsely declared physical conditions.**
- Research-only wheel rebuilt, RECORD verified and isolated installation smoked. No hidden auto-approval; optimizer state was not saved, so no resumable training claim.
- Verified local source+model+data+tests+wheel archive: `Cognitum_P22_KAN_Physical_Dynamics_Training_2026-11-01.zip`, **327** entries, SHA256 **c44c4578ef971e9b0e9f710ed1b27bc98428feb42f23aa06c3ac06d4554765ab**. Independently extracted, checksums verified and all 42 tests passed again.
- Trained RBF checkpoint SHA256: `aa0bd3ca07f077db9a4eafeb8fa68afb40373ff309ed3584c0870ec21b38c3be`. These tested P22 source changes remain **inside the local artifact, not yet merged/committed to the production source tree**.

## Decision

**PASS:** offline actual KAN training, versioned trustworthy artifact, numerical regression comparisons, out-of-domain refusal, model re-execution. **NO-GO:** using learned output for drone collision avoidance, any physical-world safety assertion, or as an improvement over an exact known equation. **NO-GO for scientific advantage over the tested degree-4 polynomial**.

Recommended next P22b: a new frozen benchmark of partially unknown, genuinely nonlinear simulated dynamics with wind, drag and actuator latency included as explicit features, physically monotone constraints and comparison with ordinary models and physics-based solvers. Keep authoritative NVP collision/geometry logic deterministic. Keep all prior Linux cgroup/OS recovery gates and C14 causal-confidence gates open.

