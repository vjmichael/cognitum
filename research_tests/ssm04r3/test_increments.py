"""COG-05-SSM-04-R3 independent stochastic increments/square-root tests.

Analytic moment formulae and independent ODE integration validate finite-
interval joint Gaussian conditioning. All data synthetic, no benchmarks.
"""
import math
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.linalg import expm
from cognitum.research import ssm_stochastic_increments as s


def test_exact_scalar_integrated_observation_no_process_noise():
    # ΔY = x0*dt + sqrt(R)*ΔV, x0~N(m,P).
    dt, m, P, R, dy = 2., .4, .8, 1.7, 3.
    out=s.kalman_bucy_increments([[0]],[[0]],[[1]],[[R]],
                                  [m],[[P]],[dt],[[dy]])
    K=P*dt/(P*dt**2+R*dt)
    expected=m+K*(dy-m*dt)
    variance=P-(P*dt)**2/(P*dt**2+R*dt)
    assert out['means'][-1,0]==pytest.approx(expected,abs=2e-12)
    assert out['covariances'][-1,0,0]==pytest.approx(variance,abs=2e-12)
    assert out['log_likelihood']==pytest.approx(
        -.5*(math.log(2*math.pi*(P*dt**2+R*dt))+(dy-m*dt)**2/(P*dt**2+R*dt)),abs=2e-12)
    assert out['observation_semantics'].startswith('continuous_integrated')
    assert not out['conditioned_on_full_continuous_sensor_path']
    assert not out['certified'] and not out['execution_authorized']


def test_exact_scalar_integrated_process_noise_cross_covariance():
    # x_t=x0+sqrt(Q)W_t; Y_t=∫x_s ds+sqrt(R)V_t.
    # Cov(x_t,Y_t)=P*t+Q*t²/2; Var(Y_t)=P*t²+Q*t³/3+R*t.
    P, Q, R, dt, m, dy = .6, .3, .4, 1.7, -.2, 1.8
    out=s.kalman_bucy_increments([[0]],[[Q]],[[1]],[[R]],
                                  [m],[[P]],[dt],[[dy]])
    cross=P*dt+Q*dt**2/2
    vy=P*dt**2+Q*dt**3/3+R*dt
    expected=m+cross/vy*(dy-m*dt)
    variance=P+Q*dt-cross**2/vy
    assert out['means'][-1,0]==pytest.approx(expected,abs=2e-12)
    assert out['covariances'][-1,0,0]==pytest.approx(variance,abs=2e-12)
    assert np.linalg.eigvalsh(out['covariances']).min()>=0


def test_continuous_rate_and_integrated_increment_are_distinct_semantics():
    # Same dy under different dt is not the same as holding dy/dt constant.
    a=s.kalman_bucy_increments([[0]],[[0]],[[1]],[[1]],
                                [0],[[1]],[1.],[[2.]])
    b=s.kalman_bucy_increments([[0]],[[0]],[[1]],[[1]],
                                [0],[[1]],[2.],[[2.]])
    assert a['means'][-1,0]==pytest.approx(1.)
    assert b['means'][-1,0]==pytest.approx(2/3)
    assert b['observation_semantics']!='piecewise_constant_observed_rate_not_exact_SDE_path'


def test_independent_coupled_ODE_conditional_gaussian():
    # No reuse of the production Van Loan calculation for expected values.
    A=np.array([[-.7,.9],[-.6,-.4]])
    Q=np.array([[.3,.04],[.04,.5]])
    H=np.array([[1.,.2],[-.1,.8]])
    R=np.array([[.6,.1],[.1,.3]])
    P=np.array([[.8,.1],[.1,.4]])
    m=np.array([.4,-.7])
    t=1.3
    inc=np.array([1.5,-.2])
    n=k=2;d=n+k
    F=np.zeros((d,d));F[:n,:n]=A;F[n:,:n]=H
    diffusion=np.zeros((d,d));diffusion[:n,:n]=Q;diffusion[n:,n:]=R
    z=np.r_[m,[0.,0.]]
    V0=np.zeros((d,d));V0[:n,:n]=P
    def rhs(_time,vec):
        mu=vec[:d]
        cov=vec[d:].reshape(d,d)
        return np.r_[F@mu,(F@cov+cov@F.T+diffusion).ravel()]
    iv=np.r_[z,V0.ravel()]
    solution=solve_ivp(rhs,(0,t),iv,rtol=1e-12,atol=1e-13)
    assert solution.success
    mu=solution.y[:d,-1];V=solution.y[d:,-1].reshape(d,d)
    K=np.linalg.solve(V[n:,n:],V[:n,n:].T).T
    expected_mu=mu[:n]+K@(inc-mu[n:])
    expected_cov=V[:n,:n]-K@V[n:,:n]
    out=s.kalman_bucy_increments(A,Q,H,R,m,P,[t],[inc])
    np.testing.assert_allclose(out['means'][-1],expected_mu,atol=1e-10)
    np.testing.assert_allclose(out['covariances'][-1],expected_cov,atol=1e-10)
    np.testing.assert_allclose(out['factors'][-1]@out['factors'][-1].T,
                               out['covariances'][-1],atol=1e-13)


