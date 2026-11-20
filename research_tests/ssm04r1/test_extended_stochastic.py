import itertools
import numpy as np
import pytest
from scipy.stats import norm
from cognitum.research import ssm_stochastic as s, ssm_stochastic_extended as e

@pytest.mark.parametrize('seed',[2,19,51])
def test_nonlinear_sde(seed):
    z=e.nonlinear_sde([[-1]],[.4],[.1],[.6],[.2],[.3],.125,16,2048,seed)
    assert z['half_rmse']<z['coarse_rmse'] and not z['certified']
    np.testing.assert_array_equal(z['fine'],e.nonlinear_sde([[-1]],[.4],[.1],[.6],[.2],[.3],.125,16,2048,seed)['fine'])


def test_sde_brownian():
    z=e.nonlinear_sde([[0,0],[0,0]],[0,0],[1,-1],[.4,.5],[0,0],[0,0],.125,8,4096,4)
    np.testing.assert_allclose(z['coarse'],z['fine'],atol=1e-12);np.testing.assert_allclose(z['mean'],[1,-1],atol=.03);np.testing.assert_allclose(z['variance'],[.16,.25],atol=.02)


def test_sde_refusal():
    with pytest.raises(ValueError):e.nonlinear_sde([[0]],[0],[0],[.1],[.2],[0],.125,8,10,1)

@pytest.mark.parametrize('cells',[16,32,64])
def test_heat_mode(cells):
    x=(np.arange(cells)+.5)/cells;p=(1+.5*np.cos(np.pi*x))/cells;t=[0,.1,.5]
    z=e.fokker_planck(0,1,cells,[0,0,0],.2,p,t);lam=4*.2*cells**2*np.sin(np.pi/(2*cells))**2
    np.testing.assert_allclose(z['masses'],(1+.5*np.exp(-lam*np.array(t)[:,None])*np.cos(np.pi*x))/cells,atol=1e-12);assert z['mass_error']<1e-10 and z['masses'].min()>=0


def test_fp_refining():
    errs=[]
    for n in [16,32,64]:
        x=(np.arange(n)+.5)/n;z=e.fokker_planck(0,1,n,[0,0,0],.2,(1+.5*np.cos(np.pi*x))/n,[.2]);ref=(1+.5*np.exp(-.2*np.pi**2*.2)*np.cos(np.pi*x))/n;errs.append(np.sum(abs(z['masses'][0]-ref)))
    assert errs[2]<errs[1]/3 and errs[1]<errs[0]/3


def test_fp_drift():
    p=np.zeros(24);p[0]=1;z=e.fokker_planck(0,1,24,[-1,.3,1],.05,p,[0,.5,1]);assert z['masses'].min()>=0 and np.all(np.diff(z['masses']@z['centers'])>=0)


def test_fp_refuse():
    with pytest.raises(ValueError):e.fokker_planck(0,1,4,[0,0,0],-.1,[.25]*4,[1])


def ref_filter(F,Q,H,R,m,P,obs):
    ms=[np.array(m)];ps=[np.array(P)];m,P=ms[0],ps[0];F,Q=np.array(F),np.array(Q)
    for y in obs:
        m=F@m;P=F@P@F.T+Q
        if y is not None:m,P,*_=s.gaussian_update(m,P,H,R,y)
        ms.append(m);ps.append(P)
    return np.array(ms),np.array(ps)

@pytest.mark.parametrize('method',[e.sqrt_filter,e.information_filter])
@pytest.mark.parametrize('missing',[False,True])
def test_robust_filter(method,missing):
    F=[[1,.2],[0,.9]];Q=[[.1,.02],[.02,.05]];H=[[1,2]];R=[[.03]];m=[1,-1];P=[[2,.5],[.5,1]];obs=[[.3],None if missing else [.1],[-.4]];z=method(F,Q,H,R,m,P,obs);a,b=ref_filter(F,Q,H,R,m,P,obs);np.testing.assert_allclose(z['means'],a,atol=1e-12);np.testing.assert_allclose(z['covariances'],b,atol=1e-12)
    if method==e.sqrt_filter:assert np.all(np.diagonal(z['factors'],axis1=1,axis2=2)>0)
    else:np.testing.assert_allclose(z['information']@z['covariances'],np.tile(np.eye(2),(4,1,1)),atol=1e-12)


def test_sqrt_ill_conditioned():
    z=e.sqrt_filter(np.eye(2),np.zeros((2,2)),np.eye(2),np.diag([1e-12,1]),[0,0],np.diag([1e-10,10]),[[1,1]])
    np.testing.assert_allclose(z['covariances'][-1].diagonal(),[1/(1e10+1e12),10/11],rtol=1e-10)

@pytest.mark.parametrize('method',[e.sqrt_filter,e.information_filter])
def test_robust_refuse(method):
    with pytest.raises(ValueError):method([[1]],[[0]],[[1]],[[0]],[0],[[1]],[[1]])


