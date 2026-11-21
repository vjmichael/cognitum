"""COG-05-SSM-04-R2 bounded native analytic/independent correctness tests."""
import numpy as np
import pytest
from scipy.linalg import expm
from cognitum.research import ssm_stochastic_continuous as s

def test_bucy_scalar_stationary_exact_mean_and_riccati():
    # A=0, Q=R=H=1, P0=1 is stationary Riccati.
    ts=[0.,.2,.5,1.,2.]
    a=s.kalman_bucy([[0]],[[1]],[[1]],[[1]],[0],[[1]],ts,[[2.]]*4)
    np.testing.assert_allclose(a['means'][:,0],
        2*(1-np.exp(-np.array(ts))),atol=1e-9)
    np.testing.assert_allclose(a['covariances'][:,0,0],1,atol=1e-10)
    assert all(v>0 for v in a['unprojected_min_eigenvalues'])
    assert not a['certified'] and not a['execution_authorized']
    assert a['measurement_semantics'].startswith('piecewise_constant')

def test_bucy_scalar_riccati_nonstationary_exact_tanh():
    ts=np.linspace(0,2.,9)
    out=s.kalman_bucy([[0]],[[1]],[[1]],[[1]],[0],[[0]],ts.tolist(),[[0.]]*8)
    np.testing.assert_allclose(out['covariances'][:,0,0],np.tanh(ts),atol=2e-9)
    assert out['covariance_psd_checked']
    assert not out['covariance_globally_certified']

def test_bucy_coupled_observation_dynamics_retains_psd():
    A=[[-.8,2.],[-1.5,-.3]]
    Q=[[.2,.03],[.03,.15]]
    H=[[1.,.5],[-.2,1.]]
    R=[[.4,.07],[.07,.5]]
    out=s.kalman_bucy(A,Q,H,R,[1,-1],[[1.,.1],[.1,.8]],
                       [0.,.15,.4,.9],[[0.,0.],[1.,-1.],[.3,.1]])
    assert np.linalg.eigvalsh(out['covariances']).min()>0
    assert np.isfinite(out['means']).all() and not out['uses_future']

def test_irregular_scalar_exact_ou_variance_and_missing_data():
    t=[.3,2.2,2.35]
    a=.7;q=.2;mean=2.;P=.3
    out=s.irregular_filter([[-a]],[[q]],[[1]],[[.1]],[mean],[[P]],t,
                           [None,None,None])
    for i,stamp in enumerate([0.]+t):
        f=np.exp(-a*stamp)
        expected=P*f*f+q*(-np.expm1(-2*a*stamp))/(2*a)
        assert out['means'][i,0]==pytest.approx(mean*f,abs=2e-10)
        assert out['covariances'][i,0,0]==pytest.approx(expected,abs=2e-10)
    assert out['missing_samples']==3
    assert out['imputed_missing_samples']==0
    assert out['nis']==(None,None,None)
    assert out['log_likelihood']==0.

def test_irregular_two_observations_analytic_bayesian_updates():
    out=s.irregular_filter([[0]],[[1]],[[1]],[[.5]],[0],[[1]],
                           [0.5,1.7],[[1.],None])
    pred=1.5
    gain=pred/(pred+.5)
    assert out['means'][1,0]==pytest.approx(gain)
    assert out['covariances'][1,0,0]==pytest.approx((1-gain)*pred)
    assert out['means'][2,0]==pytest.approx(out['means'][1,0])
    assert out['covariances'][2,0,0]==pytest.approx((1-gain)*pred+1.2)
    assert out['nis'][1] is None

def test_irregular_coupled_exact_van_loan_vs_direct_block_exponential():
    A=np.array([[-.4,1],[-2.,-.2]])
    Q=np.array([[.25,.05],[.05,.4]])
    P0=np.array([[.4,.1],[.1,.7]])
    dt=1.8
    F=expm(A*dt)
    Z=np.zeros_like(A)
    v=expm(np.block([[A,Q],[Z,-A.T]])*dt)
    W=v[:2,2:]@F.T
    out=s.irregular_filter(A,Q,[[1,0]],[[.1]],[.1,.7],P0,[dt],[None])
    np.testing.assert_allclose(out['means'][1],F@[.1,.7],atol=1e-10)
    np.testing.assert_allclose(out['covariances'][1],F@P0@F.T+W,atol=1e-10)
    assert out['segment_counts']==(2,)

