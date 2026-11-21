"""R4 independent finite-interval joint-Gaussian and causality tests.

The batch reference integrates deterministic moment ODEs instead of using
implementation Van Loan or backward pair factors. All observations synthetic.
"""
import math
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.linalg import block_diag
from cognitum.research import ssm_stochastic_smoothing as s
from cognitum.research import ssm_stochastic_increments as r3


def _ode_interval(A,Q,H,R,N,dt):
    A,Q,H,R,N = map(np.asarray,(A,Q,H,R,N))
    n,k=H.shape
    d=n+k
    aug=np.zeros((d,d))
    aug[:n,:n]=A;aug[n:,:n]=H
    rate=np.block([[Q,N],[N.T,R]])
    # State transition and joint random accumulator covariance via ODE.
    init=np.r_[np.eye(d).ravel(),np.zeros((d,d)).ravel()]
    def rhs(t,z):
        T=z[:d*d].reshape(d,d); P=z[d*d:].reshape(d,d)
        return np.r_[(aug@T).ravel(),(aug@P+P@aug.T+rate).ravel()]
    sol=solve_ivp(rhs,(0,float(dt)),init,rtol=1e-12,atol=1e-13)
    assert sol.success
    end=sol.y[:,-1]
    T=end[:d*d].reshape(d,d)
    P=end[d*d:].reshape(d,d)
    return T[:n,:n],T[n:,:n],(P+P.T)/2


def _batch_reference(A,Q,H,R,N,m0,P0,times,increments,initial=0.):
    """Unconditional whole-path Gaussian, then Schur-complement conditioning."""
    A=np.asarray(A);Q=np.asarray(Q);H=np.asarray(H);R=np.asarray(R)
    N=np.asarray(N);m0=np.asarray(m0);P0=np.asarray(P0)
    n,k=H.shape;count=len(times)
    size=n+count*(n+k)
    primitives=[P0]
    mapping=np.zeros((n,size));mapping[:,:n]=np.eye(n)
    xs=[mapping.copy()];ys=[]
    for i,dt in enumerate(np.diff(np.r_[initial,times])):
        F,G,V=_ode_interval(A,Q,H,R,N,dt)
        primitives.append(V)
        noise_index=n+i*(n+k)
        yi=G@mapping
        yi[:,noise_index+n:noise_index+n+k]+=np.eye(k)
        following=F@mapping
        following[:,noise_index:noise_index+n]+=np.eye(n)
        xs.append(following);ys.append(yi)
        mapping=following
    primitive_cov=block_diag(*primitives)
    state_map=np.vstack(xs)
    sensor_map=np.vstack(ys)
    full_cov= np.block([
        [state_map@primitive_cov@state_map.T, state_map@primitive_cov@sensor_map.T],
        [sensor_map@primitive_cov@state_map.T, sensor_map@primitive_cov@sensor_map.T],
    ])
    # Mean via the same independent linear mapping; all interval noise centered.
    primitive_mean=np.r_[m0,np.zeros(size-n)]
    full_mean=np.r_[state_map@primitive_mean,sensor_map@primitive_mean]
    return full_mean,full_cov,n,k,count


def _batch_condition(model, state_index, end, increments):
    mu,C,n,k,count=model
    xi=slice(state_index*n,(state_index+1)*n)
    obs_indices=[];z=[]
    for j in range(end):
        if increments[j] is not None:
            obs_indices+=list(range((count+1)*n+j*k,(count+1)*n+(j+1)*k))
            z.extend(increments[j])
    if not obs_indices:
        return mu[xi], C[xi,xi]
    cov_y=C[np.ix_(obs_indices,obs_indices)]
    cov_xy=C[xi,:][:,obs_indices]
    delta=np.asarray(z)-mu[obs_indices]
    gain=np.linalg.solve(cov_y,cov_xy.T).T
    return mu[xi]+gain@delta, C[xi,xi]-gain@cov_xy.T


def test_single_interval_closed_form_correlated_brownian_smoothing():
    # dx=sqrt(Q)dW, dY=x dt+noise, E[dW dV]=N dt.
    # Cov(x_end,Y)=P*t+Q*t^2/2+N*t.
    # Var(Y)=P*t^2+Q*t^3/3+N*t^2+R*t.
    P,Q,R,N,dt,m,dy=.8,.5,.9,.3,1.4,.4,2.1
    out=s.correlated_increment_filter([[0]],[[Q]],[[1]],[[R]],
                                      [m],[[P]],[dt],[[dy]],noise_cross=[[N]])
    var_y=P*dt**2+Q*dt**3/3+N*dt**2+R*dt
    old_gain=P*dt/var_y
    new_gain=(P*dt+Q*dt**2/2+N*dt)/var_y
    posterior=s.fixed_lag_increment_smooth(out,1)
    assert posterior['means'][0,0]==pytest.approx(m+old_gain*(dy-m*dt),abs=2e-12)
    assert posterior['covariances'][0,0,0]==pytest.approx(P-(P*dt)**2/var_y,abs=2e-12)
    assert out['means'][1,0]==pytest.approx(m+new_gain*(dy-m*dt),abs=2e-12)
    assert out['covariances'][1,0,0]==pytest.approx(P+Q*dt-(new_gain**2)*var_y,abs=2e-12)
    assert posterior['state_indices']==(0,) and posterior['release_times'][0]==dt