def test_ukf_linear():
    F=[[1,.2],[0,.9]];Q=[[.1,.02],[.02,.05]];H=[[1,2]];R=[[.2]];m=[1,-1];P=[[2,.5],[.5,1]];obs=[[.3],None,[-.4]];z=e.unscented(F,[0,0],[0,0],Q,H,[[0,0]],R,m,P,obs);a,b=ref_filter(F,Q,H,R,m,P,obs);np.testing.assert_allclose(z['means'],a,atol=1e-12);np.testing.assert_allclose(z['covariances'],b,atol=1e-12)


def test_ukf_quadratic():
    # Sigma points of N(1,.25): x=1,1±sqrt(.5), weights .5,.25,.25.
    z=e.unscented([[1]],[0],[0],[[0]],[[0]],[[1]],[[.5]],[1],[[.25]],[[2]])
    assert z['means'][-1,0]==pytest.approx(1+.5*.75/1.5625);assert z['covariances'][-1,0,0]==pytest.approx(.25-.25/1.5625)


def test_ukf_nonlinear_prediction():
    z=e.unscented([[.5]],[.4],[.1],[[.2]],[[1]],[[.2]],[[.3]],[.2],[[.5]],[None,[.1],[.4]])
    assert z['means'].shape==(4,1) and np.min(z['covariances'])>0 and z['nis'][0] is None

@pytest.mark.parametrize('seed',[1,13,71])
def test_ffbs(seed):
    t=np.array([0,.2,.6,1.]);r=s.kalman([[0]],[[1]],[[1]],[[1]],[0],[[1]],[[1],None,[-.4]],np.diff(t).tolist());z=e.posterior_paths(r,8192,seed);X=z['paths'][:,:,0];C=1+np.minimum.outer(t,t);i=[1,3];S=C[np.ix_(i,i)]+np.eye(2);M=C[:,i]@np.linalg.solve(S,[1,-.4]);V=C-C[:,i]@np.linalg.solve(S,C[i,:]);np.testing.assert_allclose(X.mean(0),M,atol=.035);np.testing.assert_allclose(np.cov(X.T),V,atol=.04);assert z['uses_future']

@pytest.mark.parametrize('seed',[3,18,83])
def test_ensemble(seed):
    X=np.random.default_rng(seed+1000).normal(size=(4096,1));z=e.ensemble([[1]],[[.2]],[[1]],[[.7]],X,[[.5]],seed);assert abs(z['means'][0,0]-.5*1.2/1.9)<.05;assert abs(z['covariances'][0,0,0]-1.2*.7/1.9)<.04


def test_ensemble_missing():
    z=e.ensemble([[2]],[[0]],[[1]],[[1]],[[-1],[0],[1]],[None],2);np.testing.assert_allclose(z['means'],[[0]]);np.testing.assert_allclose(z['covariances'],[[[4]]])


def test_switching_enumeration():
    P=np.array([[.8,.2],[.3,.7]]);p=[.6,.4];F=[.5,1.5];Q=[.2,.4];obs=[.2,1.];z=e.switching(P,p,[([[a]],[[b]]) for a,b in zip(F,Q)],[1],[[.5]],[[y] for y in obs],[[1]],[[.3]])
    parts=[]
    for i,j in itertools.product(range(2),repeat=2):
        m,v=1.,.5;w=p[i]*P[i,j]
        for k,y in zip([i,j],obs):
            m=F[k]*m;v=F[k]**2*v+Q[k];w*=norm.pdf(y,m,np.sqrt(v+.3));gain=v/(v+.3);m+=gain*(y-m);v*=1-gain
        parts.append((j,m,v,w))
    w=sum(p[3] for p in parts);m=sum(p[1]*p[3] for p in parts)/w;v=sum((p[2]+(p[1]-m)**2)*p[3] for p in parts)/w;assert z['means'][-1,0]==pytest.approx(m);assert z['covariances'][-1,0,0]==pytest.approx(v);assert z['log_likelihood']==pytest.approx(np.log(w));assert z['regime_probabilities'][-1,0]==pytest.approx(sum(p[3] for p in parts if p[0]==0)/w)


def test_switching_missing_permutation():
    P=[[.8,.2],[.3,.7]];modes=[([[.5]],[[.2]]),([[1.5]],[[.4]])];args=([1],[[.5]],[None,[.2]],[[1]],[[.3]]);a=e.switching(P,[.6,.4],modes,*args);b=e.switching(np.array(P)[::-1,::-1],[.4,.6],modes[::-1],*args);np.testing.assert_allclose(a['means'],b['means']);np.testing.assert_allclose(a['regime_probabilities'],b['regime_probabilities'][:,::-1]);assert a['components']==4


def test_switching_budget():
    with pytest.raises(ValueError):e.switching([[.5,.5],[.5,.5]],[.5,.5],[([[1]],[[1]])]*2,[0],[[1]],[None]*13,[[1]],[[1]])
