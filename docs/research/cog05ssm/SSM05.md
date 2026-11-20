# COG-05-SSM-05 — Statistical inference and mathematical model discovery

**Status:** bounded local research candidate; 28/28 dedicated and 122/122 available combined local tests. Native qualification pending. Parent staged candidate 4bc93018c51c917daa19ecf7014df5b072507ea7. CPU-first NumPy/SciPy, no new dependencies, no execution authority.

## Implemented profiles
- DS33: iid scalar normal MLE for mean and positive variance, closed-form log likelihood and normal-inverse-gamma conjugate posterior with parameter uncertainty. Scalar Gaussian mixture EM (2–4 components), variance floor, log-sum-exp responsibilities, component-collapse refusal and likelihood monotonicity diagnostic. Local optimization only; general state-space likelihood optimization, HMM/LDS EM and posterior intervals remain open.
- DS34: fully observed discrete linear model x_next=A x+B u by SVD-checked least squares, joint excitation/rank condition and independent supplied held-out prediction error. No latent-state uniqueness, errors-in-variables correction or arbitrary trajectory identification.
- DS35: SISO/MIMO eigensystem realization algorithm from impulse Markov parameters, paired block Hankel matrices, SVD rank/gap check with supplied order, recovered realization and impulse residual. State coordinates only defined up to similarity. No noisy order selection or stochastic subspace identification.
- DS36: bounded degree 1–3 polynomial library and sequential thresholded least squares SINDy with supplied derivative data, explicit exponent/coefficients and held-out derivative residual. Noise and wrong-library controls. No automatic derivative reconstruction, general symbolic search or unique governing equation claim; independent KAN comparison still open.
- DS37: full-rank DMD and polynomial EDMD regression with eigenvalues and held-out lifted observable prediction residual. Invariant linear example and a noninvariant-dictionary counterexample. Not a proof of global finite Koopman closure or low-rank/noisy spectral consistency.
- DS38: polynomial operator inference with optional Euclidean quadratic conservation x^T f(x)=0 imposed via coefficient constraint null space. Floating coefficient identity residual (not exact proof) rather than sample penalty; clean/noisy recovery and deliberately incompatible dissipative system. No general Hamiltonian, metric, dissipative, reduced-basis or port constraints yet.

DS33–38 partial, no physical validation or autonomous control authority. DS39–40 and residual DS33–38 remain for extension.

## Actual local results
Initially 25/28 passed; three noisy-LTI tests had incompatible held-out state/control row counts (256 versus 80). Corrected fixtures to use matched 80-row independent held-out arrays, no implementation or tolerance change. Final 28/28 dedicated (0.25 seconds) and 122/122 combined (1.02 seconds), no failures/errors/skips. Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, pytest 9.0.2, one-thread OpenBLAS/OMP/MKL. Restored prior 35+28+31 isolated test and source blobs match the previously published pins. Not full repository or native Windows/Linux qualification. Test durations are not performance benchmarks.

- Source blob d474ec24c498beaa322c7f8ccebd4ae6a75bdb27; SHA256 045acd72c3cc8fb8a44fb9a5b464294a7dd50f90500fe6adb6872f9415262aae.
- Test blob 4817545f6be49b2dae01792d4f7392eeb9197e9b; SHA256 f8491a2b395481e08d8b36525c3ea4731d9d8854c12b59652b52b7eb1e913c60.
- Dedicated JUnit SHA256 197b39af9b03b2532e963ece752066f80cd81cf72dd5a056db0f99e5caf32b22.
- Combined JUnit SHA256 b50e6832d53286c20680554f90af2cb8fb48f502b2b87d762f93a6817c644713.

Published source and test blob identities match local tested bytes. Sequential same-head gate staged: verifies SSM-04-R1 prior receipt and 31-case inventory, cumulative source pins, prior internal artifact hashes, executes 28 dedicated cases and preserves receipt/log/XML. No separate CI launched. Existing branch retained; main unchanged by this task.

Next independent task: SSM-05-R1 likelihood/EM for latent-state models, richer identification and noisy subspace realization, trajectory/weak-form discovery, KAN cross-check, structured operator inference, statistical forecasting and calibrated change detection (DS33–40). Native closeout remains open.