def test_random_multivariate_correlated_lag_vs_independent_batch_gaussian():
    A=[[-.6,.2],[-.15,-.3]]
    Q=[[.4,.03],[.03,.2]]
    H=[[1.,-.2],[.25,.8]]
    R=[[.7,.1],[.1,.5]]
    N=[[.11,-.08],[.07,.06]]
    m0=[.3,-.9];P0=[[.7,.11],[.11,.4]]
    times=[.2,.8,1.6,2.0]
    y=[[.5,-.2],[-.4,.1],None,[.2,.6]]
    f=s.correlated_increment_filter(A,Q,H,R,m0,P0,times,y,noise_cross=N)
    ref=_batch_reference(A,Q,H,R,N,m0,P0,times,y)
    for lag in (0,1,2,3,4):
        for j, index in enumerate(range(len(times)+1-lag)):
            smooth=s.fixed_lag_increment_smooth(f,lag)
            e,c=_batch_condition(ref,index,index+lag,y)
            np.testing.assert_allclose(smooth['means'][j],e,atol=1e-10,rtol=1e-10)
            np.testing.assert_allclose(smooth['covariances'][j],c,atol=1e-10,rtol=1e-10)
            np.testing.assert_allclose(smooth['factors'][j]@smooth['factors'][j].T,
                                       smooth['covariances'][j],atol=1e-13)
            assert np.linalg.eigvalsh(smooth['covariances'][j]).min()>-1e-12
        assert smooth['trailing_pending_states']==lag
        assert smooth['certified'] is False and smooth['execution_authorized'] is False


def test_no_explicit_cross_matches_original_independent_increment_filter():
    args=([[-.3,.1],[-.4,-.5]],[[.2,.03],[.03,.1]],[[1.,-.2]],[[.6]],
          [.4,-.2],[[.8,.1],[.1,.4]],[.2,.7,1.3],[[1.],None,[-.3]])
    a=s.correlated_increment_filter(*args)
    b=r3.kalman_bucy_increments(*args)
    np.testing.assert_allclose(a['means'],b['means'],atol=3e-12)
    np.testing.assert_allclose(a['covariances'],b['covariances'],atol=3e-12)
    assert a['log_likelihood']==pytest.approx(b['log_likelihood'],abs=3e-12)
    assert a['missing_increments']==1


def test_missing_increment_does_not_impute_zero_and_smoothing_conditions_later():
    args=([[0]],[[.3]],[[1]],[[.5]],[0],[[1]],[.3,1.])
    f=s.correlated_increment_filter(*args,[None,[1.]])
    z=s.correlated_increment_filter(*args,[[0.],[1.]])
    one=s.fixed_lag_increment_smooth(f,1)
    two=s.fixed_lag_increment_smooth(f,2)
    assert f['missing_increments']==1 and f['imputed_missing_increments']==0
    assert abs(f['means'][1,0]-z['means'][1,0])>1e-6 or f['covariances'][1,0,0]>z['covariances'][1,0,0]
    # State zero receives no information from the missing first increment until
    # the second increment becomes available.
    assert one['means'][0,0]==pytest.approx(0.,abs=1e-12)
    assert abs(two['means'][0,0])>1e-4


def test_prefix_invariance_when_future_measurement_changes():
    args=([[-.15]],[[.2]],[[1]],[[.5]],[.2],[[.8]],[.2,.6,1.1])
    a=s.correlated_increment_filter(*args,[[.3],[.1],[-1.] ],noise_cross=[[.1]])
    b=s.correlated_increment_filter(*args,[[.3],[.1],[100.]],noise_cross=[[.1]])
    x=s.fixed_lag_increment_smooth(a,1)
    z=s.fixed_lag_increment_smooth(b,1)
    np.testing.assert_allclose(x['means'][:2],z['means'][:2],atol=1e-12)
    np.testing.assert_allclose(x['covariances'][:2],z['covariances'][:2],atol=1e-12)
    assert x['release_times'][1]==pytest.approx(.6)


def test_rank_deficient_initial_state_and_zero_state_noise():
    f=s.correlated_increment_filter([[0,0],[0,-.3]],[[0,0],[0,0]],
        [[1.,0.]],[[.6]],[0,1],[[0,0],[0,1.]],
        [.3,.6],[[.2],[-.2]],noise_cross=[[0.],[0.]])
    sm=s.fixed_lag_increment_smooth(f,2)
    assert sm['covariances'][0,0,0]==pytest.approx(0.,abs=1e-12)
    assert np.linalg.eigvalsh(sm['covariances'][0]).min()>=-1e-12