def test_fixed_lag_matches_bayesian_conditioning_and_no_late_rewrites():
    # x0~N(0,1), process var .2/time, y1=x.5+noise var .5.
    # E[x0|y1] = y1 / (1 + .1 + .5) = y1/1.6.
    inp=([0.5,1.5,2.5],[[2.],[-1.],[10.]])
    out=s.irregular_filter([[0]],[[.2]],[[1]],[[.5]],[0],[[1]],*inp)
    lag=s.fixed_lag_smooth(out,1)
    assert lag['state_indices']==(0,1,2)
    assert lag['state_times'].tolist()==[0.,.5,1.5]
    assert lag['release_times'].tolist()==[.5,1.5,2.5]
    assert lag['means'][0,0]==pytest.approx(2./1.6,abs=1e-12)
    assert lag['trailing_pending_states']==1
    prior=s.irregular_filter([[0]],[[.2]],[[1]],[[.5]],[0],[[1]],
                             inp[0][:2],inp[1][:2])
    shorter=s.fixed_lag_smooth(prior,1)
    np.testing.assert_allclose(lag['means'][:2],shorter['means'])
    np.testing.assert_allclose(lag['covariances'][:2],shorter['covariances'])
    assert not lag['uses_future_beyond_release']

def test_fixed_lag_zero_equals_causal_filter_and_psd_lag_two():
    out=s.irregular_filter([[-.2]],[[.3]],[[1]],[[.6]],[1.],[[.7]],
                           [.5,1.,2.,3.],[[.3],[1.],[0.],[-1.]])
    z=s.fixed_lag_smooth(out,0)
    np.testing.assert_allclose(z['means'],out['means'])
    np.testing.assert_allclose(z['covariances'],out['covariances'])
    r=s.fixed_lag_smooth(out,2)
    assert r['state_indices']==(0,1,2)
    assert len(r['means'])==3 and r['trailing_pending_states']==2
    assert np.linalg.eigvalsh(r['covariances']).min()>=0

@pytest.mark.parametrize('bad',[0.,-1.,float('nan'),float('inf')])
def test_irregular_refuses_noncausal_timestamps(bad):
    with pytest.raises(ValueError):
        s.irregular_filter([[-1]],[[.2]],[[1]],[[1]],[0],[[1]],
                           [bad],[None])

def test_irregular_refuses_nonmonotone_misaligned_and_invalid_observations():
    args=([[-1]],[[.2]],[[1]],[[1]],[0],[[1]])
    with pytest.raises(ValueError):
        s.irregular_filter(*args,[.5,.4],[None,None])
    with pytest.raises(ValueError):
        s.irregular_filter(*args,[.5],[None,None])
    with pytest.raises(ValueError):
        s.irregular_filter(*args,[.5],[[float('nan')]])
    with pytest.raises(ValueError):
        s.irregular_filter(*args,[.5],[[0,1]])

def test_bucy_rejects_invalid_noise_and_nonincreasing_time():
    with pytest.raises(ValueError):
        s.kalman_bucy([[0]],[[1]],[[1]],[[-1]],[0],[[1]],
                      [0.,1.],[[1.]])
    with pytest.raises(ValueError):
        s.kalman_bucy([[0]],[[1]],[[1]],[[1]],[0],[[1]],
                      [0.,0.],[[1.]])

def test_fixed_lag_rejects_modified_prediction_covariance():
    out=s.irregular_filter([[0]],[[0]],[[1]],[[.2]],[0],[[1]],
                           [.5,1.],[None,[1.]])
    out['predicted_cov'][0,0,0]=-2
    with pytest.raises(ValueError,match='negative eigenvalue'):
        s.fixed_lag_smooth(out,1)

def test_total_irregular_segment_budget_refuses_excessive_work():
    with pytest.raises(ValueError,match="segment.*budget"):
        s.irregular_filter([[0]],[[.1]],[[1]],[[.5]],[0],[[1]],
                           [10.],[None],max_segment=.001)

def test_fixed_lag_no_unreleased_state_beyond_available_history():
    filtered=s.irregular_filter([[0]],[[.1]],[[1]],[[.5]],[0],[[1]],
                                [.5],[None])
    with pytest.raises(ValueError,match="lag cannot exceed"):
        s.fixed_lag_smooth(filtered,2)

def test_bucy_prefix_does_not_change_when_later_rate_changes():
    model=([[0]],[[1]],[[1]],[[1]],[0],[[1]])
    before=s.kalman_bucy(*model,[0.,1.],[[2.]])
    after=s.kalman_bucy(*model,[0.,1.,2.],[[2.],[-500.]])
    np.testing.assert_allclose(before['means'],after['means'][:2],atol=1e-10)
    np.testing.assert_allclose(before['covariances'],after['covariances'][:2],
                               atol=1e-10)
