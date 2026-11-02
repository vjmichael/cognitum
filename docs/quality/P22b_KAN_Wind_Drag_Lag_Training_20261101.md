# Cognitum P22b — Trained KAN for wind, drag and actuator-lag dynamics

**Engineering date:** November 1, 2026 (America/Phoenix; runtime UTC November 2).  
**Status:** **PASS** for bounded offline training, numerical validation, artifact integrity, and benchmark reproducibility. **NO-GO** for safety/real-drone control or replacing a known numerical solver.  
**Project boundary:** Cognitum-only Linux research; Lu unchanged; all Windows tasks/P15 deferred; no production algorithm promotion.

## Research question

Can a bounded, independently trained KAN approximate a *nonlinear time-varying* forward stopping problem more accurately than conventional regression, especially under unfamiliar combinations of wind, quadratic drag, motor latency, and slower actuator response? Does a soft monotonicity penalty improve quality without promising a hard guarantee? The numerical solver, not real-world flight testing, supplies ground truth.

The six input variables are ground speed **2–18 m/s**, commanded brake **2.5–8 m/s²**, trigger delay **0.04–0.35 s**, actuator rise time **0.06–0.55 s**, drag coefficient **0.002–0.035 1/m**, and along-track wind **−4 to +4 m/s**. Reference dynamics:

\[
\dot v(t)=-a\left(1-e^{-\max(t-\tau,0)/\lambda}\right)-k\,(v-w)|v-w|;\qquad \dot x=v,\;\text{stop when }v=0.
\]

A fixed-step RK4 numerical implementation handles velocity and a bounded event interpolation handles distance to the first stop. Reference labels use **dt=0.0125 s**. On 600 independent conditions, changing dt from 0.0125 to 0.00625 had maximum discrepancy ~**0.00083 m**, and 0.00625 to 0.003125 had maximum ~**0.00012 m**. Eighteen independent SciPy `solve_ivp` event integrations also agreed within **0.003 m**. The differential equation itself is a **deliberately simplified authored simulation**, not a validated real drone model. It omits 3D control, attitude, lift, variable battery, arbitrary gusts, impacts, obstacles, uncertain measurements and real material interactions.

## Training protocol

- Training **8,000** cases, validation **1,200**, one-sided empirical calibration **1,500**. Unseen uniform test **2,400**, dependent high-speed/tailwind/weak-brake/slow-actuator stress **1,600**, unfamiliar joint-correlation pattern **1,600**, and *latent* actuator-health damage **1,200**. Fixed separate seeds.
- The RBF KAN **6 → 8 → 1**, 11 Gaussian centers per input, obeys Cognitum's existing secure `kan_optional._load` maximum eight hidden units. NumPy-portable bounded NPZ weights. Offline PyTorch CPU training; AdamW, 1,650 minibatch steps, validation-selected checkpoint (step 1650), stable research-only model receipt. No changes to the pinned trusted loader or input protobuf contract.
- A **second, post-hoc experimental** KAN starts from the first model and fine-tunes for 800 steps with five directional finite-difference **soft monotonicity penalties**. Model selection uses validation only (selected at 600). These penalties **do not prove global monotonicity**.
- Baselines: the old ideal constant-deceleration equation (inapplicable to this extended physics), degree-2/degree-3 polynomial ridge models, histogram gradient-boosted regression, and the *same simulated ODE* integrated coarsely at dt=0.08. A fine dt=0.00625 reference confirms numerical stability. Polynomial regularization selected using validation only.
- The regularized variant was introduced **after seeing initial unregularized test results**, so initial held-out comparisons for that variant are adaptively informed. A second fresh-seed cohort of **6,000** cases (1,500 each of four test types) was run **after freezing both model checkpoints**, without retraining or tuning them.

## Model performance (mean absolute stopping-distance error, meters)

| Test family | Original KAN | Monotonicity-regularized KAN | Degree-3 polynomial | Boosted trees | Coarse RK4 solver |
|---|---:|---:|---:|---:|---:|
| Uniform (2,400) | 0.1608 | **0.1302** | 0.2361 | 0.3125 | **0.00345** |
| Weak braking / high speed stress (1,600) | 0.5096 | **0.4344** | 0.7760 | 1.3315 | **0.00262** |
| Unseen wind/drag correlations (1,600) | 0.1602 | **0.1278** | 0.1477 | 0.3194 | **0.00338** |

The old ideal stopping equation's MAE is **3.1676 m**, **3.4841 m**, and **2.8676 m** respectively, showing the extended simulator is genuinely different from P22's ideal equation. But the deterministic coarse ODE solver beats the learned approximations by more than an order of magnitude and remains the preferred accurate solution whenever that model is available.

### Fresh-seed secondary cohort (post-freeze; 1,500 per row)

