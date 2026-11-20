# COG-05-SSM-06 — Offline feedback and optimal control mathematics

**Status:** bounded research candidate. 30/30 dedicated and 175/175 available combined local tests passed. Native qualification pending. Parent 3691bb60f0a280b77d654398fdb0d8a2f04323db. CPU-first NumPy/SciPy, no new dependencies or actuation authority.

## Mathematical scope
- DS41: discrete Luenberger observer, known input and noiseless measured output, gain via dual pole placement and explicit error dynamics A-LC. Checks observable rank and stable distinct real poles; refuses deficient systems. Unknown-input observers and uncertain measurements remain open.
- DS42: discrete state feedback pole placement with controllability rank and eigenvalue residual; infinite-horizon LQR via DARE with independently recomputed Bellman/Riccati residual, PSD value and Schur stability checks; finite-horizon LQR via backward dynamic programming and simulated cost agreement. Scalar closed-form reference controls and unstabilizable refusal. No continuous, nonlinear, repeated/complex pole synthesis or general numerical certification.
- DS43: stationary discrete LQG predictor feedback with independent Gaussian process/measurement draws and separate seeded simulation; dual Riccati covariance and predictor gain, augmented state/error matrix triangular separation, independent pole comparison and scalar gain reference. Limited to supplied linear time-invariant Gaussian model and stated timing; no optimality or safety claim for arbitrary system/constraints.
- DS44: condensed finite-horizon linear-quadratic planning for symmetric state/input boxes; positive definite input cost, terminal quadratic cost, linear feasibility search and convex numerical QP solve, independent nonnegative active constraint multiplier fit and primal/stationarity/complementarity residual checks. Unconstrained parity against dynamic programming, active input and state constraints, unsafe initial state and infeasible case refusal. This is the predictive optimization core, not a deployed receding-horizon controller, recursive feasibility proof, general planning adapter or exact optimality certificate.
- DS45/48: exact rational sufficient robust invariant-box witness for a supplied discrete feedback u=-Kx, with independent componentwise bounded additive disturbance. Checks |A-BK|b+w<=b and |K|b<=input bound with exact fractions; returns rational margins or refuses. This certifies only the declared model/box/feedback, not plant fidelity, safety outside the box, robust optimal synthesis, chance constraints or general reach-avoid/safety filters.
- DS46/47 remain open: adaptive/data-enabled predictive control and experiment/sensor optimization.

All outputs are research-only and do not grant execution authorization. Numerical tests are not physical validation. DS41–45/48 partial.

## Actual local qualification
Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2; one-thread BLAS/OMP/MKL. 30 dedicated tests in 0.89 s and 175 available combined in 2.83 s; zero failures/errors/skips. Combined run included 145 inherited cases, excluded the unavailable full KAN runtime cases explicitly and did not execute full repository or native Windows/Linux workflow. Available inherited source/test Git hashes matched previous pins. Test time is not a benchmark.
- Source Git blob 2fd5771352a6fadb2ff4b722d2519894b08c5c85, SHA256 6edfb6ebaaae4ac5d0eed0385c92df1fb8fb581a227764599a7507934306fcda.
- Test Git blob fbdd1d2d242a20c1a8c69a0ba2ae375688f8fe67, SHA256 2a1e30e5ff55e6c3bedaa650887ac83934be2d9ff6e5b4c51f6bab861e17a76c.
- Dedicated JUnit SHA256 b89ba2750905e210a4f94a6ed03032e23ef780a5184c2559c4217efd55c901d0.
- Combined JUnit SHA256 04a0bf96c9b1a4cdbe464c0c3f2b2a622ca3e4eb935c01c4a0d97c24bc056211.

## Native and next development
Sequential same-head gate consumes SSM-05-R1 receipt (25 tests including KAN integration), verifies cumulative source pins and prior artifact hashes, runs 30 dedicated tests and preserves receipt/log/XML. Source and test blobs match published candidate. No overlapping CI launched; existing staged branch retained, main unchanged by this task. Prior KAN and native acceptance remain open.
Next independent SSM-06-R1: unknown-input observation, receding-horizon simulation, robust and chance-constrained planning, adaptive/data-enabled control, optimal experiment design/sensor selection, safety-filter and reach-avoid certificate checks, and planning interoperability. Offline only; no external actuation.
