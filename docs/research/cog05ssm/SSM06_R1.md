# COG-05-SSM-06-R1 — Advanced offline control and mathematical safety

**Status:** bounded research candidate. 31/31 dedicated and 206/206 available combined local tests passed. Native qualification pending. Parent 8b5c156fef65b237e0c9b977be1d860794e8ce1d. No new dependencies or external execution authority.

## Mathematical implementation
- DS41: discrete full-order unknown-input observer for known disturbance coupling E and noiseless Cx observations. Requires full column rank CE and observability of (TA,C), T=I-E(CE)^+C. Numerical decoupling and error-dynamics checks; three seeded disturbance cancellation cases and rank refusal. General detectable-but-not-observable designs and noise robustness open.
- DS44: receding-horizon offline simulation re-solves the tightened QP each step from the simulated full state, verifies supplied disturbances respect declared bounds, and refuses invalid or infeasible runs. No recursive feasibility, closed-loop stability, terminal invariant-set synthesis or C11/C12 planning adapter established.
- DS45: finite-horizon open-loop robust state-box tightening by propagated absolute-matrix disturbance envelopes; linear Gaussian chance-constrained planning with known iid zero-mean additive covariance, deterministic full initial state and union-bound allocation over all state coordinates and horizon times. Numerical convex optimization and KKT residual checks. Exhaustive 64 disturbance-corner histories in coupled two-state fixture; three independent 20,000-trajectory Gaussian Monte Carlo checks. No parameter uncertainty, tube feedback, distributionally robust synthesis, repeated-horizon risk or exact numerical guarantee.
- DS46: offline certainty-equivalent adaptive simulation using expanding least-squares model fitting from observed state/control transitions, rank refusal and predictive planning. Direct full-state noiseless LTI trajectory-span planning via initial state and stacked controls, full-row-rank check and consistency residual, no explicit A/B fit. Comparison to independent model-based MPC at three horizons and noisy/deficient data refusal. No noisy DeePC, general latent outputs, adaptive robustness or convergence guarantee.
- DS47: finite D-optimal experiment subset enumeration with supplied linear sensitivities, noise variances and prior information; finite sensor subset selection with weighted observability Gramian. Deterministic rank checks, known optimal subset and deficient alternatives. Local linear model only; no general nonlinear experiment design.
- DS48: exact rational scalar safety filter selecting the closest feasible proposed action in a one-step robust state/input interval for known scalar linear dynamics and bounded disturbance. Rational margins, negative and zero input gains covered, unsafe initial/infeasible inputs refuse. Previous exact invariant-box witness remains separate. No arbitrary multivariate reach-avoid, long-horizon assurance or actuation.

DS41/44–48 remain partial; DS46 and DS47 newly initiated. All 56 initiated capabilities remain partial, 16 open. No blanket completeness or physical validation claims.

## Actual local evidence
Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2; one-thread OpenBLAS/OMP/MKL. 31 dedicated cases passed in 0.94 s, 206 available combined cases passed in 2.89 s (175 inherited). No executed failures, errors or skips. The full repository, prior KAN integration cases (excluded/unavailable) and native matrix were not executed. Times are test durations, not benchmarks.
- Source Git blob 50ef911a90c9eb6b94987ac57884c4919ac93d27; SHA256 c8c033f85a59f006d1257efdc83453a778b4d61c72e1fc1412f80d548b7891ec.
- Test Git blob 595736e74c590b08f797f25a9622fee0a9828275; SHA256 97044221e4d8e6e47d819d83080e67edcca0e449ae78932ac5f36900a8569098.
- Dedicated JUnit SHA256 98ac38df2ea071bca58ead5e7eb36d3b1c446725233c2dc35aa47de42c4a502b.
- Combined JUnit SHA256 48a505ff6404f53bcb916c3c42586e03afaf81453c2e2da5504f2bcb251b2aab.
Both new published blobs match locally tested bytes. One missing trailing semicolon in the initial published test was restored to match the tested blob; no functional change.

## Native and next development
Same-head sequential gate consumes SSM-06 receipt (30 cases), validates cumulative source pins and prior artifact hashes, and executes 31 dedicated cases with no skips. No overlapping CI initiated; existing staged branch retained, main unchanged by this task. Native and prior KAN closeout remain required.
Next independent SSM-07 — structured and selective learned state-space mathematics: HiPPO projection, recurrence/convolution, structured SSM kernels, selective input-dependent recurrence, stable parameterization and verified scan/gradient parity. No autonomous external execution.