| Condition | Original KAN MAE | Regularized KAN MAE | Main safety finding |
|---|---:|---:|---|
| Uniform | 0.1528 | 0.1283 | Simulated in-domain performance improved |
| High-speed/weak-braking stress | 0.5040 | 0.4257 | Regularized margin covers only **88.93%** |
| Correlated drag/wind | 0.1671 | 0.1317 | Regularized margin covers **98.40%** |
| Unmeasured 35% brake degradation | 3.4690 | **3.6110 (worse)** | Regularized margin covers **6.53%** |

All three modeled test-family gains for the regularized model have positive 95% *paired bootstrap* sample intervals in the independent audit. On unmeasured brake damage the gain is negative. These CIs quantify random synthetic dataset variation, not real-world transfer or a safety margin.

## Physical consistency and uncertainty: FAIL for safety use

- Across **2,000** independently seeded probes for each expected trend (speed↑, brake↑, delay↑, lag↑, tailwind↑), the original KAN had **59, 71, 98, 120, 144** directional errors. The regularized KAN had **19, 48, 62, 89, 117** (a reduction from 492 to 335 of 10,000 paired direction checks), **not zero**. The numerical reference had zero violations for these probes. No mathematical monotonicity guarantee exists for the trained RBF model.
- Initial calibration used the empirical **99th percentile of underprediction residual** on 1,500 independent calibration cases. The original KAN's coverage on uniform, stress and correlated tests was **99.17%, 92.94%, 98.50%**. The regularized model's was **99.21%, 87.00%, 99.19%**. These are empirical observed fractions, not risk guarantees.
- With unobserved effective braking reduced to 65% of the declared value, original KAN MAE was **3.389 m**, maximum underprediction **19.45 m**, and calibrated-margin coverage **11.25%**. Regularized KAN MAE was **3.525 m**, maximum underprediction **19.99 m**, and coverage **6.33%**. The full post-freeze cohort independently confirmed this failure. A model cannot detect an unmeasured failure mode from the same nominal inputs.
- Research inference **fails closed** for disabled access, mismatched physics identifiers, non-finite data, values outside the training domain and forged or incorrectly pinned artifacts. **This cannot verify that a caller's supplied physical conditions reflect the actual world.**

## Latency and suitability

For batches of 2,400 cases on this CPU (five warmed repetitions), median observed execution was approximately **2.14 ms for preloaded KAN**, **3.85 ms including checkpoint decoding**, **11.85 ms for coarse RK4** and **56.25 ms for dt=0.0125 RK4**. The old ideal equation took **0.035 ms** but is the wrong physical model here. Batch times are **not** flight controller or per-step latency benchmarks. The ~5.5× throughput advantage of preloaded KAN over the coarse solver does **not** make 0.13–0.43 m average model error acceptable for safety-critical decisions.

## Engineering acceptance

- **66/66 tests passed** across P22b, P22, P18 safe KAN decode, P19 model artifacts and P17 component checks. The two Python ZIP duplicate-name warnings are from intentionally hostile fixtures whose rejection is asserted.
- Trained KAN and regularized KAN both load through the existing size-/shape-bounded NPZ parser and exact SHA-256-pinned protobuf inference interface.
- Independent `solve_ivp` ODE cross-check, convergence of fixed-step integration, negative input and physical-regime gates, monotonicity probes, empirical coverage failures and inherited regressions are in the tests.
- Fresh-seed post-freeze audit on 6,000 examples; both KANs and their receipts are separately hashed and verified.
- **Exact independent training replay:** original checkpoint, original receipt, regularized checkpoint, regularized receipt and case-level uniform predictions match byte-for-byte. Model metric/trace JSON matches after excluding wall-clock and batch timing fields. Different hardware/software versions may change floating-point results; exact portability across platforms is not asserted.
- Rebuilt `cognitum_core-0.1.0` **development-only** wheel: internal SHA-256 `RECORD` verified; installed and smoke-tested outside source tree. No production promotion.

## Decisions

**Research PASS:** trainable bounded KAN surrogate, wind/drag/lag simulator, enhanced numerical and adversarial tests, soft monotonicity regularization, fresh independent audit, trusted artifact compatibility and reproducibility.

**Production/safety NO-GO:** any automated collision avoidance, drone actuation, NVP collision authority, hard physical-law guarantees, calibrated worst-case safety bounds, unseen real physics, hidden actuator failure, or replacing the known solver. For NVP, continue to use authoritative geometry/physics; KAN may eventually accelerate appropriately bounded *non-authoritative* preview tasks with measured error tolerance.

**Next:** P23 SSM temporal object-state training, with scene-ground-truth generation, chunk and reset equivalence, unseen sequence lengths, novel physics and action-effects. Real P13/P14 cgroup containment and C14 causal confidence gates remain open; P15 and every Windows task remain deferred. Lu is unchanged.
