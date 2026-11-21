"""COG-05-SSM-04-R4: causal fixed-lag smoothing of integrated Ito increments.

The correlated continuous-time model is
    dx = A x dt + dW,      dY = H x dt + dV,
    Cov([dW,dV]) = [[Q,N],[N.T,R]] dt.
N (``noise_cross``) is a *rate*, not a sampled-observation covariance.

For each interval we condition the JOINT adjacent state pair (x_i,x_{i+1})
on the ACTUAL integrated observation increment. A backward conditional chain
then releases x_i after at most ``lag`` later increment events. The ordinary
endpoint-measurement RTS formula is invalid here: increment noise is generally
correlated with state-transition noise, even when N=0.

Finite-bin conditional distributions are exact for this linear Gaussian model,
up to floating-point errors; they do not condition on the full continuous
sensor path. Numerical QR factors keep reported covariances positive
semidefinite, but they are not certified enclosures or execution authority.
"""
from __future__ import annotations

import math
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from . import ssm_stochastic as core
from . import ssm_stochastic_increments as increments_core

MAX_LAG = 64


def _qr_root(B):
    """Lower QR root for up to 2*MAX_N joint state dimensions."""
    B = np.asarray(B, dtype=float)
    core.need(B.ndim == 2 and 1 <= B.shape[0] <= 2*increments_core.MAX_N
              and B.shape[1] >= B.shape[0] and np.isfinite(B).all(),
              "joint square-root dimensions or finite budget")
    _, upper = np.linalg.qr(B.T, mode="reduced")
    root = upper.T
    root *= np.where(np.diag(root) < 0, -1., 1.)
    core.need(np.isfinite(root).all() and np.max(np.abs(root)) <= 1e8,
              "joint square-root overflow")
    return root


def _conditional_joint(pair_mean, pair_factor, expected_y, Ly, observation):
    """Condition BOTH states on the same integrated increment using QR."""
    cov_y = Ly @ Ly.T
    core.need(np.isfinite(cov_y).all() and np.linalg.cond(cov_y) <= 1e12,
              "integrated observation innovation singular/ill-conditioned")
    cho = cho_factor((cov_y + cov_y.T)/2, lower=True, check_finite=True)
    gain = cho_solve(cho, (pair_factor @ Ly.T).T).T
    residual = observation - expected_y
    mean = pair_mean + gain @ residual
    root = _qr_root(pair_factor - gain @ Ly)
    nis = float(residual @ cho_solve(cho, residual))
    ll = -.5*(len(residual)*math.log(2*math.pi) +
             2*np.log(np.diag(cho[0])).sum() + nis)
    core.need(np.isfinite(mean).all() and np.max(np.abs(mean)) <= 1e8
              and np.isfinite(ll), "joint increment posterior overflow")
    return mean, root, nis, float(ll)


def correlated_increment_filter(A, Q, H, R, m0, P0, times, increments,
                                *, noise_cross=None, initial_time=0.0):
    """Filter actual interval-integrated dY and save correlation-correct pairs.

    ``noise_cross`` is n-by-k Cov(dW,dV)/dt; ``None`` selects independent
    Brownian drivers. Full [[Q,N],[N.T,R]] must be positive semidefinite.
    Missing increments are predict-only, never imputed as zero. History is
    only valid for :func:`fixed_lag_increment_smooth`, not sampled RTS.
    """
    A,Q,H,R,m,P = increments_core._inputs(A,Q,H,R,m0,P0)
    clock, dts = increments_core._grid(times, increments, initial_time)
    n,k = len(m), H.shape[0]
    N = (np.zeros((n,k)) if noise_cross is None else
         core.array(noise_cross,2))
    core.need(N.shape == (n,k), "noise cross covariance rate shape")
    rate = np.block([[Q,N],[N.T,R]])
    _, rate_clips = increments_core._psd_root(rate,
                                              title="joint process/sensor rate")
    generator = np.zeros((n+k,n+k))
    generator[:n,:n] = A
    generator[n:,:n] = H
    S, initial_clips = increments_core._psd_root(P,title="initial state")
    means, roots = [m.copy()], [S.copy()]
    pairs_mean, pairs_root = [], []
    nis, elapsed = [], []
    missing, ll_sum, clips = 0,0.,rate_clips+initial_clips
    for dt, delta in zip(dts, increments):
        M, noise_root, c = increments_core._van_loan(generator, rate, float(dt))
        clips += c
        F, G = M[:n,:n], M[n:,:n]
        # Independent xi prior and interval diffusion; diffusion can correlate
        # process and sensor innovations via both N and the state integral.
        state_pair = np.block([
            [S, np.zeros((n,n+k))],
            [F@S, noise_root[:n,:]],
        ])
        sensor = np.column_stack((G@S, noise_root[n:,:]))
        pair_mean = np.r_[m,F@m]
        if delta is None:
            pair_root = _qr_root(state_pair)
            missing += 1
            nis.append(None)
        else:
            observed = increments_core._vector(delta,k)
            pair_mean,pair_root,z,ll = _conditional_joint(
                pair_mean,state_pair,G@m,sensor,observed)
            nis.append(z)
            ll_sum += ll
        pairs_mean.append(pair_mean.copy())
        pairs_root.append(pair_root.copy())
        m = pair_mean[n:].copy()
        S = _qr_root(pair_root[n:,:])
        means.append(m.copy()); roots.append(S.copy())
        elapsed.append(float(dt))
    root_history = np.asarray(roots)
    return core.receipt(
        method="correlated_joint_Ito_increment_pair_QR_filter",
        observation_semantics="continuous_integrated_Itô_measurement_increments_not_rates",
        times=clock, elapsed_dts=np.asarray(elapsed),
        means=np.asarray(means), factors=root_history,
        covariances=root_history@root_history.transpose(0,2,1),
        joint_pair_means=np.asarray(pairs_mean),
        joint_pair_factors=np.asarray(pairs_root),
        cross_noise_rate=N.copy(), nis=tuple(nis),
        log_likelihood=float(ll_sum), missing_increments=missing,
        imputed_missing_increments=0, numerical_eigen_clips=clips,
        finite_interval_joint_Gaussian_conditional_exact=True,
        conditioned_on_full_continuous_sensor_path=False,
        covariance_psd_by_QR=True, covariance_globally_certified=False,
        uses_future=False)


