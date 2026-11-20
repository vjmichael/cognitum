# COG-05-SSM-04 — Stochastic dynamics and probabilistic state estimation

**Status:** locally qualified bounded research candidate, 28/28 dedicated tests and 63/63 available combined local tests. Native acceptance pending; no production/control authorization. Same staged research branch as SSM-03-R1, parent 8bc236f51c6e21d41de1b9ae16c851140f78a14d.

## Mathematical implementation
- DS25: finite discrete Markov propagation with row-stochastic kernel, and continuous-time Markov model with validated generator and matrix-exponential transition. Probability mass and nonnegativity diagnostics; dimension/time limits. Floating, not exact rational or general state-space kernels.
- DS26: scalar Ornstein–Uhlenbeck Itô model with analytic moments and analytic finite-step Gaussian transition, Euler–Maruyama coupled to the same Brownian increments via the integrated-noise conditional Gaussian. Seeded terminal ensembles and coupled RMSE; three-seed moment controls and refinement. No general nonlinear/multiplicative SDE solver, certified error, Fokker–Planck discretization or path-law guarantee.
- DS27: full covariance continuous linear drift with sampled Gaussian measurements, Van Loan block-exponential process covariance, arbitrary bounded positive intervals, missing entire observation, Cholesky innovation solve, Joseph covariance, likelihood and NIS. Batch Gaussian and coupled information-form analytical references. No continuous-measurement Kalman–Bucy, nonzero drift input or partial observation masks.
- DS28: covariance checks, Joseph update and Cholesky solves with PSD cleanup of numerical roundoff; not a square-root covariance propagator or information filter. Ill-conditioning limits/validation need broader qualification.
- DS29: offline full Rauch–Tung–Striebel smoother, explicitly future-dependent; independent joint Gaussian conditioning test. Fixed-lag smoothing and posterior path sampling open.
- DS30: scalar separable quadratic observation over a coupled Gaussian prior, extended Kalman measurement update and spherical-radial cubature measurement update. Linear-limit parity and analytical cubature fixture; not arbitrary nonlinear transition, nonlinear sequence filter, general UKF or validated posterior accuracy.
- DS31: bootstrap particle filtering for linear Gaussian transitions and observations, user-supplied initial particles, independent seeded Gaussian innovations, log-space weights and systematic ESS-triggered resampling; missing observations and posterior mean. Exact finite two-point posterior and three independent Gaussian Monte Carlo cases. General nonlinear likelihood/transition, ensemble Kalman, genealogy and calibrated convergence studies open.
- DS32: categorical HMM log-space forward, backward smoothing, Viterbi and likelihood with impossible-emission refusal, compared to finite exact enumeration. Future-dependent outputs marked; switching LDS, regime parameter fitting, label permutation and broader tests open.

Research output explicitly uncertified; no execution authorization. NumPy/SciPy only, CPU-first. DS25–32 partial, not blanket accepted. DS33+ remain queued.

## Actual local evidence
Python 3.13, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, one-thread BLAS/OMP. Local workspace contains new source/test and the prior exact SSM-03-R1 isolated source/test; not the full repository. Dedicated 28 passed in 0.64 s; combined 63 passed in 0.87 s (35 prior plus 28 new); no skips/errors/failures on final runs. These are test elapsed times, not performance benchmarks.
Initial combined run 60 pass/3 fail: Gaussian particle fixtures reused the same seeded stream for initial particles and innovations, introducing correlation not present in the reference model. Corrected fixture to seed+1000 for initial particles; kept tolerance and filter unchanged. Final test/source Git blobs verified against published bytes.

- Source blob e6616d14f4b02bd447f872f2a67a444d83bc7df6; SHA256 d65737dbd0c31e82fcfa5689998de0ff57fb78f87cbbeb2f0d688f454c6e4b46.
- Test blob 5da5e7c5a7e41346a279f82d2490b87246ee592f; SHA256 42cfab12fae3f06248c536b31ecaae8d4b81439cfedf14d0d61749d9c04e6beb.
- Dedicated JUnit SHA256 d22d2d5d7c45d31bc57176c9a7273516ebe1c49889da6dd1084f0b70d9b60f63; combined SHA256 d23fb1fec87b3a14dfebcd34f412aa9776c34be2c5fcaf7a764c146949b88713.

## Native acceptance and residual
New sequential gate consumes the same-head SSM-03-R1 receipt (39 dedicated tests), verifies source pins and prior artifact hashes, runs 28 no-skip tests, preserves receipt/log/XML. No overlapping CI submitted by this task; main remains unchanged. Parent native and real KAN checkpoint integration still require reconciliation; full repository regressions not executed here. Next independent task SSM-04-R1: general bounded nonlinear stochastic dynamics, nonlinear sequence filtering/UKF, robust square-root and information filters, fixed-lag smoothing/posterior sampling, particle/ensemble and switching-state extensions. SSM-05 identification remains queued.
