import itertools
import numpy as np
import pytest
from scipy.stats import norm
from cognitum.research import ssm_stochastic as s


def test_markov():
    P=[[.8,.2],[.3,.7]];r=s.markov(P,[1,0],32);t=np.arange(33);np.testing.assert_allclose(r['states'][:,0],.6+.4*.5**t);assert not r['execution_authorized']


def test_ctmc():
    t=np.linspace(0,3,21);r=s.ctmc([[-2,2],[3,-3]],[1,0],t);np.testing.assert_allclose(r['states'][:,0],.6+.4*np.exp(-5*t))

@pytest.mark.parametrize('P,p',[([[.8,.1],[.3,.7]],[1,0]),([[1.1,-.1],[0,1]],[1,0]),([[1,0],[0,1]],[.5,.6])])
def test_markov_refuse(P,p):
    with pytest.raises(ValueError):s.markov(P,p,1)

@pytest.mark.parametrize('dt',[.125,.5,1.])
def test_discretize(dt):
    F,Q=s.discretize([[0,1],[0,0]],[[0,0],[0,2]],dt);np.testing.assert_allclose(F,[[1,dt],[0,1]]);np.testing.assert_allclose(Q,[[2*dt**3/3,dt**2],[dt**2,2*dt]],atol=1e-12)

@pytest.mark.parametrize('seed',[1,13,82])
def test_ou(seed):
    r=s.ou(1.,2.,.7,0.,.125,16,8192,seed);assert abs(np.mean(r['exact'])-r['mean'])<.025;assert abs(np.var(r['exact'])-r['variance'])<.02;assert r['coupled_rmse']<.08


def test_ou_refinement():
    a=s.ou(1,0,1,1,.25,4,8192,2);b=s.ou(1,0,1,1,.0625,16,8192,2);assert b['coupled_rmse']<a['coupled_rmse']/3


def test_ou_replay():
    args=(1,0,1,0,.125,8,64,8);np.testing.assert_array_equal(s.ou(*args)['exact'],s.ou(*args)['exact'])


def test_kalman_batch_smooth():
    # Random walk x0~N(0,1), increment variance dt, measurement variance 1.
    t=np.array([0,.2,.6,1.]);y=[1.,None,-.4];r=s.kalman([[0]],[[1]],[[1]],[[1]],[0],[[1]],[[1],None,[-.4]],np.diff(t).tolist());C=1+np.minimum.outer(t,t);i=[1,3];S=C[np.ix_(i,i)]+np.eye(2);M=C[:,i]@np.linalg.solve(S,[1,-.4]);V=C-C[:,i]@np.linalg.solve(S,C[i,:]);z=s.smooth(r);np.testing.assert_allclose(z['means'][:,0],M,atol=1e-12);np.testing.assert_allclose(z['covariances'][:,0,0],np.diag(V),atol=1e-12);assert z['uses_future'] and r['nis'][1] is None
    assert r['log_likelihood']==pytest.approx(-.5*(2*np.log(2*np.pi)+np.linalg.slogdet(S)[1]+np.array([1,-.4])@np.linalg.solve(S,[1,-.4])))


def test_coupled_kalman():
    P=np.array([[2,.4],[.4,1]]);H=np.array([[1,2]]);R=np.array([[.3]]);m=np.array([1.,0]);y=np.array([2.]);r=s.kalman(np.zeros((2,2)),np.zeros((2,2)),H,R,m,P,[y],[.2]);C=np.linalg.inv(np.linalg.inv(P)+H.T@np.linalg.solve(R,H));M=C@(np.linalg.solve(P,m)+H.T@np.linalg.solve(R,y));np.testing.assert_allclose(r['means'][-1],M,atol=1e-12);np.testing.assert_allclose(r['covariances'][-1],C,atol=1e-12)

@pytest.mark.parametrize('bad',[[[1,2],[0,1]],[[1,2],[2,1]]])
def test_cov_refuse(bad):
    with pytest.raises(ValueError):s.discretize(np.eye(2),bad,.1)

@pytest.mark.parametrize('method',['ekf','cubature'])
def test_nonlinear_linear_limit(method):
    m=[1,2];P=[[2,.5],[.5,1]];a=[1,-1];r=s.nonlinear_update(m,P,0.,.4,(a,[0,0]),method);q=s.gaussian_update(np.array(m),np.array(P),[a],[[.4]],[0]);np.testing.assert_allclose(r['mean'],q[0],atol=1e-12);np.testing.assert_allclose(r['covariance'],q[1],atol=1e-12)


def test_cubature_quadratic():
    # N(1,.25), h=x², two symmetric points: sensor mean 1.25, cross cov .5.
    z=s.nonlinear_update([1],[[.25]],2.,.5,([0],[1]),'cubature');assert z['mean'][0]==pytest.approx(1+.5/1.5*.75);assert z['covariance'][0,0]==pytest.approx(.25-.25/1.5)

@pytest.mark.parametrize('threshold',[.01,1.])
def test_particle_exact(threshold):
    x=np.array([[-1.],[1.]]*128);r=s.particle([[1]],[[0]],[[1]],[[1]],x,[[1]],9,threshold);p=1/(1+np.exp(-2));assert r['means'][0,0]==pytest.approx(2*p-1);assert r['ess'][0]==pytest.approx(128/(p*p+(1-p)**2));assert r['resampled']==(threshold==1.,);assert r['weights'].sum()==pytest.approx(1)

@pytest.mark.parametrize('seed',[3,19,76])
def test_particle_gaussian(seed):
    rng=np.random.default_rng(seed+1000);x=rng.normal(size=(4096,1));r=s.particle([[1]],[[.2]],[[1]],[[.7]],x,[[.5]],seed,.7);assert abs(r['means'][0,0]-.5*1.2/1.9)<.05


def test_particle_missing():
    x=[[-1],[1]];r=s.particle([[1]],[[0]],[[1]],[[1]],x,[None],1);np.testing.assert_allclose(r['means'],[[0]]);assert r['log_likelihood']==0


def test_hmm_enumeration():
    P=np.array([[.8,.2],[.3,.7]]);E=np.array([[.7,.3],[.2,.8]]);p=np.array([.6,.4]);obs=[0,1,1];z=s.hmm(P,E,p,obs);paths=list(itertools.product(range(2),repeat=len(obs)));weights=np.array([p[a[0]]*E[a[0],obs[0]]*np.prod([P[a[j-1],a[j]]*E[a[j],obs[j]] for j in range(1,len(obs))]) for a in paths]);total=weights.sum();post=np.array([[sum(w for a,w in zip(paths,weights) if a[j]==i)/total for i in range(2)] for j in range(len(obs))]);np.testing.assert_allclose(z['smoothed'],post);assert z['viterbi']==paths[np.argmax(weights)];assert z['log_likelihood']==pytest.approx(np.log(total))


def test_hmm_impossible():
    with pytest.raises(ValueError):s.hmm([[1,0],[0,1]],[[1,0],[1,0]],[.5,.5],[1])
