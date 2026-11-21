"""SSM-04-R3: continuous stochastic observation *increments* and QR covariance.

Linear Ito model: dx=A*x dt+Q^(1/2)dW, dY=H*x dt+R^(1/2)dV;
W,V independent Brownian motions. Each supplied dY is the actual integrated
sensor increment for its interval, NOT a held observation rate. Conditioning
on this integrated increment is exact for the finite-interval linear Gaussian
model, including correlated process/observation increments due to shared x.

Only the integrated increments are supplied: this is NOT conditioning on the
entire continuous observation path within an interval. Fine-grid increments
approach the continuous-path Kalman-Bucy filtering limit; no pathwise exactness
or certified roundoff enclosure is claimed. All paths use bounded CPU floats.

The companion square_root_sampled_filter handles discrete endpoint sensor
samples (different semantics). Its output supports the existing R2 causal
fixed-lag smoother. The increments filter must NOT be fed to that smoother:
its interval observation and process noises are correlated after integration.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.linalg import expm, cho_factor, cho_solve
from . import ssm_stochastic as core

MAX_N = 8
MAX_K = 8
MAX_STEPS = 256
MAX_TIME = 256.0
MAX_DT = 16.0


def _inputs(A, Q, H, R, m0, P0):
    A = core.square(A)
    n = len(A)
    core.need(n <= MAX_N, "state dimension budget")
    Q = core.cov(Q, n)
    H = core.array(H, 2)
    core.need(H.shape[1] == n and 1 <= H.shape[0] <= MAX_K,
              "measurement dimension budget")
    k = H.shape[0]
    R = core.cov(R, k, True)
    core.need(np.linalg.cond(R) <= 1e12, "ill-conditioned measurement noise")
    m = core.array(m0, 1)
    core.need(m.shape == (n,), "state mean shape")
    P = core.cov(P0, n)
    return A, Q, H, R, m, P


def _grid(times, observations, initial_time):
    core.need(type(observations) in (list, tuple) and
              1 <= len(observations) <= MAX_STEPS, "increment/sample count")
    t = core.array(times, 1)
    core.need(t.shape == (len(observations),), "timestamp/sample alignment")
    core.need(type(initial_time) in (int, float) and
              math.isfinite(initial_time) and 0 <= initial_time < t[0] and
              np.all(np.diff(t) > 0) and t[-1] - initial_time <= MAX_TIME,
              "causal strictly increasing timestamps")
    d = np.diff(np.r_[float(initial_time), t])
    core.need(np.all(d > 0) and np.all(d <= MAX_DT),
              "bounded continuous-time interval")
    return np.r_[float(initial_time), t], d


def _vector(x, n):
    v = core.array(x, 1)
    core.need(v.shape == (n,), "observation increment shape")
    return v


def _psd_root(M, *, title):
    """Symmetric nonnegative noise factor; only tiny roundoff negatives clipped."""
    M = np.asarray(M, dtype=float)
    core.need(M.ndim == 2 and M.shape[0] == M.shape[1] and
              np.isfinite(M).all(), f"{title} finite square covariance")
    M = (M + M.T) / 2
    w, V = np.linalg.eigh(M)
    scale = max(1., float(np.max(abs(w))))
    core.need(float(w[0]) >= -1e-11*scale,
              f"{title} materially negative covariance")
    # Zero eigenvalues are legitimate: deterministic/partially observed states.
    L = V * np.sqrt(np.maximum(w, 0.))
    core.need(np.isfinite(L).all() and np.max(abs(L)) <= 1e8,
              f"{title} covariance factor magnitude")
    return L, int(np.count_nonzero(w < 0))


def _qr_root(B):
    """Return lower square root of B B^T without subtractive covariance update."""
    B = np.asarray(B, dtype=float)
    core.need(B.ndim == 2 and 1 <= B.shape[0] <= MAX_N and
              B.shape[1] >= B.shape[0] and np.isfinite(B).all(),
              "square-root QR factor budget")
    _, R = np.linalg.qr(B.T, mode="reduced")
    lower = R.T
    # QR is sign-indeterminate; canonicalize columns, including rank-deficient.
    lower = lower * np.where(np.diag(lower) < 0, -1.0, 1.0)
    core.need(np.isfinite(lower).all() and np.max(abs(lower)) <= 1e8,
              "square-root factor overflow")
    return lower


def _van_loan(A, Q, dt):
    """Exact finite-interval linear SDE transition and process Gramian."""
    n = len(A)
    core.need(0 < dt <= MAX_DT and np.max(abs(A))*dt <= 80.,
              "unstable or unbounded continuous generator/time")
    Z = np.zeros((n, n))
    V = expm(np.block([[A, Q], [Z, -A.T]]) * dt)
    F = V[:n, :n]
    W = (V[:n, n:] @ F.T)
    core.need(np.isfinite(F).all() and np.max(abs(F)) <= 1e8 and
              np.isfinite(W).all() and np.max(abs(W)) <= 1e8,
              "continuous process transition overflow")
    L, clipped = _psd_root(W, title="Van Loan process noise")
    return F, L, clipped


def _condition_qr(prior_mean, Lx, expected_obs, Ly, observed):
    """Joint Gaussian conditioning via innovation Cholesky and QR Joseph factor.

    Lx*Lx.T is Var(x), Ly*Ly.T Var(Y), Lx*Ly.T is Cov(x,Y).
    The covariance factor of x|Y is QR-root(Lx-K Ly), hence PSD without
    subtracting two similar covariance matrices.
    """
    k = len(observed)
    C = Ly @ Ly.T
    core.need(np.isfinite(C).all() and np.linalg.cond(C) <= 1e12,
              "integrated/sampled innovation condition")
    cho = cho_factor((C+C.T)/2, lower=True, check_finite=True)
    cross = Lx @ Ly.T
    K = cho_solve(cho, cross.T).T
    innovation = observed - expected_obs
    mean = prior_mean + K @ innovation
    root = _qr_root(Lx - K @ Ly)
    nis = float(innovation @ cho_solve(cho, innovation))
    log_likelihood = -.5*(k*math.log(2*math.pi) +
                         2*np.log(np.diag(cho[0])).sum() + nis)
    core.need(np.isfinite(mean).all() and np.max(abs(mean)) <= 1e8 and
              np.isfinite(log_likelihood), "conditioned stochastic mean overflow")
    return mean, root, nis, float(log_likelihood)


def kalman_bucy_increments(A, Q, H, R, m0, P0, times, increments,
                            *, initial_time=0.0):
    """Exact linear-Gaussian conditioning on each integrated dY interval.

    A,Q continuous state drift/covariance rate; H,R continuous sensor drift
    and Wiener covariance RATE. Each `increments[i]` is the sensor-integral
    Y[t_i]-Y[t_(i-1)] in observation units, NOT y_rate, NOT a sampled value.
    None = missing entire integrated interval. Returns lower QR factors.
    All Wiener drivers are assumed independent. No physical units inferred.
    """
    A, Q, H, R, m, P = _inputs(A, Q, H, R, m0, P0)
    clock, dts = _grid(times, increments, initial_time)
    n, k = len(m), H.shape[0]
    Aaug = np.zeros((n+k, n+k))
    Aaug[:n, :n] = A
    Aaug[n:, :n] = H
    Qaug = np.zeros_like(Aaug)
    Qaug[:n, :n] = Q
    Qaug[n:, n:] = R
    S, clipped = _psd_root(P, title="initial state")
    means, roots, covs = [m.copy()], [S.copy()], [S@S.T]
    missing, nis, steps, correction_count = 0, [], [], clipped
    ll_total = 0.
    for dt, delta in zip(dts, increments):
        M, Lw, c = _van_loan(Aaug, Qaug, float(dt))
        correction_count += c
        # Accumulator always resets to exactly zero at EACH observed interval.
        Fx = M[:n, :n]
        Fy = M[n:, :n]
        expected_x = Fx @ m
        expected_y = Fy @ m
        Lx = np.column_stack((Fx @ S, Lw[:n, :]))
        Ly = np.column_stack((Fy @ S, Lw[n:, :]))
        if delta is None:
            missing += 1
            m, S = expected_x, _qr_root(Lx)
            nis.append(None)
        else:
            y = _vector(delta, k)
            m, S, z, ll = _condition_qr(expected_x, Lx, expected_y, Ly, y)
            nis.append(z)
            ll_total += ll
        means.append(m.copy()); roots.append(S.copy()); covs.append(S@S.T)
        steps.append(float(dt))
    return core.receipt(
        method="exact_integrated_stochastic_observation_increment_conditioning",
        observation_semantics="continuous_integrated_Itô_measurement_increments_not_rates",
        times=clock, elapsed_dts=np.asarray(steps),
        means=np.asarray(means), covariances=np.asarray(covs),
        factors=np.asarray(roots), nis=tuple(nis),
        log_likelihood=float(ll_total), missing_increments=missing,
        imputed_missing_increments=0, numerical_eigen_clips=correction_count,
        conditioned_on_full_continuous_sensor_path=False,
        finite_interval_joint_Gaussian_conditional_exact=True,
        covariance_psd_by_QR=True, covariance_globally_certified=False,
        uses_future=False)


def square_root_sampled_filter(A, Q, H, R, m0, P0, times, observations,
                               *, initial_time=0.0):
    """Irregular instantaneous samples with Van Loan + QR Joseph square root.

    Intended to preserve R2 `fixed_lag_smooth` history compatibility. Unlike
    the integrated increment method, these sensor errors are independent of
    the process noise preceding each instantaneous endpoint observation.
    """
    A, Q, H, R, m, P = _inputs(A, Q, H, R, m0, P0)
    clock, dts = _grid(times, observations, initial_time)
    n, k = len(m), H.shape[0]
    S, c = _psd_root(P, title="initial state")
    LR = np.linalg.cholesky(R)
    means, roots, covs = [m.copy()], [S.copy()], [S@S.T]
    predicted, pred_roots, pred_cov, Fs = [], [], [], []
    missing, nis, ll_total, eigen_clips = 0, [], 0., c
    for dt, obs in zip(dts, observations):
        F, Lw, clips = _van_loan(A, Q, float(dt))
        eigen_clips += clips
        m = F @ m
        Sprior = _qr_root(np.column_stack((F @ S, Lw)))
        predicted.append(m.copy()); pred_roots.append(Sprior.copy())
        pred_cov.append(Sprior @ Sprior.T); Fs.append(F)
        if obs is None:
            S = Sprior
            missing += 1
            nis.append(None)
        else:
            y = _vector(obs, k)
            # Observation noise is independent of prior state and process.
            Lx = np.column_stack((Sprior, np.zeros((n, k))))
            Ly = np.column_stack((H @ Sprior, LR))
            m, S, z, ll = _condition_qr(m, Lx, H @ m, Ly, y)
            nis.append(z); ll_total += ll
        means.append(m.copy()); roots.append(S.copy()); covs.append(S@S.T)
    return core.receipt(
        method="QR_square_root_Van_Loan_Joseph_sampled_filter",
        observation_semantics="irregular_instantaneous_samples_not_continuous_rates",
        times=clock, means=np.asarray(means),
        covariances=np.asarray(covs), factors=np.asarray(roots),
        predicted=np.asarray(predicted), predicted_cov=np.asarray(pred_cov),
        predicted_factors=np.asarray(pred_roots), transitions=np.asarray(Fs),
        nis=tuple(nis), log_likelihood=float(ll_total),
        missing_samples=missing, imputed_missing_samples=0,
        numerical_eigen_clips=eigen_clips, covariance_psd_by_QR=True,
        covariance_globally_certified=False, uses_future=False)
