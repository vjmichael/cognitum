# COG-05-SSM-04-R2 — Native continuous-time and irregular-timestamp estimation

**Status: ACCEPTED — 5/5 genuine native/independent jobs at exact source `ee88fdb0a53af04603c51b41c30768bdc62f9c0d`.** Windows and Linux, Python 3.11/3.13, original SSM-04 regressions and new R2 mathematical interfaces all passed. No new weather/Orc benchmark or publisher acquisition was performed.

## What this implements

New isolated CPU research module `cognitum/research/ssm_stochastic_continuous.py` reuses accepted SSM-04 `ssm_stochastic` validation, Van Loan continuous-to-discrete covariance transition, Joseph Gaussian update and numerical covariance clipping within a small explicitly checked tolerance. Existing stochastic/SSM specialist source is unchanged.

1. **Continuous-time Kalman–Bucy equations:** bounded numerical DOP853 integration of
   `dm/dt = A m + P H^T R^-1 (y_rate-Hm)` and
   `dP/dt = A P+P A^T+Q-P H^T R^-1 H P`,
   with a piecewise constant observed measurement rate on predeclared intervals. This is the continuous Kalman–Bucy Riccati/mean ODE, **not** an assertion that holding a sampled noisy increment produces an exact pathwise white-noise innovation. Results explicitly label the approximation; process diffusion and sensor noise covariance are separate.
2. **Irregular sampled measurements:** strict increasing timestamps, exact continuous-to-discrete Van Loan covariance and transition composition between samples, bounded segmentation and Joseph covariance updates, Gaussian log likelihood and NIS. Entirely missing samples are `None`: prediction only, no imputed zeros or invented readings. The timestamp scale is the model's physical time unit; these are discrete instantaneous measurements, **not** the continuous rate semantics above.
3. **Bounded fixed-lag RTS smoothing:** after assimilating measurement event `j`, release state `j-lag` using only observations through event `j`, with explicit state timestamp, release timestamp, reported pending tail and no future beyond release. The fixed lag is measured in **observation events, not wall-clock seconds**. Prior fully offline RTS smoother remains available separately and must not be mistaken for online filtering.
4. **Covariance safety:** explicit strict observation-noise positive definiteness and condition bound, symmetric/finite/PSD checks on every posterior and prediction, refusal for materially negative eigenvalues and ill-conditioned smoother gain, numerical step budgets, finite input shapes and magnitudes; all receipts are `certified=False`, `execution_authorized=False`.

## Bounded scope

- Maximum 8 state variables and 8 sensor measurements; at most 256 observation events, total modeled time 256 units, at most 4,096 composed discrete transition segments across a run. Kalman–Bucy supports intervals at most 32 modeled time units, with at most 8,192 total accepted DOP853 steps and 100,000 RHS calls.
- Covariance corrections are numerical tolerance and diagnostics, **not interval-certified enclosures or evidence of global positive-definiteness for every admissible physical model**.
- No nonlinear continuous-time observation model, true stochastic continuous white-noise path sampling, matrix-free large-dimensional filtering, arbitrary rank-deficient observation noise, live host actuation, installed MEL permission, or uncertainty calibration under model mismatch is claimed.
- This task is *mathematical engine implementation*, not a new forecasting performance ranking; all existing SSM/HDC/KAN, Orc Graph, original R3–R5 NOAA scientific and safety results remain unchanged.

## Independent correctness and regression obligations

New `research_tests/ssm04r2/test_continuous.py` covers stationary scalar Kalman–Bucy exact mean, nonstationary Riccati `tanh(t)` analytic covariance, coupled 2D PSD, analytic OU irregular first/second moments, scalar closed-form Gaussian posterior and missingness, a distinct direct block-exponential Van Loan calculation, one-step fixed-lag Gaussian batch conditioning, release prefix invariance when later observations change, lag-zero filter parity, two-event smoothing PSD, bad/misaligned/noncausal clocks, negative sensor noise, invalid sensor vector, modified negative covariance and computational budget refusals. 
Original `research_tests/ssm04/` and `research_tests/ssm04r1/` must continue passing. Complete native qualification runs on Ubuntu/Windows Python 3.11/3.13 with pinned NumPy/SciPy, identical JUnit test inventory and source Git SHA checks, and independently verifiable artifact records. A local focused run passed 18/18 cases in the model working container; final exact Git SHA acceptance is separately required.

## Next extensions

