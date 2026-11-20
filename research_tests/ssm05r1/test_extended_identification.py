import numpy as np
import pytest
from cognitum.research import ssm_identification_extended as e


def simulate(seed,n=1024):
    rng=np.random.default_rng(seed);x=rng.normal();y=[]
    for _ in range(n):
        x=.8*x+rng.normal(scale=np.sqrt(.3));y.append(x+rng.normal(scale=np.sqrt(.2)))
    return y


@pytest.mark.parametrize('seed',[7,23,91])
def test_em(seed):
    y=simulate(seed,1536);y[::17]=[None]*len(y[::17]);z=e.latent_em(y,.5,.5,.5,iterations=180)
    assert np.min(np.diff(z['log_likelihood']))>=-1e-7 and abs(z['phi']-.8)<.09
    assert abs(z['process_variance']-.3)<.1 and abs(z['measurement_variance']-.2)<.1
    assert z['uses_future'] and not z['global_optimum']


def test_em_joint():
    y=[.4,None,-.3,1.,.1];z=e.latent_em(y,.5,.7,.3,iterations=1);a=z['phi'];q=z['process_variance'];r=z['measurement_variance'];n=len(y)+1
    C=np.zeros((n,n));C[0,0]=1
    for i in range(1,n):
        C[i,:i]=a*C[i-1,:i];C[:i,i]=C[i,:i];C[i,i]=a*a*C[i-1,i-1]+q
    inds=[1,3,4,5];v=np.array([.4,-.3,1.,.1]);S=C[np.ix_(inds,inds)]+r*np.eye(4);M=C[:,inds]@np.linalg.solve(S,v);V=C-C[:,inds]@np.linalg.solve(S,C[inds,:]);np.testing.assert_allclose(z['means'],M,atol=1e-12);np.testing.assert_allclose(z['variances'],V.diagonal(),atol=1e-12)
    assert z['log_likelihood'][-1]==pytest.approx(-.5*(4*np.log(2*np.pi)+np.linalg.slogdet(S)[1]+v@np.linalg.solve(S,v)))


def test_em_bad():
    with pytest.raises(ValueError):e.latent_em([None]*6,.5,.5,.5)


@pytest.mark.parametrize('seed',[3,11,88])
def test_noisy_era(seed):
    rng=np.random.default_rng(seed);g=np.array([0]+[.8**i+.4**i for i in range(23)])[:,None,None];a=g+rng.normal(0,.0001,g.shape);b=g+rng.normal(0,.0001,g.shape);z=e.noisy_era(a,b,g,[1,2],8);assert z['order']==2 and z['test_rmse']<.001
    z2=e.noisy_era(a,b,g+10,[1,2],8);assert z2['order']==z['order'] and z2['validation_rmse']==z['validation_rmse']


def test_era_no_order():
    with pytest.raises(ValueError):e.noisy_era(np.ones((20,1,1)),np.ones((20,1,1)),np.ones((20,1,1)),[2],5)


def trajectories(dt,initials):
    t=np.arange(1001)*dt;return [np.column_stack((x*np.cos(t)-y*np.sin(t),x*np.sin(t)+y*np.cos(t))) for x,y in initials]


@pytest.mark.parametrize('noise',[0,0.0005])
def test_weak(noise):
    a=trajectories(.01,[(1,0),(0,2),(2,1)]);b=trajectories(.01,[(.5,1.4),(-2,-1)]);rng=np.random.default_rng(9);a=[x+rng.normal(0,noise,x.shape) for x in a];z=e.weak_sindy(a,b,.01,100,2,.05);D=dict(zip(z['exponents'],z['coefficients']));np.testing.assert_allclose(D[(1,0)],[0,1],atol=.01);np.testing.assert_allclose(D[(0,1)],[-1,0],atol=.01);assert np.count_nonzero(z['coefficients'])==2 and z['weak_heldout_rmse']<.005


def test_weak_rank():
    with pytest.raises(ValueError):e.weak_sindy([np.ones((101,2))],[np.ones((101,2))],.01,20,2,.1)


@pytest.mark.parametrize('noise',[0,.02])
def test_metric(noise):
    rng=np.random.default_rng(12);X=rng.normal(size=(256,2));T=rng.normal(size=(80,2));P=np.array([[2.,.3],[.3,1.]]);A=np.linalg.solve(P,np.array([[0,-1],[1,0]]));f=lambda x:x@A.T*(1+x[:,:1]);z=e.metric_operator(X,f(X)+rng.normal(0,noise,X.shape),T,f(T),P);assert z['heldout_rmse']<max(1e-12,noise) and z['coefficient_conservation_residual']<1e-12


def test_metric_wrong():
    rng=np.random.default_rng(12);X=rng.normal(size=(256,2));T=rng.normal(size=(80,2));z=e.metric_operator(X,-X,T,-T,[[2,.3],[.3,1]]);assert z['heldout_rmse']>.5


def test_forecast():
    t=np.arange(240);y=.03*t+np.sin(2*np.pi*t/12);z=e.rolling_forecast(y,120,3,12);assert z['rmse']<.001 and z['rmse']<z['seasonal_rmse'] and z['rmse']<z['persistence_rmse'];assert z['interval_count']==111 and not z['coverage_guaranteed']


def test_no_leakage():
    t=np.arange(160);y=np.sin(2*np.pi*t/12)+.02*t;z=e.rolling_forecast(y,80,3,12);y[100:]+=20;q=e.rolling_forecast(y,80,3,12);np.testing.assert_array_equal(z['predictions'][:21],q['predictions'][:21]);np.testing.assert_array_equal(z['upper'][:21],q['upper'][:21])


def test_forecast_refuse():
    with pytest.raises(ValueError):e.rolling_forecast([1]*100,20,3,12)


@pytest.mark.parametrize('seed',[4,16,91])
def test_change(seed):
    rng=np.random.default_rng(seed);ref=rng.normal(size=1024);C=rng.normal(size=(999,32));M=rng.normal(size=(1000,32));Z=rng.normal(1.5,1,size=(1000,32));a=e.calibrated_change(ref,C,M);b=e.calibrated_change(ref,C,Z);assert a['threshold']==b['threshold'];assert a['alarms'].mean()<.085 and b['alarms'].mean()>.9;assert not a['repeated_monitoring_guaranteed']


def test_change_insufficient():
    with pytest.raises(ValueError,match='insufficient'):e.calibrated_change(np.arange(20),np.zeros((4,4)),np.zeros((1,4)))


def test_change_outlier():
    rng=np.random.default_rng(7);ref=rng.normal(size=1024);C=rng.normal(size=(999,32));M=np.zeros((2,32));M[0,0]=1e7;M[1]=2;z=e.calibrated_change(ref,C,M);assert not z['alarms'][0] and z['alarms'][1]
