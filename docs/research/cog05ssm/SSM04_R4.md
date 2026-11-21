# COG-05-SSM-04-R4 — Integrated-increment fixed-lag smoothing with correlated noise

**Status (2026-11-21): IMPLEMENTED as isolated research candidate; local synthetic qualification 26/26 PASS; original unchanged-SHA Windows/Linux qualification PENDING.** Do not treat this as installed MEL execution, scientific certification, or a reason to alter already accepted R3.

## Correct finite-interval model

Use a linear Itô SDE with jointly Gaussian driving increments:

```text
dx(t) = A x(t) dt + dW(t)
dY(t) = H x(t) dt + dV(t)
Cov([dW, dV]) = [[Q, N], [N.T, R]] dt
```

The cross-rate `N` is a state-dimension by sensor-dimension matrix. The full block rate covariance **must be PSD**. `Q` may be semidefinite and `R` is strictly PD. `N=None` recovers independent Brownian drivers, but the **integrated process and observation increments can still be correlated** through the integrated state, even when `N=0`.

The observation for interval i is the true integrated `deltaY_i=Y(t_(i+1))-Y(t_i)`, not a sampled endpoint measurement, held rate or full continuous path. `None` skips conditioning on this interval and never imputes an increment of zero. Use the exact augmented Van Loan covariance for `(x_(i+1), deltaY_i)`; the observation accumulator is reset every interval.

## Mathematically correct backward recursion

Define the locally conditioned adjacent state pair

```text
(u_i, u_(i+1), L_i) represent
  (x_i, x_(i+1)) | deltaY_1, ..., deltaY_(i+1)
with pair covariance L_i @ L_i.T.
```

After conditioning both states on the **same interval increment**, partition `L_i` by rows into `Lold` and `Lnew` and calculate

```text
B = (Lold @ Lnew.T) @ pinv(Lnew @ Lnew.T)
m_(i|end) = u_i + B @ (m_(i+1|end) - u_(i+1))
residual_root = Lold - B @ Lnew
smooth_root = QR_root([residual_root, B @ smooth_next_root])
```

The pseudoinverse is rank-aware for semidefinite filtered states; significant ill-conditioning and nonfinite inputs are refused. The conditional residual and downstream uncertainty are composed as **QR factors** rather than subtracting near-equal covariance matrices. This recursion follows from adjacent conditional Gaussians, not the ordinary RTS formula `P_i F.T (F P_i F.T + W)^-1`, whose independence assumption is false for the integrated measurement update.

Only observations through the requested release event `i+lag` influence each output. `lag=0` reproduces causal filtering; a positive lag leaves that many newest states pending. Lag is in **increment events**, not elapsed seconds. The method does not retrospectively rewrite previously released state estimates.

## Interfaces and scope

- `correlated_increment_filter(A,Q,H,R,m0,P0,times,increments,*,noise_cross=None,initial_time=0.0)` saves chronological filtered means, PSD factors, adjacent joint-pair means/factors, missing-interval counts, log-likelihood and cross-rate provenance.
- `fixed_lag_increment_smooth(filtered,lag)` releases bounded causal fixed-lag estimates, state/release timestamps, covariance and QR roots, and leaves trailing states pending.
- Inherited R3 bounds: <=8 state dimensions, <=8 sensor dimensions, <=256 increments, interval <=16 time units, total horizon <=256; R4 lag <=64 increment events.
- R2 instantaneous-sample smoother remains separate and deliberately refuses the new integrated-increment receipt. R3 accepted modules/tests remain unchanged.
- Numerical PSD construction is **not** a global interval-arithmetic guarantee. Only finite-interval integrated increments are conditioned on; no full-path stochastic observation, physical calibration, installed sensor custody or MEL execution authorization is claimed.

## Evidence and outstanding qualification

Local Linux research harness: **26/26** focused tests passed, using source byte-identical R4 module/test files and local interface-equivalent R3 helpers. It does **not** establish exact original R3 dependency byte identity. The source and test Git blobs matched on local and GitHub:

- `cognitum/research/ssm_stochastic_smoothing.py`: `bc657af3ba28474c72bbb34376739f6bdef82106`
- `research_tests/ssm04r4/test_correlated_smoothing.py`: `f9cc09a3a54308135d6f25f63904d18d0d3ff6f8`

The tests check: analytic one-interval correlated Brownian covariances; independent ODE-built, full joint-Gaussian conditioning with several lags and irregular timestamps; 12 randomized correlated multibin systems; missing increments; prefix/release noninterference; QR PSD reconstruction; rank-deficient state; invalid non-PSD noise cross-rate; receipt tampering; R3 compatibility when `N=0`; and refusal of interchange with the sampled R2 smoother.

**Unresolved:** Execute the manually dispatched `.github/workflows/ssm04r4-native.yml` on real Windows/Linux Python 3.11/3.13 and independently reconcile the original JUnit records and exact Git blobs. Workflow is intentionally **manual-only** to avoid stacking CI. Repair only genuine failures; no mainline merge or installed-authority claim before native acceptance.

**Suggested next task:** `COG-05-SSM-04-R4-R1` — qualify exact committed source across four native targets; reconcile mathematical failures and source receipts; then close R4 if genuinely accepted.