- A strict **continuous stochastic measurement increment** assimilation method with correctly modeled Brownian-path/innovation discretization (the deterministic held-rate ODE is not that), plus more explicit continuous/discrete sensor covariance units.
- Stable square-root/information continuous-discrete filtering for poorly conditioned or semidefinite regimes; Kalman–Bucy numerical Riccati integration with a verified stability enclosure or deterministic residual certificate under declared assumptions.
- Optional time-duration rather than observation-count fixed-lag smoothing, and durable stream/checkpoint/resume source custody through MEL host authorization.
- Broader nonlinear/stochastic filtering, distributed state models and real physical source uncertainty must be separate claims and tasks.

**Task outcome is not a claim of universal SSM estimation superiority or complete SSM-04 coverage.** All 72 broad COG-05 research capabilities remain PARTIAL until their respective scientific and native acceptance obligations are met.

## R2-R1 original native exact-source closeout (2026-11-21)

**Accepted unchanged original source:** `ee88fdb0a53af04603c51b41c30768bdc62f9c0d`; original [GitHub Actions 5-job run #44879505986](https://github.com/vjmichael/cognitum/actions/runs/44879505986) **SUCCESS**. Original native Windows/Linux Python **3.11/3.13 each passed 77/77**, **308/308 total** with zero failed, errored or skipped checks. A separate fifth original workflow job independently downloaded all four ZIPs, checked identical exact source SHA, identical six original/new source Git blob identities, and identical original + R2 test names across all four native targets. That fifth job also **PASSED**.

All five original GitHub Actions ZIPs were independently downloaded, SHA-256 checked against their GitHub-recorded digest, ZIP CRC-checked, JUnit inventories inspected, and the independent receipt checked against the four native ZIPs. Their complete source/archive SHA and per-platform counts are preserved in [SSM04_R2_R1_NATIVE_ARTIFACTS.json](SSM04_R2_R1_NATIVE_ARTIFACTS.json). Exact original legacy stochastic module Git blobs `e6616d14f4b02bd447f872f2a67a444d83bc7df6` and `19aefcc2c01ff629f6da5778b12fa0d495a3b610` remain byte-identical. **There were no genuine native source compilation/test failures, so no model-source repair or replacement Git candidate was necessary.**

### Accepted public mathematical contracts

- **`kalman_bucy(A,Q,H,R,m0,P0,times,measurement_rates,rtol,atol)`**: deterministic DOP853 integration of the *continuous* Kalman–Bucy moment/Riccati equations for a held observed rate over each interval; returns means, covariances and observed numerical PSD/step diagnostics. It does **not** represent an exact pathwise continuous stochastic measurement increment.
- **`irregular_filter(A,Q,H,R,m0,P0,times,observations,initial_time,max_segment)`**: continuous generator/process diffusion exactly transformed to each irregular interval by the existing Van Loan transition, followed by a separate *discrete sampled* Joseph Gaussian sensor update when a real observation is present. An explicit `None` means a missing observation: prediction-only, never a fabricated sensor sample. Returns aligned prediction and posterior histories, NIS/log-likelihood and missingness.
- **`fixed_lag_smooth(filtered,lag)`**: observation-*event*-count lag RTS release using only events available at the release time, with explicit original state timestamps, release timestamps, pending tail and no future beyond that release. It is **not** a fixed-duration-in-seconds smoothing API, and not the original offline full-future RTS.

These are explicitly bounded numerical research interfaces, maximum 8 states/8 sensors and 256 observation events. All returned receipts are `execution_authorized=False`, `certified=False`; covariance PSD checks and tiny numerical projections are not proofs of global mathematical positivity or model correctness under arbitrary physical misspecification. No installed MEL/native agent grant or source-backed forecasting supremacy is conferred.

### Independent local supplementary mathematical audit (not misrepresented as exact SHA)

A **separate local earlier working copy with a different Git blob**, not the exact accepted published SHA, passed 18 focused tests plus 40 independently constructed random two-state dynamics, 320 Gaussian *batch-conditioned* causal prefix fixed-lag release checks, and seven analytic nonstationary scalar Riccati references, with largest observed numerical disagreement around `1.3e-15`. This supportive analysis is **not** counted toward accepted native CI/JUnit and is not used to assert cross-platform identity. The native unchanged source tests and original ZIPs alone establish R2-R1 exact-source acceptance.

**R2-R1 disposition: CLOSED for native mathematical implementation/portability, OPEN for production MEL integration and future stochastic improvements.** Next engine development: **COG-05-SSM-04-R3** — mathematically consistent continuous Brownian observation *increment* handling with stable square-root covariance propagation and independently checked conditional moments. Later: time-duration-based fixed-lag smoothing, robust/information backends, installed MEL permissions, physical-source uncertainty and nonlinear SSM extensions. The one-time automatic R2 CI push trigger is retired; the original test workflow remains manual-only.
