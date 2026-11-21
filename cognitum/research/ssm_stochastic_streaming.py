"""COG-05-SSM-04-R5: bounded-memory fixed-DURATION smoothing of Ito increments.

Streaming, event-time implementation of the accepted R4 correlated joint-pair
backward recursion. Duration is in the SAME time units as input timestamps, not
an event count. When an arriving interval endpoint would cross an earlier
state's duration cutoff, that state is released BEFORE assimilating the new
increment. At an endpoint exactly on the cutoff the increment is included.
Thus no increment ending after the cutoff can influence a released state.

A monotone event-time watermark can release due states during sensor silence.
Watermarked late increments are refused, never silently inserted. Only bounded
pending states and their correlated adjacent-pair conditionals are retained;
there is no unbounded in-object history or automatic speculative flush.

All quantities are synthetic, linear-Gaussian, CPU numerical and finite-bin
conditional. Neither physical sensor trust nor numerical certification nor
installed MEL execution authority is implied.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import ssm_stochastic as core
from . import ssm_stochastic_increments as inc
from . import ssm_stochastic_smoothing as r4

MAX_DURATION = 256.0
MAX_PENDING = 256
MAX_EVENTS = 1_000_000
MAX_CLOCK = 1e8


@dataclass(frozen=True)
class _State:
    index: int
    time: float
    mean: np.ndarray
    factor: np.ndarray


@dataclass(frozen=True)
class _Pair:
    mean: np.ndarray
    factor: np.ndarray


def _real(value, label):
    core.need(type(value) in (int, float) and math.isfinite(value)
              and 0 <= value <= MAX_CLOCK, f"{label} finite clock/duration budget")
    return float(value)


class FixedDurationIncrementSmoother:
    """Stateful event-time smoother; every push and watermark update is atomic.

    max_pending_states bounds retained state nodes (and one fewer adjacent pair
    nodes) to 1..256; an update may use ONE additional transient state and pair
    before a due-state release. On budget refusal the stream is unchanged.
    The class does not retain releases: each call returns immutable-in-practice
    new receipt objects which the caller owns.

    If duration==0, x0 is available in `initial_releases` immediately and all
    following pushes release their instantaneous filtered state. No unobserved
    interval is silently integrated at a watermark.
    """

    def __init__(self, A, Q, H, R, m0, P0, *, lag_duration,
                 noise_cross=None, initial_time=0.0, max_pending_states=128):
        A,Q,H,R,m,P = inc._inputs(A,Q,H,R,m0,P0)
        n,k = H.shape[1],H.shape[0]
        N = (np.zeros((n,k)) if noise_cross is None else
             core.array(noise_cross,2))
        core.need(N.shape == (n,k), "noise cross covariance rate shape")
        rate = np.block([[Q,N],[N.T,R]])
        _,rate_clips = inc._psd_root(rate,title="joint process/sensor rate")
        duration=_real(lag_duration,"lag duration")
        core.need(duration<=MAX_DURATION,"duration budget")
        core.need(type(max_pending_states) is int and
                  1 <= max_pending_states <= MAX_PENDING,
                  "bounded pending state count")
        t0=_real(initial_time,"initial time")
        generator=np.zeros((n+k,n+k))
        generator[:n,:n]=A;generator[n:,:n]=H
        S,init_clips=inc._psd_root(P,title="initial state")
        self._generator=generator.copy()
        self._rate=rate.copy()
        self._m=m.copy();self._S=S.copy()
        self._n=n;self._k=k
        self.duration=duration
        self.max_pending_states=max_pending_states
        self._time=t0
        self._watermark=t0
        self._index=0
        self._count=0
        self._missing=0
        self._ll=0.0
        self._clips=init_clips+rate_clips
        self._released=0
        self._peak=0
        state=_State(0,t0,m.copy(),S.copy())
        self._states=[state] if duration>0 else []
        self._pairs=[]
        self.initial_releases=(self._release(state,m,S,t0,t0),) if duration==0 else ()
        self._released=len(self.initial_releases)
        self._peak=len(self._states)

    def _release(self,state,mean,root,release_at,conditioned_through):
        core.need(conditioned_through <= state.time+self.duration and
                  state.time <= conditioned_through <= release_at,
                  "smoothing output information cutoff/order")
        covariance=root@root.T
        return core.receipt(
            method="bounded_streaming_correlated_Itô_increment_duration_QR",
            observation_semantics="continuous_integrated_Itô_measurement_increments_not_rates",
            state_index=state.index, state_time=state.time,
            observation_cutoff_time=state.time+self.duration,
            release_time=release_at,conditioned_through_time=conditioned_through,
            mean=mean.copy(),factor=root.copy(),covariance=covariance,
            lag_duration=self.duration,uses_future_beyond_cutoff=False,
            uses_future_beyond_release=False,
            conditioned_on_full_continuous_sensor_path=False,
            covariance_psd_by_QR=True,covariance_globally_certified=False)

    def _emit_prefix(self,states,pairs,due,at):
        if not due:
            return ()
        core.need(len(pairs)==len(states)-1 and 0<=due<=len(states),
                  "correlated streaming pair/state alignment")
        n=self._n
        # One backward sweep serves every due state; O(window), not repeated
        # O(window**2) smoothing for a burst of due releases.
        mean=states[-1].mean.copy();root=states[-1].factor.copy()
        backward=[(mean,root)]
        for pair in reversed(pairs):
            old,new=pair.factor[:n,:],pair.factor[n:,:]
            gain,residual=r4._backward_gain(old,new)
            mean=pair.mean[:n]+gain@(mean-pair.mean[n:])
            root=r4._qr_root(np.column_stack((residual,gain@root)))
            core.need(np.isfinite(mean).all() and np.max(abs(mean))<=1e8,
                      "streaming backward mean overflow")
            backward.append((mean,root))
        backward.reverse()
        through=states[-1].time
        released=tuple(self._release(states[j],*backward[j],at,through)
                       for j in range(due))
        del states[:due]
        del pairs[:due]
        return released

    def _step(self,dt,delta):
        n,k=self._n,self._k
        M,noise_root,clips=inc._van_loan(self._generator,self._rate,dt)
        F,G=M[:n,:n],M[n:,:n]
        state_pair=np.block([
            [self._S,np.zeros((n,n+k))],
            [F@self._S,noise_root[:n,:]],
        ])
        sensor=np.column_stack((G@self._S,noise_root[n:,:]))
        pair_mean=np.r_[self._m,F@self._m]
        ll=0.
        if delta is None:
            pair_root=r4._qr_root(state_pair)
            nis=None
        else:
            observation=inc._vector(delta,k)
            pair_mean,pair_root,nis,ll=r4._conditional_joint(
                pair_mean,state_pair,G@self._m,sensor,observation)
        mean=pair_mean[n:].copy()
        root=r4._qr_root(pair_root[n:,:])
        return mean,root,_Pair(pair_mean.copy(),pair_root.copy()),nis,ll,clips

    def push(self,end_time,increment):
        """Assimilate one actual integrated increment; return newly due states.

        A crossing interval is NOT used to smooth a state whose duration cutoff
        lies inside that interval. At exact equality it IS used. The return is
        the only in-object representation of each released estimate; no output
        history accumulates. Invalid/overflow steps leave the stream unchanged.
        """
        at=_real(end_time,"end time")
        core.need(at>self._time and at>self._watermark,
                  "strictly increasing unwatermarked event time")
        dt=at-self._time
        core.need(0<dt<=inc.MAX_DT,"bounded integrated increment interval")
        core.need(self._count<MAX_EVENTS,"stream event-count budget")
        # Validate observation before any potential internal mutation.
        if increment is not None:
            inc._vector(increment,self._k)
        states=list(self._states);pairs=list(self._pairs)
        # Information cutoff precedes assimilation of a crossing interval.
        due=sum(s.time+self.duration<at for s in states)
        before=self._emit_prefix(states,pairs,due,at)
        mean,root,pair,nis,ll,clips=self._step(float(dt),increment)
        if states:
            pairs.append(pair)
        new_state=_State(self._index+1,at,mean.copy(),root.copy())
        states.append(new_state)
        # Exact-cutoff event is eligible and is included in its release.
        due=sum(s.time+self.duration<=at for s in states)
        after=self._emit_prefix(states,pairs,due,at)
        core.need(len(states)<=self.max_pending_states,
                  "bounded pending state budget exceeded: no silent eviction")
        core.need(len(pairs)==max(0,len(states)-1),
                  "streaming pair retention invariant")
        # Commit all state changes only after successful math + release.
        self._states=states;self._pairs=pairs
        self._m=mean;self._S=root
        self._time=at;self._watermark=at
        self._index+=1;self._count+=1
        self._missing+=int(increment is None)
        self._ll+=ll;self._clips+=clips
        self._released+=len(before)+len(after)
        self._peak=max(self._peak,len(states))
        return before+after

    def advance_watermark(self,watermark_time):
        """Release elapsed-duration states during silence; reject late events.

        Watermark means no future increment with an endpoint <= this time can
        arrive. Does not fabricate an observation, process transition or state.
        """
        at=_real(watermark_time,"event-time watermark")
        core.need(at>=self._time and at>=self._watermark,
                  "watermark monotonicity/last observation")
        states=list(self._states);pairs=list(self._pairs)
        due=sum(s.time+self.duration<=at for s in states)
        releases=self._emit_prefix(states,pairs,due,at)
        self._states=states;self._pairs=pairs
        self._watermark=at
        self._released+=len(releases)
        return releases

    def status(self):
        """Bounded immutable-snapshot diagnostics; never exposes active arrays."""
        root=self._S.copy()
        return core.receipt(
            method="bounded_streaming_correlated_Itô_increment_status",
            last_observation_time=self._time,event_time_watermark=self._watermark,
            total_increment_events=self._count,missing_increments=self._missing,
            imputed_missing_increments=0,total_released_states=self._released,
            pending_count=len(self._states),retained_pair_count=len(self._pairs),
            pending_state_indices=tuple(s.index for s in self._states),
            pending_state_times=tuple(s.time for s in self._states),
            peak_pending_states=self._peak,max_pending_states=self.max_pending_states,
            lag_duration=self.duration,filter_mean=self._m.copy(),
            filter_factor=root,filter_covariance=root@root.T,
            log_likelihood=float(self._ll),numerical_eigen_clips=self._clips,
            uses_future=False,covariance_globally_certified=False)


def fixed_duration_increment_smooth(A,Q,H,R,m0,P0,times,increments,*,
                                    lag_duration,noise_cross=None,
                                    initial_time=0.0,max_pending_states=128,
                                    final_watermark=None):
    """Finite convenience adapter; emitted result arrays are intentionally held.

    Use FixedDurationIncrementSmoother.push/advance_watermark for actually
    bounded-memory streaming: this batch collector necessarily retains output.
    Pending estimates are NOT completed artificially unless an explicit final
    monotone watermark is supplied (which admits no extra observations).
    """
    core.need(type(increments) in (list,tuple) and
              len(increments)>0 and len(increments)<=MAX_EVENTS,
              "finite batch increment count")
    t=core.array(times,1,limit=MAX_EVENTS)
    core.need(t.shape==(len(increments),),"increment timestamp alignment")
    engine=FixedDurationIncrementSmoother(A,Q,H,R,m0,P0,
         lag_duration=lag_duration,noise_cross=noise_cross,
         initial_time=initial_time,max_pending_states=max_pending_states)
    released=list(engine.initial_releases)
    for at,increment in zip(t,increments):
        released.extend(engine.push(float(at),increment))
    if final_watermark is not None:
        released.extend(engine.advance_watermark(final_watermark))
    status=engine.status()
    return core.receipt(
        method="finite_collection_of_bounded_duration_increment_stream",
        observation_semantics="continuous_integrated_Itô_measurement_increments_not_rates",
        releases=tuple(released),status=status,
        released_count=len(released),trailing_pending_states=status['pending_count'],
        uses_future_beyond_cutoff=False,uses_future_beyond_release=False,
        conditioned_on_full_continuous_sensor_path=False,
        covariance_psd_by_QR=True,covariance_globally_certified=False)