def test_two_interval_updates_reset_integrated_sensor_accumulator():
    # If x is exactly constant, all increments jointly contribute precision Σdt/R.
    out=s.kalman_bucy_increments([[0]],[[0]],[[1]],[[.5]],
                                  [0],[[2]],[.25,1.0],[[.1],[1.2]])
    variance=1/(1/2+1/.5)
    mean=variance*(.1+1.2)/.5
    assert out['means'][-1,0]==pytest.approx(mean,abs=1e-12)
    assert out['covariances'][-1,0,0]==pytest.approx(variance,abs=1e-12)


def test_missing_increment_is_predict_only_not_zero_integrated_measurement():
    args=([[-.3]],[[.2]],[[1]],[[.1]],[1],[[.5]],[.2,.8])
    skipped=s.kalman_bucy_increments(*args,[None,[.2]])
    observed=s.kalman_bucy_increments(*args,[[0.],[.2]])
    pure=s.kalman_bucy_increments(*args[:6],[.2],[None])
    np.testing.assert_allclose(skipped['means'][1],pure['means'][1],atol=1e-12)
    np.testing.assert_allclose(skipped['covariances'][1],pure['covariances'][1],atol=1e-12)
    assert skipped['missing_increments']==1 and skipped['imputed_missing_increments']==0
    assert skipped['nis'][0] is None
    assert abs(skipped['means'][1,0]-observed['means'][1,0])>1e-4


def test_more_genuine_observation_increments_add_information():
    # Observing two increments contains the information of their sum plus more.
    whole=s.kalman_bucy_increments([[0]],[[.5]],[[1]],[[.3]],
                                    [0],[[1]],[1.],[[0.]])
    two=s.kalman_bucy_increments([[0]],[[.5]],[[1]],[[.3]],
                                  [0],[[1]],[.4,1.],[[0.],[0.]])
    assert two['covariances'][-1,0,0] < whole['covariances'][-1,0,0]
    assert two['covariances'][-1,0,0]>0


def test_stochastic_finite_bin_covariance_converges_to_bucy_riccati():
    # A=0 Q=R=H=1, P0=0: continuous-path P(t)=tanh(t).
    exact=np.tanh(1.)
    coarse=s.kalman_bucy_increments([[0]],[[1]],[[1]],[[1]],
                                     [0],[[0]],[1.],[[0.]])
    fine=s.kalman_bucy_increments([[0]],[[1]],[[1]],[[1]],
                                   [0],[[0]],list(np.arange(1,41)/40),[[0.]]*40)
    c=coarse['covariances'][-1,0,0]
    f=fine['covariances'][-1,0,0]
    assert abs(f-exact)<abs(c-exact)
    assert abs(f-exact)<1e-4


def test_qr_sampled_filter_matches_existing_R2_discrete_irregular():
    from cognitum.research import ssm_stochastic_continuous as r2
    A=[[-.3,1],[-.4,-.6]]
    Q=[[.2,.03],[.03,.1]]
    H=[[1.,0.],[.5,1.]]
    R=[[.1,.02],[.02,.4]]
    m=[.7,-.2];P=[[.9,.1],[.1,.6]]
    ts=[.25,.6,1.4,2.25]
    y=[[1.,.3],None,[.8,-.1],[.4,.2]]
    a=s.square_root_sampled_filter(A,Q,H,R,m,P,ts,y)
    b=r2.irregular_filter(A,Q,H,R,m,P,ts,y)
    np.testing.assert_allclose(a['means'],b['means'],atol=1e-11)
    np.testing.assert_allclose(a['covariances'],b['covariances'],atol=1e-11)
    np.testing.assert_allclose(a['predicted_cov'],b['predicted_cov'],atol=1e-11)
    assert a['nis'][1] is None and b['nis'][1] is None
    for j in (0,2,3):
        assert a['nis'][j]==pytest.approx(b['nis'][j],abs=1e-11)
    assert a['missing_samples']==1


