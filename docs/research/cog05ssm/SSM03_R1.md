# COG-05-SSM-03-R1 — Extended scientific dynamics

**Status:** bounded local numerical candidate; 35/35 isolated tests passed, 4 real KAN checkpoint cases staged but not executed locally. Full inherited SSM suite and native Windows/Linux acceptance not executed in this session. Parent SSM-03 native acceptance not verified. Research only; no execution authority or production promotion.

## Implemented scope
- DS20: homogeneous semi-explicit linear index-1 DAE with E=diag(I,0), invertible algebraic block elimination, initial consistency and residual checks. Ordered linear hybrid modes with directional affine guards, resets, event and trajectory refinement, max eight modes. No cyclic graph, simultaneous guard arbitration, general invariant checking, nonlinear/high-index DAE or certified event completeness.
- DS21: single constant positive delay, retarded linear DDE, constant vector history, method of steps with dense preceding segment interpolation and mesh/tolerance refinement. Distributed, variable and neutral delays and general history remain open.
- DS22: finite-dimensional diffusion M u'=-K u and wave M u''=-K u; symmetric positive mass, PSD stiffness, generalized modal evolution including zero-frequency modes, independent matrix-exponential numerical comparison and energy diagnostic. KAN adapter calls existing COG-04P exact assembly, records canonical assembly SHA-256 and rejects time-dependent trial bases. Four genuine checkpoint tests staged; actual continuum guarantees, general boundary/time-dependent operators and native KAN integration not qualified.
- DS23: Euclidean POD/Galerkin with snapshot reconstruction and independent held-out original trajectory errors; square-root balanced truncation for strictly stable minimal well-conditioned continuous LTI, Lyapunov residual checks, separated truncation boundary, reduced stability and estimated classical twice-discarded-Hankel-singular-value bound. Neither floating error bound nor sampled transfer checks are certificates.
- DS24: symmetric nonnegative weighted graph Laplacian, mass and diffusion diagnostics, partitioned RHS integration compared to monolithic matrix exponential; coupled oscillator modal energy case. Multirate, distributed execution, directed graphs and multiscale coupling remain open.

Input and trajectory budgets, no new dependencies (NumPy/SciPy), CPU-first. Numerical results explicitly uncertified. No prior kernel edits. No physical-system validation claims.

## Local receipt
Python 3.13.5, SciPy 1.17.0; one-thread BLAS/OMP. Command: python -m pytest -q research_tests/ssm03r1 (only the isolated test_extended.py was present locally). 35 passed in 0.62 seconds, zero failures/errors/skips. This is test elapsed time, not performance benchmarking. The source and isolated test blobs published on this branch match the local Git blob identities.

- Source blob 51545521268402c5313e933e246d4a3045bf556b; SHA-256 163edeaa92272515ac712636c7e9f13a8992462a1ba56bd4c86fb040412e548b.
- Local test blob 5ba573dec4152eea99e6f2580e0bad2c77a36493; SHA-256 dff144b1e01115fdbaf7943112fc334c91d103818dc25d8119ba8995092aeb1a.
- Local JUnit SHA-256 f28b1ef6df86018e5e030c31848f1e386711254a19b6c33f3730fd5c3f6912a4.
- KAN test blob 779ef5114edb79cd8ff9f6032a6233cdc6bd7751; not locally run.

## Native closeout
Separate research branch based on 1d331fa8ba839b3af012b7c203c4eaeca88ca3e1; no new CI batch launched. Existing regression extended with a same-head SSM-03 predecessor receipt and artifact integrity check, source pins and 39 dedicated no-skip cases, preserved native receipt. Reconcile predecessor acceptance and run the full native gate at unchanged candidate source before acceptance. DS20–24 remain partial. SSM-04 stochastic dynamics/filtering may be independent development after staged candidate reconciliation; no blanket completion.
