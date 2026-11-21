"""SSM-04-R5: independent whole-path Gaussian and streaming refusal tests."""
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.linalg import block_diag
from cognitum.research import ssm_stochastic_streaming as s
from cognitum.research import ssm_stochastic_smoothing as r4


def _independent_joint(A,Q,H,R,N,m0,P0,times):
    """Independent coupled-moment ODE reference, never uses production Van Loan."""
    A,Q,H,R,N,m0,P0=map(np.asarray,(A,Q,H,R,N,m0,P0))
    n,k=H.shape
    count=len(times)
    size=n+count*(n+k)
    block_noise=np.block([[Q,N],[N.T,R]])
    drift=np.zeros((n+k,n+k));drift[:n,:n]=A;drift[n:,:n]=H
    basis=np.zeros((n,size));basis[:,:n]=np.eye(n)
    state_basis=[basis.copy()];obs_basis=[];blocks=[P0]
    for i,dt in enumerate(np.diff(np.r_[0.,times])):
        d=n+k;init=np.r_[np.eye(d).ravel(),np.zeros((d,d)).ravel()]
        def rhs(_t,z):
            F=z[:d*d].reshape(d,d);W=z[d*d:].reshape(d,d)
            return np.r_[(drift@F).ravel(),(drift@W+W@drift.T+block_noise).ravel()]
        sol=solve_ivp(rhs,(0.,float(dt)),init,rtol=1e-12,atol=1e-13)
        assert sol.success
        last=sol.y[:,-1];F=last[:d*d].reshape(d,d)
        W=last[d*d:].reshape(d,d);W=(W+W.T)/2
        blocks.append(W)
        off=n+i*d
        obs=F[n:,:n]@basis
        obs[:,off+n:off+d]+=np.eye(k)
        new=F[:n,:n]@basis
        new[:,off:off+n]+=np.eye(n)
        state_basis.append(new);obs_basis.append(obs)
        basis=new
    primitive=block_diag(*blocks)
    X=np.vstack(state_basis);Y=np.vstack(obs_basis)
    M=np.r_[X,Y]
    mean=M@np.r_[m0,np.zeros(size-n)]
    cov=M@primitive@M.T
    return mean,cov,n,k,count


def _conditioning(reference,index,end,observations):
    mu,C,n,k,count=reference
    xi=slice(index*n,(index+1)*n)
    obs_ids=[];values=[]
    for j in range(end):
        if observations[j] is not None:
            obs_ids.extend(range((count+1)*n+j*k,(count+1)*n+(j+1)*k))
            values.extend(observations[j])
    if not obs_ids:
        return mu[xi],C[xi,xi]
    gain=np.linalg.solve(C[np.ix_(obs_ids,obs_ids)],C[xi,:][:,obs_ids].T).T
    return mu[xi]+gain@(np.asarray(values)-mu[obs_ids]),C[xi,xi]-gain@C[obs_ids,:][:,xi]


def _assert_batch(releases,reference,times,observations):
    grid=np.r_[0.,times]
    for x in releases:
        i=x['state_index'];cutoff=x['observation_cutoff_time']
        end=sum(t<=cutoff for t in times)
        e,C=_conditioning(reference,i,end,observations)
        np.testing.assert_allclose(x['mean'],e,atol=3e-10,rtol=3e-10)
        np.testing.assert_allclose(x['covariance'],C,atol=3e-10,rtol=3e-10)
        np.testing.assert_allclose(x['factor']@x['factor'].T,x['covariance'],atol=1e-13)
        assert x['conditioned_through_time'] <= cutoff
        assert x['state_time']==pytest.approx(grid[i])
        assert x['release_time']>=cutoff
        assert x['certified'] is False and x['execution_authorized'] is False
        assert x['uses_future_beyond_cutoff'] is False