def test_qr_sampled_factors_psd_for_degenerate_initial_state():
    a=s.square_root_sampled_filter([[0,0],[0,-1]],[[0,0],[0,.001]],
        [[1.,1.]],[[1e-9]],[2.,1.],[[0,0],[0,1.]],
        [.1,.4,1.],[[3.],[-2.],[1.]])
    for root,C in zip(a['factors'],a['covariances']):
        np.testing.assert_allclose(root@root.T,C,rtol=0,atol=1e-12)
        assert np.linalg.eigvalsh(C).min()>=-1e-13
    assert a['covariance_psd_by_QR']
    assert not a['covariance_globally_certified']


def test_qr_sampled_filter_compatible_with_R2_causal_lag_smoother():
    from cognitum.research import ssm_stochastic_continuous as r2
    a=s.square_root_sampled_filter([[-.2]],[[.15]],[[1]],[[.4]],
        [0],[[1]],[.3,.7,1.4],[[1.],[2.],[0.]])
    filtered=r2.irregular_filter([[-.2]],[[.15]],[[1]],[[.4]],
        [0],[[1]],[.3,.7,1.4],[[1.],[2.],[0.]])
    sl=r2.fixed_lag_smooth(a,1)
    fl=r2.fixed_lag_smooth(filtered,1)
    np.testing.assert_allclose(sl['means'],fl['means'],atol=1e-11)
    np.testing.assert_allclose(sl['covariances'],fl['covariances'],atol=1e-11)


def test_increments_filter_is_not_mistaken_for_R2_smoother_input():
    from cognitum.research import ssm_stochastic_continuous as r2
    a=s.kalman_bucy_increments([[0]],[[.1]],[[1]],[[.2]],
                                 [0],[[1]],[.3,.7],[[.1],[.2]])
    with pytest.raises(ValueError,match='fixed-lag estimator requires'):
        r2.fixed_lag_smooth(a,1)


def test_exact_time_causality_of_fixed_prefix():
    args=([[0]],[[.1]],[[1]],[[.3]],[0],[[1]])
    shorter=s.kalman_bucy_increments(*args,[.5],[[1.]])
    longer=s.kalman_bucy_increments(*args,[.5,1.],[[1.],[-100.]])
    np.testing.assert_allclose(shorter['means'],longer['means'][:2],atol=1e-13)
    np.testing.assert_allclose(shorter['covariances'],longer['covariances'][:2],atol=1e-13)


@pytest.mark.parametrize('times,obs',[
    ([0.],[[1.]]),
    ([.2,.1],[[1.],[1.]]),
    ([.2,.2],[[1.],[1.]]),
    ([.5],[[1.],[1.]]),
    ([17.],[[1.]]),
    ([.2],[[float('nan')]]),
    ([.2],[[1.,2.]]),
])
def test_invalid_clocks_and_increment_shapes_refused(times,obs):
    with pytest.raises(ValueError):
        s.kalman_bucy_increments([[0]],[[.1]],[[1]],[[.3]],
                                  [0],[[1]],times,obs)


def test_invalid_singular_measurement_noise_refused():
    with pytest.raises(ValueError):
        s.kalman_bucy_increments([[0]],[[.1]],[[1]],[[0]],
                                  [0],[[1]],[1.],[[1.]])


def test_rank_deficient_multivariate_noise_remains_psd():
    a=s.kalman_bucy_increments([[0,0],[0,-.5]],[[.02,0],[0,0]],
       [[1,0],[0,1]],[[.1,0],[0,.1]],[1,1],[[0,0],[0,0]],
       [.2,.9],[[.4,.3],[.1,-.2]])
    assert min(float(np.linalg.eigvalsh(C).min()) for C in a['covariances'])>=-1e-13
    np.testing.assert_allclose(a['factors']@a['factors'].transpose(0,2,1),
                               a['covariances'],atol=1e-14)