@pytest.mark.parametrize('N',[[[2.]],[[float('nan')]],[[1.,2.]],[[float('inf')]]])
def test_nonpsd_nonfinite_or_wrong_cross_rate_refused(N):
    with pytest.raises(ValueError):
        s.correlated_increment_filter([[0]],[[.1]],[[1]],[[.2]],
                                       [0],[[1]],[.2],[[.1]],noise_cross=N)


def test_wrong_filter_receipt_or_history_refused():
    args=([[0]],[[.2]],[[1]],[[.5]],[0],[[1]],[.3,.7],[[.1],[.2]])
    old=r3.kalman_bucy_increments(*args)
    with pytest.raises(ValueError,match='requires causal correlated'):
        s.fixed_lag_increment_smooth(old,1)
    f=s.correlated_increment_filter(*args)
    with pytest.raises(ValueError):s.fixed_lag_increment_smooth(f,-1)
    with pytest.raises(ValueError):s.fixed_lag_increment_smooth(f,4)
    bad=dict(f)
    bad['joint_pair_means']=f['joint_pair_means'].copy()
    bad['joint_pair_means'][0,-1]+=10
    with pytest.raises(ValueError,match='inconsistent'):
        s.fixed_lag_increment_smooth(bad,1)


def test_zero_lag_is_filter_and_release_at_same_time():
    f=s.correlated_increment_filter([[0]],[[.3]],[[1]],[[.6]],
                                    [0],[[.7]],[.5,1.],[[.2],[.4]],
                                    noise_cross=[[.1]])
    sm=s.fixed_lag_increment_smooth(f,0)
    np.testing.assert_allclose(sm['means'],f['means'],atol=1e-13)
    np.testing.assert_allclose(sm['covariances'],f['covariances'],atol=1e-13)
    np.testing.assert_allclose(sm['state_times'],sm['release_times'],atol=0)


@pytest.mark.parametrize('seed',range(12))
def test_randomized_scalar_closed_form_multibin_gaussian(seed):
    rng=np.random.default_rng(40400+seed)
    a=-rng.uniform(.02,.7)
    q=rng.uniform(.01,.7)
    h=rng.uniform(.2,1.4)
    r=rng.uniform(.1,.9)
    cross=rng.uniform(-.7,.7)*math.sqrt(q*r)
    p=rng.uniform(.1,1.2)
    initial=float(rng.normal())
    times=np.cumsum(rng.uniform(.12,.7,size=4)).tolist()
    y=[rng.normal(size=1).tolist() for _ in times]
    if seed%3==0:y[1]=None
    args=([[a]],[[q]],[[h]],[[r]],[initial],[[p]],times,y)
    got=s.correlated_increment_filter(*args,noise_cross=[[cross]])
    model=_batch_reference([[a]],[[q]],[[h]],[[r]],[[cross]],
                           [initial],[[p]],times,y)
    for lag in (0,1,2,4):
        actual=s.fixed_lag_increment_smooth(got,lag)
        for j in range(5-lag):
            ex_mu,ex_cov=_batch_condition(model,j,j+lag,y)
            np.testing.assert_allclose(actual['means'][j],ex_mu,rtol=2e-10,atol=2e-10)
            np.testing.assert_allclose(actual['covariances'][j],ex_cov,
                                       rtol=2e-10,atol=2e-10)


def test_pure_sensor_noise_correlation_with_zero_drift_observation():
    # Even with H=0, dY and state increments share Brownian noise.
    # Its measurement MUST update x_end, but cannot inform x_start.
    f=s.correlated_increment_filter([[0]],[[.8]],[[0]],[[1.]],
                                    [0],[[.6]],[.5],[[1.2]],noise_cross=[[.5]])
    expected_gain=.5/(1.)
    assert f['means'][1,0]==pytest.approx(expected_gain*1.2,abs=2e-12)
    old=s.fixed_lag_increment_smooth(f,1)
    assert old['means'][0,0]==pytest.approx(0.,abs=2e-12)
    assert old['covariances'][0,0,0]==pytest.approx(.6,abs=2e-12)


def test_stochastic_budget_and_legacy_smoother_boundary():
    from cognitum.research import ssm_stochastic_continuous as r2
    f=s.correlated_increment_filter([[0]],[[.1]],[[1]],[[.5]],
                                    [0],[[1]],[.4],[[.3]],noise_cross=[[.1]])
    with pytest.raises(ValueError,match='fixed-lag estimator requires'):
        r2.fixed_lag_smooth(f,0)
    with pytest.raises(ValueError):
        s.correlated_increment_filter([[0]],[[.1]],[[1]],[[.5]],
                                       [0],[[1]],[18.],[[.3]],noise_cross=[[.1]])