def test_irregular_multivariate_correlation_missing_and_exact_time_cutoff():
    A=[[-.6,.2],[-.1,-.4]];Q=[[.3,.05],[.05,.2]]
    H=[[1.,-.1],[.2,.7]];R=[[.6,.1],[.1,.5]]
    N=[[.1,-.03],[.02,.08]];m0=[.4,-.2];P0=[[.7,.1],[.1,.6]]
    times=[.3,.75,1.4,1.5,2.5,3.,4.]
    obs=[[.1,-.3],[.4,.2],None,[1.,-.2],[-.1,.2],[.1,.2],[.8,.4]]
    stream=s.FixedDurationIncrementSmoother(A,Q,H,R,m0,P0,
        lag_duration=1.5,noise_cross=N,max_pending_states=16)
    releases=[]
    for t,y in zip(times,obs):releases.extend(stream.push(t,y))
    releases.extend(stream.advance_watermark(times[-1]+2.))
    assert len(releases)==len(times)+1
    assert [v['state_index'] for v in releases]==list(range(len(times)+1))
    assert stream.status()['pending_count']==0
    assert any(r['state_index']==0 and r['conditioned_through_time']==1.5
               for r in releases)
    _assert_batch(releases,_independent_joint(A,Q,H,R,N,m0,P0,times),times,obs)


def test_crossing_increment_is_excluded_even_when_it_is_extreme():
    args=([[0]],[[.2]],[[1]],[[.4]],[0],[[.8]])
    a=s.FixedDurationIncrementSmoother(*args,lag_duration=1.,noise_cross=[[.1]])
    b=s.FixedDurationIncrementSmoother(*args,lag_duration=1.,noise_cross=[[.1]])
    assert not a.push(.4,[.2]); assert not b.push(.4,[.2])
    x=a.push(1.2,[100.]); y=b.push(1.2,[-100.])
    assert len(x)==len(y)==1
    assert x[0]['state_index']==0 and x[0]['conditioned_through_time']==.4
    np.testing.assert_allclose(x[0]['mean'],y[0]['mean'],atol=1e-13)
    np.testing.assert_allclose(x[0]['covariance'],y[0]['covariance'],atol=1e-13)


def test_exact_cutoff_event_included_and_no_future_event_used():
    args=([[0]],[[.3]],[[1]],[[.6]],[0],[[1.]])
    stream=s.FixedDurationIncrementSmoother(*args,lag_duration=1.,noise_cross=[[.1]])
    stream.push(.4,[.1])
    (released,)=stream.push(1.,[.8])
    assert released['conditioned_through_time']==1.
    assert released['release_time']==1.
    other=s.FixedDurationIncrementSmoother(*args,lag_duration=1.,noise_cross=[[.1]])
    other.push(.4,[.1]);(old,)=other.push(1.,[.8])
    other.push(1.4,[999.])
    np.testing.assert_allclose(old['mean'],released['mean'],atol=1e-13)


def test_duration_zero_releases_initial_and_every_new_filtered_state():
    p=s.FixedDurationIncrementSmoother([[0]],[[.4]],[[1]],[[.2]],
        [0],[[1]],lag_duration=0.,noise_cross=[[.1]],max_pending_states=1)
    assert len(p.initial_releases)==1 and p.initial_releases[0]['state_index']==0
    for i in range(1,21):
        (r,)=p.push(i*.1,[.2])
        assert r['state_index']==i and r['conditioned_through_time']==pytest.approx(i*.1)
        assert p.status()['pending_count']==0 and p.status()['retained_pair_count']==0
    assert p.status()['total_released_states']==21


def test_watermark_silence_release_and_reject_late_events():
    p=s.FixedDurationIncrementSmoother([[0]],[[.2]],[[1]],[[.5]],
        [0],[[1]],lag_duration=1.,noise_cross=[[.1]])
    assert not p.push(.2,[.3])
    (release,)=p.advance_watermark(1.)
    assert release['state_index']==0 and release['release_time']==1.
    assert release['conditioned_through_time']==.2
    previous=p.status()
    with pytest.raises(ValueError,match='unwatermarked'):
        p.push(.8,[.1])
    assert p.status()['total_increment_events']==previous['total_increment_events']
    assert p.push(1.1,[.2])==()
    (due,)=p.advance_watermark(1.2)
    assert due["state_index"]==1 and due["conditioned_through_time"]==1.1
    with pytest.raises(ValueError,match='watermark'):
        p.advance_watermark(1.1)


