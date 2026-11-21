"""COG-05-SSM-04-R2: bounded continuous and irregular-time Gaussian estimation.

Research-only CPU numerical methods. kalman_bucy integrates continuous
Kalman-Bucy moment/Riccati ODE with a piecewise-constant observed measurement
rate. This is a deterministic finite-resolution rate approximation, not exact
pathwise white-noise SDE observation integration. irregular_filter uses exact
Van Loan continuous-to-discrete dynamics between sampled observations.
None denotes a missing entire sample. fixed_lag_smooth releases state i
after at most lag later samples; never assimilates anything after release.

No actuation, certified covariance enclosure or physical uncertainty guarantee.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import cho_factor, cho_solve
from . import ssm_stochastic as base

MAX_N = 8
MAX_K = 8
MAX_OBSERVATIONS = 256
MAX_SEGMENTS = 4096
MAX_HORIZON = 256.0

def _validated(A, Q, H, R, mean, covariance):
    A = base.square(A)
    n = A.shape[0]
    base.need(n <= MAX_N, "continuous engine state dimension budget")
    Q = base.cov(Q, n)
    H = base.array(H, 2)
    base.need(H.shape[1] == n and 1 <= H.shape[0] <= MAX_K,
              "continuous measurement matrix shape")
    R = base.cov(R, H.shape[0], True)
    base.need(np.linalg.cond(R) <= 1e12, "measurement covariance condition")
    mean = base.array(mean, 1)
    base.need(mean.shape == (n,), "initial mean dimension")
    covariance = base.cov(covariance, n)
    return A, Q, H, R, mean, covariance

def _times(values, n, *, allow_zero=True):
    t = base.array(values, 1)
    base.need(t.shape == (n,) and len(t) <= MAX_OBSERVATIONS + 1,
              "time grid dimensions or count")
    base.need(t[0] >= 0 and (allow_zero or t[0] > 0) and
              np.all(np.diff(t) > 0) and t[-1] - t[0] <= MAX_HORIZON,
              "time grid must be finite, strictly increasing and bounded")
    return t

def _finite_vector(x, n, label):
    y = base.array(x, 1)
    base.need(y.shape == (n,), f"{label} shape")
    return y

def _checked_covariance(P, *, title):
    P = np.asarray(P, dtype=float)
    base.need(P.ndim == 2 and P.shape[0] == P.shape[1] and
              np.isfinite(P).all(), f"{title} finite square matrix")
    P = (P + P.T) / 2
    vals = np.linalg.eigvalsh(P)
    scale = max(1.0, float(np.max(np.abs(vals))))
    base.need(vals[0] >= -1e-10 * scale,
              f"{title} materially negative eigenvalue")
    P = base.clean(P)
    base.need(np.isfinite(P).all() and np.max(np.abs(P)) <= 1e8,
              f"{title} magnitude budget")
    return P, float(vals[0])

def kalman_bucy(A, Q, H, R, m0, P0, times, measurement_rates,
                 *, rtol=1e-9, atol=1e-11):
    """Continuous Kalman-Bucy equations under held observed measurement rates.

    dx=A*x*dt+Q^(1/2)dW; dY=H*x*dt+R^(1/2)dV.
    On each interval the supplied observed dY/dt is held constant:
      dm/dt=A*m+P*H'R^-1*(dY/dt-H*m)
      dP/dt=A*P+P*A'+Q-P*H'R^-1*H*P.
    This approximates finite-resolution increments; it is NOT pathwise exact
    white noise nor an exact sampled-measurement conditioning update.
    """
    A, Q, H, R, mean, P = _validated(A, Q, H, R, m0, P0)
    base.need(type(measurement_rates) in (tuple, list) and
              1 <= len(measurement_rates) <= MAX_OBSERVATIONS,
              "continuous observation-rate budget")
    t = _times(times, len(measurement_rates) + 1)
    base.need(type(rtol) is float and type(atol) is float and
              1e-12 <= rtol <= 1e-4 and 1e-14 <= atol <= 1e-6,
              "explicit bounded integration tolerances")
    k, n = H.shape
    RiH = cho_solve(cho_factor(R, lower=True), H)
    info = H.T @ RiH
    means = [mean.copy()]
    covariances = [P.copy()]
    minima = [float(np.linalg.eigvalsh(P)[0])]
    solver_steps = []
    evaluations = [0]
    for index, rate in enumerate(measurement_rates):
        u = _finite_vector(rate, k, "continuous measurement rate")
        hu = H.T @ cho_solve(cho_factor(R, lower=True), u)
        delta = float(t[index + 1] - t[index])
        base.need(delta <= 32, "bounded continuous integration interval")
        state = np.concatenate((mean, P.ravel()))
        def rhs(_time, vector):
            evaluations[0] += 1
            base.need(evaluations[0] <= 100000,
                      "continuous solver evaluation budget")
            x = vector[:n]
            V = vector[n:].reshape(n, n)
            V = (V + V.T) / 2
            gradient = A @ x + V @ (hu - info @ x)
            riccati = A @ V + V @ A.T + Q - V @ info @ V
            return np.concatenate((gradient, riccati.ravel()))
        solution = solve_ivp(rhs, (float(t[index]), float(t[index + 1])),
                             state, method="DOP853", rtol=rtol, atol=atol,
                             max_step=min(0.25, delta / 2))
        base.need(solution.success and len(solution.t) <= 4096 and
                  np.isfinite(solution.y).all(),
                  "continuous Kalman-Bucy solver failed or exceeded budget")
        mean = _finite_vector(solution.y[:n, -1], n, "continuous posterior")
        P, min_eig = _checked_covariance(
            solution.y[n:, -1].reshape(n, n), title="continuous Riccati")
        means.append(mean.copy())
        covariances.append(P.copy())
        minima.append(min_eig)
        solver_steps.append(len(solution.t) - 1)
        base.need(sum(solver_steps) <= 8192,
                  "continuous solver total-step budget")
    return base.receipt(
        times=t.copy(), means=np.asarray(means),
        covariances=np.asarray(covariances),
        unprojected_min_eigenvalues=np.asarray(minima),
        solver_step_counts=tuple(solver_steps),
        solver_evaluations=evaluations[0],
        measurement_semantics="piecewise_constant_observed_rate_not_exact_SDE_path",
        method="Kalman-Bucy_Riccati_ODE_DOP853",
        covariance_psd_checked=True, covariance_globally_certified=False,
        uses_future=False, numerical_approximation=True)

def _interval_transition(A, Q, dt, max_segment):
    base.need(math.isfinite(dt) and 0 < dt <= MAX_HORIZON and
              0 < max_segment <= 1.0,
              "continuous-to-discrete elapsed-time budget")
    segments = max(1, math.ceil(dt / max_segment))
    base.need(segments <= MAX_SEGMENTS, "segment computation budget")
    h = dt / segments
    # Reuse accepted SSM-04 Van Loan covariance transition and compose
    # independent noise increments over a long interval.
    T, V = base.discretize(A, Q, float(h))
    n = A.shape[0]
    F = np.eye(n)
    W = np.zeros((n, n))
    for _ in range(segments):
        W, _ = _checked_covariance(T @ W @ T.T + V,
                                   title="continuous interval process noise")
        F = T @ F
    base.need(np.isfinite(F).all() and np.max(abs(F)) <= 1e8,
              "ill-conditioned interval transition")
    return F, W, segments

def irregular_filter(A, Q, H, R, m0, P0, times, observations,
                     *, initial_time=0.0, max_segment=1.0):
    """Causal continuous dynamics plus exact discrete Gaussian observations.

    Unlike continuous Kalman-Bucy observation rates, these are instantaneous
    sensor samples at strictly increasing real timestamps. None means no
    observation update. Van Loan gives continuous process covariance exactly
    up to floating-point numerical error; a measurement uses Joseph update.
    """
    A, Q, H, R, mean, P = _validated(A, Q, H, R, m0, P0)
    base.need(type(observations) in (tuple, list) and
              1 <= len(observations) <= MAX_OBSERVATIONS and
              type(initial_time) in (float, int) and
              math.isfinite(initial_time) and 0 <= initial_time <= MAX_HORIZON,
              "irregular sample grid/budget")
    t = _times(times, len(observations))
    base.need(t[0] > initial_time and t[-1] - initial_time <= MAX_HORIZON,
              "irregular samples must be strictly after bounded prior timestamp")
    base.need(type(max_segment) is float and .001 <= max_segment <= 1.0,
              "bounded integration segment")
    prior_time = float(initial_time)
    all_t = np.concatenate(([prior_time], t))
    posterior_means = [mean.copy()]
    posterior_covariances = [P.copy()]
    predicted_means = []
    predicted_covariances = []
    transitions = []
    innovations = []
    segment_counts = []
    log_likelihood = 0.0
    missing = 0
    total_segments = 0
    for j, at in enumerate(t):
        F, W, segments = _interval_transition(A, Q, float(at - all_t[j]),
                                               max_segment)
        total_segments += segments
        base.need(total_segments <= MAX_SEGMENTS,
                  "total irregular transition segment budget")
        mean = _finite_vector(F @ mean, len(mean), "predicted state")
        P, _ = _checked_covariance(F @ P @ F.T + W,
                                   title="irregular predicted covariance")
        predicted_means.append(mean.copy())
        predicted_covariances.append(P.copy())
        transitions.append(F.copy())
        segment_counts.append(segments)
        if observations[j] is None:
            missing += 1
            innovations.append(None)
        else:
            obs = _finite_vector(observations[j], H.shape[0],
                                 "sampled observation")
            mean, P, ll, nis = base.gaussian_update(mean, P, H, R, obs)
            mean = _finite_vector(mean, len(mean), "sampled posterior")
            P, _ = _checked_covariance(P, title="sampled posterior covariance")
            log_likelihood += ll
            innovations.append(float(nis))
        posterior_means.append(mean.copy())
        posterior_covariances.append(P.copy())
    return base.receipt(
        times=all_t, means=np.asarray(posterior_means),
        covariances=np.asarray(posterior_covariances),
        predicted=np.asarray(predicted_means),
        predicted_cov=np.asarray(predicted_covariances),
        transitions=np.asarray(transitions),
        nis=tuple(innovations), log_likelihood=float(log_likelihood),
        missing_samples=missing, imputed_missing_samples=0,
        segment_counts=tuple(segment_counts), total_segments=total_segments,
        covariance_psd_checked=True, covariance_globally_certified=False,
        uses_future=False,
        observation_semantics="irregular_instantaneous_samples_not_continuous_rates")

def fixed_lag_smooth(filtered, lag):
    """Online RTS: release x_i conditioned on observations up to i+lag only.

    Trailing lag states are pending. Lag counts sample events, not seconds.
    A released output at timestamp t_j uses no observation after t_j.
    """
    base.need(type(filtered) is dict and type(lag) is int and 0 <= lag <= 64
              and filtered.get("uses_future") is False
              and filtered.get("observation_semantics") ==
              "irregular_instantaneous_samples_not_continuous_rates",
              "fixed-lag estimator requires causal sampled filter history")
    m = base.array(filtered['means'], 2)
    C = base.array(filtered['covariances'], 3)
    predicted = base.array(filtered['predicted'], 2)
    prediction_cov = base.array(filtered['predicted_cov'], 3)
    F = base.array(filtered['transitions'], 3)
    times = base.array(filtered['times'], 1)
    steps, n = m.shape
    base.need(steps >= 2 and steps <= MAX_OBSERVATIONS + 1 and n <= MAX_N and
              C.shape == (steps, n, n) and
              predicted.shape == (steps - 1, n) and
              prediction_cov.shape == F.shape == (steps - 1, n, n) and
              times.shape == (steps,) and np.all(np.diff(times) > 0),
              "irregular filter history dimensions or time order")
    base.need(lag < steps, "lag cannot exceed available history")
    for j in range(steps):
        _checked_covariance(C[j], title="fixed-lag filtered covariance")
        if j < steps - 1:
            _checked_covariance(prediction_cov[j],
                                title="fixed-lag predicted covariance")
    out_means, out_covariances, release_times, released_at, indices = [], [], [], [], []
    for end in range(lag, steps):
        start = end - lag
        mean = m[end].copy()
        covariance = C[end].copy()
        for j in range(end - 1, start - 1, -1):
            predict_cov = prediction_cov[j]
            base.need(np.linalg.eigvalsh(predict_cov)[0] > 0 and
                      np.linalg.cond(predict_cov) <= 1e12,
                      "fixed-lag smoother prediction singular or ill-conditioned")
            gain = cho_solve(cho_factor(predict_cov, lower=True),
                             F[j] @ C[j]).T
            mean = m[j] + gain @ (mean - predicted[j])
            covariance, _ = _checked_covariance(
                C[j] + gain @ (covariance - predict_cov) @ gain.T,
                title="fixed-lag smoothed covariance")
        out_means.append(mean)
        out_covariances.append(covariance)
        indices.append(start)
        release_times.append(times[start])
        released_at.append(times[end])
    return base.receipt(
        state_indices=tuple(indices),
        state_times=np.asarray(release_times),
        release_times=np.asarray(released_at),
        means=np.asarray(out_means),
        covariances=np.asarray(out_covariances),
        lag_observation_events=lag,
        trailing_pending_states=lag,
        available_through_time=float(times[-1]),
        uses_later_samples_only_within_declared_lag=lag > 0,
        uses_future_beyond_release=False,
        covariance_psd_checked=True, covariance_globally_certified=False)