def _backward_gain(Lold, Lnew):
    """Rank-aware conditional gain; null state modes cannot carry cross-info."""
    P = (Lnew@Lnew.T)
    vals,vecs = np.linalg.eigh((P+P.T)/2)
    scale = max(1.,float(np.max(np.abs(vals))))
    core.need(vals[0] >= -1e-11*scale,"negative adjacent-pair covariance")
    mask = vals > 1e-12*scale
    if np.any(mask):
        core.need(float(np.max(vals[mask])/np.min(vals[mask])) <= 1e12,
                  "ill-conditioned correlated backward gain")
        pseudo = (vecs[:,mask]/vals[mask])@vecs[:,mask].T
        gain = (Lold@Lnew.T)@pseudo
    else:
        gain = np.zeros((Lold.shape[0],Lnew.shape[0]))
    # For a PSD pair covariance cross-covariance must vanish on the nullspace.
    residual = Lold-gain@Lnew
    core.need(np.isfinite(gain).all() and np.max(np.abs(gain)) <= 1e8,
              "correlated backward gain overflow")
    return gain,residual


def fixed_lag_increment_smooth(filtered, lag):
    """Release x_i | dY_1...dY_(i+lag), never later, via pair conditionals.

    For interval i the stored Gaussian pair is already conditioned on dY_(i+1)
    and all earlier increments. The backward transition is
      x_i | x_(i+1), dY_(1:i+1)
    with conditional mean u_old+J*(x_next-u_new), where J uses the *joint*
    pair covariance, not the unconditioned state-transition F*P. Missing
    increments still contribute transition correlations, without imputation.

    Covariance propagates as a QR root of the conditional-residual root and
    J times the downstream smooth root; no subtractive RTS covariance update.
    A lag of 0 releases the filtered states immediately. Final `lag` states
    remain pending; flushing them requires an explicitly different policy.
    """
    core.need(type(filtered) is dict and type(lag) is int and
              0 <= lag <= MAX_LAG and filtered.get('uses_future') is False and
              filtered.get('method') ==
              'correlated_joint_Ito_increment_pair_QR_filter' and
              filtered.get('observation_semantics') ==
              'continuous_integrated_Itô_measurement_increments_not_rates',
              "requires causal correlated integrated increment filter history")
    times = core.array(filtered['times'],1)
    means = core.array(filtered['means'],2)
    roots = core.array(filtered['factors'],3)
    pair_means = core.array(filtered['joint_pair_means'],2)
    pair_roots = core.array(filtered['joint_pair_factors'],3)
    steps,n = means.shape
    core.need(2 <= steps <= increments_core.MAX_STEPS+1 and
              1 <= n <= increments_core.MAX_N and
              lag < steps and times.shape == (steps,) and
              np.all(np.diff(times) > 0) and
              roots.shape == (steps,n,n) and
              pair_means.shape == (steps-1,2*n) and
              pair_roots.shape == (steps-1,2*n,2*n),
              "correlated smoother history shape, clock or lag")
    # Refuse swapped/inconsistent adjacent pairs instead of inventing history.
    for j in range(steps-1):
        core.need(np.allclose(pair_means[j,n:],means[j+1],rtol=1e-9,atol=1e-10)
                  and np.allclose(pair_roots[j,n:,:]@pair_roots[j,n:,:].T,
                                  roots[j+1]@roots[j+1].T,
                                  rtol=1e-9,atol=1e-10),
                  "inconsistent correlated joint pair/filter history")
    output_means, output_roots = [], []
    for end in range(lag,steps):
        start = end-lag
        mean, S = means[end].copy(), roots[end].copy()
        for j in range(end-1,start-1,-1):
            pairmean = pair_means[j]
            pairroot = pair_roots[j]
            Lold,Lnew = pairroot[:n,:], pairroot[n:,:]
            J,Lres = _backward_gain(Lold,Lnew)
            mean = pairmean[:n]+J@(mean-pairmean[n:])
            S = _qr_root(np.column_stack((Lres,J@S)))
            core.need(np.isfinite(mean).all() and np.max(np.abs(mean))<=1e8,
                      "correlated smoothed mean overflow")
        output_means.append(mean); output_roots.append(S)
    root_history = np.asarray(output_roots)
    return core.receipt(
        method="joint_pair_conditioned_Ito_increment_fixed_lag_QR_smoother",
        observation_semantics=filtered['observation_semantics'],
        state_indices=tuple(range(steps-lag)),
        state_times=times[:steps-lag].copy(),
        release_times=times[lag:].copy(),
        means=np.asarray(output_means), factors=root_history,
        covariances=root_history@root_history.transpose(0,2,1),
        lag_observation_events=lag, trailing_pending_states=lag,
        available_through_time=float(times[-1]),
        uses_later_increments_only_within_declared_lag=lag>0,
        uses_future_beyond_release=False, uses_future=False,
        covariance_psd_by_QR=True,covariance_globally_certified=False,
        conditioned_on_full_continuous_sensor_path=False)