def test_atomic_buffer_overflow_and_followup_recovery():
    p=s.FixedDurationIncrementSmoother([[0]],[[.3]],[[1]],[[.5]],
        [0],[[1]],lag_duration=5.,max_pending_states=3)
    p.push(.1,[.1]);p.push(.2,[.1])
    before=p.status()
    with pytest.raises(ValueError,match='pending state budget'):
        p.push(.3,[.2])
    after=p.status()
    assert after['total_increment_events']==before['total_increment_events']
    assert after['pending_state_times']==before['pending_state_times']
    np.testing.assert_array_equal(after['filter_mean'],before['filter_mean'])
    released=p.push(5.1,[.1])
    assert [a['state_index'] for a in released]==[0,1]
    assert p.status()['pending_count']==2
    assert p.status()['peak_pending_states']<=3


def test_failed_nonpsd_or_bad_increment_does_not_mutate_state():
    with pytest.raises(ValueError):
        s.FixedDurationIncrementSmoother([[0]],[[.1]],[[1]],[[.2]],
            [0],[[1]],lag_duration=1.,noise_cross=[[2.]])
    p=s.FixedDurationIncrementSmoother([[0]],[[.2]],[[1]],[[.4]],
        [0],[[1]],lag_duration=1.)
    before=p.status()
    for ts,y in ((.1,[float('nan')]),(.1,[1.,2.]),(17.,[1.]),(-1.,[1.])):
        with pytest.raises(ValueError):p.push(ts,y)
    assert p.status()['total_increment_events']==before['total_increment_events']
    assert p.status()['pending_state_times']==before['pending_state_times']


def test_long_stream_memory_is_bounded_and_output_history_not_retained():
    p=s.FixedDurationIncrementSmoother([[-.2]],[[.3]],[[1]],[[.5]],
        [0],[[1]],lag_duration=.75,noise_cross=[[.1]],max_pending_states=5)
    previous=-1;count=0
    for j in range(500):
        out=p.push(float((j+1)*.25),[float(np.sin(j*.13))] if j%11 else None)
        for r in out:
            assert r['state_index']>previous
            previous=r['state_index'];count+=1
        st=p.status()
        assert st['pending_count']<=4
        assert st['retained_pair_count']==max(0,st['pending_count']-1)
    assert p.status()['total_increment_events']==500
    assert p.status()['missing_increments']==46
    assert p.status()['peak_pending_states']<=5
    assert count==498
    assert p.status()['total_released_states']==count


def test_batch_adapter_matches_event_stream_and_keeps_trailing_pending():
    args=([[0]],[[.2]],[[1]],[[.5]],[0],[[1]],[.3,1.1,1.4],[[.2],[.3],[.4]])
    b=s.fixed_duration_increment_smooth(*args,lag_duration=1.,noise_cross=[[.1]])
    assert b['released_count']==2 and b['trailing_pending_states']==2
    assert b['status']['total_increment_events']==3
    assert b['releases'][0]['state_index']==0
    full=s.fixed_duration_increment_smooth(*args,lag_duration=1.,noise_cross=[[.1]],final_watermark=3.)
    assert full['released_count']==4 and full['trailing_pending_states']==0


@pytest.mark.parametrize('seed',range(12))
def test_random_irregular_correlated_reference_and_variable_windows(seed):
    rng=np.random.default_rng(55105+seed)
    a=-float(rng.uniform(.05,.8));q=float(rng.uniform(.1,.6))
    h=float(rng.uniform(.3,1.2));r=float(rng.uniform(.3,.9))
    cross=float(rng.uniform(-.65,.65)*np.sqrt(q*r))
    m=float(rng.normal());prior=float(rng.uniform(.2,1.))
    times=np.cumsum(rng.uniform(.13,.8,size=7)).tolist()
    y=[[float(rng.normal())] for _ in times]
    if seed%3==0:y[2]=None
    duration=float([.55,1.4,2.3][seed%3])
    ref=_independent_joint([[a]],[[q]],[[h]],[[r]],[[cross]],[m],[[prior]],times)
    p=s.FixedDurationIncrementSmoother([[a]],[[q]],[[h]],[[r]],
        [m],[[prior]],lag_duration=duration,noise_cross=[[cross]])
    emitted=[]
    for t,ob in zip(times,y):emitted.extend(p.push(float(t),ob))
    emitted.extend(p.advance_watermark(float(times[-1]+duration+1)))
    assert len(emitted)==8
    _assert_batch(emitted,ref,times,y)