def test_sampled_receipt_disclaims_certification_and_physical_claims():
    a=s.square_root_sampled_filter([[-.3]],[[.2]],[[1]],[[.1]],
        [0],[[1]],[.2],[None])
    assert a['method']=='QR_square_root_Van_Loan_Joseph_sampled_filter'
    assert a['execution_authorized'] is False
    assert a['certified'] is False
    assert a['uses_future'] is False
    assert a['missing_samples']==1

@pytest.mark.parametrize('seed',range(16))
def test_independent_random_coupled_Ito_increment_moment_ODE(seed):
    rng=np.random.default_rng(seed+60403)
    A=-.5*np.eye(2)+rng.normal(size=(2,2))*.12
    B=rng.normal(size=(2,2))*.3
    Q=B@B.T
    H=rng.normal(size=(1,2))
    R=np.array([[.2+.6*rng.random()]])
    D=rng.normal(size=(2,2))*.4
    P=D@D.T+np.eye(2)*.03
    m=rng.normal(size=2)
    delta=rng.normal(size=1)
    dt=.1+1.5*rng.random()
    # Independent ODE over joint augmented state and measurement accumulator.
    G=np.zeros((3,3));G[:2,:2]=A;G[2:,:2]=H
    noise=np.zeros((3,3));noise[:2,:2]=Q;noise[2:,2:]=R
    z0=np.r_[m,[0]]
    cov0=np.zeros((3,3));cov0[:2,:2]=P
    def ode(t,v):
        z=v[:3];cov=v[3:].reshape(3,3)
        return np.r_[G@z,(G@cov+cov@G.T+noise).ravel()]
    solve=solve_ivp(ode,(0,dt),np.r_[z0,cov0.ravel()],
                    rtol=2e-11,atol=2e-12)
    assert solve.success
    z=solve.y[:3,-1];W=solve.y[3:,-1].reshape(3,3)
    gain=W[:2,2:]/W[2,2]
    expected=z[:2]+gain[:,0]*(delta[0]-z[2])
    expected_P=W[:2,:2]-gain@W[2:,:2]
    res=s.kalman_bucy_increments(A,Q,H,R,m,P,[dt],[delta])
    np.testing.assert_allclose(res['means'][-1],expected,atol=2e-9,rtol=2e-9)
    np.testing.assert_allclose(res['covariances'][-1],expected_P,
                               atol=2e-9,rtol=2e-9)
    assert np.linalg.eigvalsh(res['covariances'][-1]).min()>-1e-12


@pytest.mark.parametrize('seed',range(12))
def test_random_square_root_vs_original_sampled_filter(seed):
    from cognitum.research import ssm_stochastic_continuous as r2
    rng=np.random.default_rng(seed+34005)
    A=np.array([[-.7,.4],[-.2,-.8]])+rng.normal(size=(2,2))*.03
    D=rng.normal(size=(2,2))
    Q=D@D.T*.07
    V=rng.normal(size=(2,2))
    P=V@V.T+np.eye(2)*.05
    H=np.array([[1.,-.1],[.2,.7]])
    R=np.array([[.5,.06],[.06,.3]])
    ts=np.cumsum(rng.uniform(.06,.6,size=5)).tolist()
    observations=[rng.normal(size=2).tolist() if i!=2 else None
                  for i in range(5)]
    m=rng.normal(size=2)
    new=s.square_root_sampled_filter(A,Q,H,R,m,P,ts,observations)
    old=r2.irregular_filter(A,Q,H,R,m,P,ts,observations)
    np.testing.assert_allclose(new['means'],old['means'],atol=2e-10)
    np.testing.assert_allclose(new['covariances'],old['covariances'],atol=2e-10)
    for root,mat in zip(new['factors'],new['covariances']):
        np.testing.assert_allclose(root@root.T,mat,atol=5e-13)


def test_excessively_unstable_generator_refused_before_expm_overflow():
    with pytest.raises(ValueError,match='unstable or unbounded'):
        s.kalman_bucy_increments([[1000]],[[.1]],[[1]],[[.5]],
                                  [0],[[1]],[1.],[[.1]])


def test_aliased_stochastic_increment_cannot_be_substituted_with_zero():
    a=s.kalman_bucy_increments([[0]],[[.3]],[[1]],[[.5]],
                                [0],[[1]],[.5],[None])
    b=s.kalman_bucy_increments([[0]],[[.3]],[[1]],[[.5]],
                                [0],[[1]],[.5],[[0.]])
    assert a['covariances'][-1,0,0]>b['covariances'][-1,0,0]
    assert a['imputed_missing_increments']==0
