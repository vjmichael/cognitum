# COG-05-SSM-04-R3 — Stochastic measurement increments and QR square-root covariance

**Status: ACCEPTED exact native mathematical source (5/5 jobs) — original SHA `1b29d6376a22308235f69de4706fafdd01af2490`.** A new native CPU mathematical engine, not an Orc Graph benchmark or installed MEL authority. R2's original three APIs and accepted source are unchanged.

## Mathematical model and precise observation contract

State and continuous sensor model, independent standard Wiener processes W and V:

`dx_t = A x_t dt + Q^(1/2) dW_t`
`dY_t = H x_t dt + R^(1/2) dV_t`

The new `kalman_bucy_increments(A,Q,H,R,m0,P0,times,increments,initial_time=0.0)` accepts **actual integrated sensor increments** `increments[i] = Y(t[i])-Y(t[i-1])`. They are neither instantaneous point samples nor deterministic held sensor rates. The matrices Q and R are *continuous covariance rates*, not measurement-noise variance for a discrete sample. `None` means the entire interval increment is missing and is never silently replaced by zero.

For each finite interval Δt, introduce the observation accumulator `z(t) = ∫H x_s ds + ∫R^(1/2) dV_s` with augmented generator `[[A,0],[H,0]]` and diffusion covariance-rate `diag(Q,R)`. Use an exact finite-interval matrix exponential / Van Loan integrated covariance for joint random variables `(x_end, z_end)`. Condition their Gaussian distribution on the **actual z_end increment**, including the process-noise/measurement-increment cross-covariance. Reset the sensor accumulator exactly to zero at every interval, propagate the filtered state forward, and do not reveal later measurements.

**Important scientific boundary:** the finite-interval posterior is exact under a linear Gaussian SDE and the *given integrated interval increments*, subject to floating-point numerical approximation. It is **not** the exact posterior given the *entire* continuously observed sensor path inside an interval. A finer increment partition approaches the continuous-observation Kalman–Bucy Riccati limit; the implementation does not infer an unobserved Brownian path from a coarse increment, claim a physical observation process, or misrepresent a held `dY/dt` as genuine stochastic data.

## Stable square-root method

Both new estimators track square-root factors `S` such that covariance `P=S S^T`. Correlation-correct joint conditioning uses observation root `Ly`, state root `Lx`, gain `K=Lx Ly^T (Ly Ly^T)^(-1)` via bounded positive-definite Cholesky solves, and posterior factor `QR_root(Lx-K Ly)`. Thus the conditioned covariance is positive semidefinite **by factor reconstruction**, without subtracting two nearly equal dense covariance matrices. Tiny negative Van Loan noise eigenvalues from roundoff may be clipped with explicit diagnostic counts; materially negative covariance and singular/ill-conditioned innovations are refused. **These are numerical protections, not a formal global PSD certificate or exact arithmetic guarantee.**

Second public interface `square_root_sampled_filter(A,Q,H,R,m0,P0,times,observations,initial_time=0.0)` is a separate bounded QR Joseph/Van Loan implementation for **instantaneous discrete Gaussian sensor samples at real irregular timestamps**. It reuses original R2 sampled measurement semantics and outputs aligned `means, covariances, predicted, predicted_cov, transitions, factors, predicted_factors, nis, log_likelihood`. Its history is compatible with the accepted R2 `fixed_lag_smooth`.

**No unsafe interchange:** a continuous *integrated-increment* filter output is deliberately not compatible with the original R2 fixed-lag smoother, whose backward conditional transition assumes independent endpoint sensor noise. Integrated process/measurement increments are correlated and require a distinct future backward-lag recursion, not invented smoothing results.

## Execution boundaries

- At most **8 state dimensions, 8 sensor dimensions, 256 increments/samples**, total time 256 model time units, any single gap at most 16 units; generator-time matrix magnitudes bounded.
- Covariance rates `Q` semidefinite and `R` strictly positive definite, independent state and sensor Wiener drivers, condition-number refusal for ill-conditioned innovations.
- Explicit `nis`, Gaussian interval log-likelihood, actual missing increments and explicit `imputed_missing_increments=0`, chronological state means/covariances and QR factors, numerical roundoff-clipping counts.
- Every receipt retains `certified=False`, `execution_authorized=False` and `uses_future=False`. No installed actuator, raw sensor provenance, calibration under physical model mismatch, Brownian path reconstruction or numerical enclosure claimed.
- New research module is isolated as `cognitum/research/ssm_stochastic_increments.py`. The original accepted `ssm_stochastic.py`, `ssm_stochastic_extended.py`, `ssm_stochastic_continuous.py` and all prior test files are unchanged.

## Qualification and synthetic independent correctness

A local source-locked research working copy of this new module and test file, each compared byte-for-byte through their original **Git blob hashes** with the GitHub candidate, passed **71/71 focused tests**, comprising 18 original R2 tests and **53 new R3 tests**. Original independent R3 checks include:

- Scalar closed-form integrated posterior mean/variance/likelihood with and without Brownian process noise, including its analytic process/measurement cross-covariance (term `Q*dt**2/2`).
- Independently integrated coupled mean/covariance ODE rather than reusing the implementation's Van Loan block exponential.
- 16 deterministic-random two-state independent SDE joint moment ODE comparisons, and 12 randomized sampled QR/reference R2 filter checks, plus coupled multivariate noise tests.
- Fine-partition convergence toward analytic `P(t)=tanh(t)` Riccati covariance, explicitly identifying finite-coarse bin error.
- Consistent QR factor reconstruction under semidefinite/near-singular states and diffusion; positivity checks without subtractive posterior covariance update.
- Proper negative/refusal behavior for nonincreasing/NaN/too-large clocks, wrong dimension, singular R, dangerously unstable generator; no hidden zero imputation or late measurement history rewrite.
- Preserved R2 source and interface compatibility for sampled smoothing; deliberate refusal to supply integrated increments to the endpoint-sensor RTS backward smoother.

The exact GitHub source identity for new source and 53 tests is protected by their original Git blobs:
`3eebcec1da8bae1cb3a65d33aab389c584cff89b`
and `ee311ead4b017e0e080f41cf412d22bfff0139b3`.
Original R2 accepted native source is `ee88fdb0a53af04603c51b41c30768bdc62f9c0d` and retained documentation closeout `24932c4faf12b0f4892571eb12463f4a287e2c0d`.

## Required native exact-source acceptance

One candidate branch `research/ssm04r3-stochastic-increments-20261121`. Four native Windows/Linux Python 3.11/3.13 source/JUnit jobs qualify previous `research_tests/ssm04`, `research_tests/ssm04r1`, `research_tests/ssm04r2` and new `research_tests/ssm04r3` with pinned NumPy/SciPy. A fifth independent job compares all four exact original Git source identities, JUnit test names/results and counts. No stacked workflows; automatically triggered R3 workflow retired after full acceptance. Preserve original failures and do not grant production or model-quality authority when completed.

## Remaining mathematical work

A discrete-time **backward smoother for integrated observations** correctly carrying correlated transition/measurement innovations, verified under joint Gaussian conditioning; direct continuous-path stochastic innovation filtering when genuinely time-resolved measurement increments are available; rank-aware/ill-conditioned information or square-root backends; fixed-duration smoothing; typed Mathematical Execution Layer/host-protected authorization; and extended nonlinear stochastic SSM. No Orc performance benchmark is necessary for R3 itself.


## R3 original exact-source native closeout (2026-11-21)

[Original five-job GitHub Actions run #44881781321](https://github.com/vjmichael/cognitum/actions/runs/44881781321) **PASS** at unchanged native source `1b29d6376a22308235f69de4706fafdd01af2490`. Windows/Linux Python 3.11/3.13 each **130/130 tests**, **520/520 total** with zero genuine failures, errors or skips; the fifth separate source/JUnit verification passed. All **five original GitHub Actions ZIP files independently downloaded and SHA-256 compared to official GitHub artifact digest**, ZIP CRCs passed, all four original JUnit test names and counts identical, and original six source/test Git blobs byte-identical across all native targets. [Accepted native original artifact manifest](SSM04_R3_NATIVE_ARTIFACTS.json). Local additional verification receipt: `ssm04r3_independent_native_evidence.json` (five ZIP digests + all test name/source identities). **No source repair was necessary**, and all accepted original SSM-04/R1/R2 code/tests remain unchanged.

The first local *test-only* finite-partition convergence expectation demanded an error below `1e-4` on a 20-bin integration when observed error was `1.23e-4`. It was resolved by evaluating 40 bins against the same unchanged analytically known `tanh(t)` limit, not by changing the stochastic source, observation model or broadening a score threshold. The final 71/71 local focused tests and source-matched 520/520 genuine native tests pass. This was an explicitly accounted local test precision issue, **not a native platform failure**.

Finalized interfaces:

- `kalman_bucy_increments(...)`: exact finite-interval **aggregated stochastic observation increment** conditional model, including process–sensor covariance, with QR-factor posterior and honest absence of full continuous-path claim.
- `square_root_sampled_filter(...)`: independently qualified irregularly timestamped **instantaneous measurement** Gaussian sampled filter, with QR-root noise propagation and R2 causal fixed-lag smoother compatibility, explicitly distinct from the increment API.

The one-time R3 automatic CI trigger was retired after acceptance; original workflow remains manually runnable. Numerical covariance/likelihood receipts are not independently certified interval-arithmetic proofs. Installed MEL custody and actual physical sensor provenance remain open. **Next engineering R4:** derive and qualify the missing **integrated-increment correlated-noise backward smoothing**, with exact finite-interval conditional references, rather than using the independent-noise endpoint RTS recursion.
