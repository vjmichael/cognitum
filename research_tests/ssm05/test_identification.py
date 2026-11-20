import numpy as np
import pytest
from cognitum.research import ssm_identification as s


def data(n=2):
    r=np.random.default_rng(42);return r.normal(size=(256,n)),r.normal(size=(80,n))


def test_normal():
    z=s.normal_estimate([1,2,3,4],[0,2,3,4]);assert z['mean']==2.5 and z['variance']==1.25;np.testing.assert_allclose(z['posterior'],[5/3,6,5,4+2.5+100/24]);assert not z['certified']

@pytest.mark.parametrize('x,p',[([1,1],[0,1,1,1]),([1,2],[0,0,1,1]),([1],[0,1,1,1])])
def test_normal_refuse(x,p):
    with pytest.raises(ValueError):s.normal_estimate(x,p)

@pytest.mark.parametrize('seed',[2,11,81])
def test_em(seed):
    rng=np.random.default_rng(seed);x=np.r_[rng.normal(-3,.5,1000),rng.normal(3,.7,1000)];z=s.mixture_em(x,[-2,2],[1,1],[.5,.5]);np.testing.assert_allclose(z['means'],[-3,3],atol=.08);np.testing.assert_allclose(z['variances'],[.25,.49],atol=.06);assert min(np.diff(z['log_likelihood']))>=-1e-8 and not z['global_optimum']


def test_lti():
    X,T=data();U,V=data(1);A=np.array([[.8,.1],[-.2,.4]]);B=np.array([[1.],[-.5]]);z=s.identify_lti(X,U,X@A.T+U@B.T,T,V,T@A.T+V@B.T);np.testing.assert_allclose(z['A'],A,atol=1e-12);np.testing.assert_allclose(z['B'],B,atol=1e-12);assert z['heldout_rmse']<1e-12


def test_lti_rank():
    X,T=data();U=X[:,:1];V=T[:,:1]
    with pytest.raises(ValueError,match='rank'):s.identify_lti(X,U,X,T,V,T)

@pytest.mark.parametrize('seed',[3,17,80])
def test_lti_noisy(seed):
    rng=np.random.default_rng(seed);X=rng.normal(size=(1024,2));U=rng.normal(size=(1024,1));T=rng.normal(size=(80,2));V=rng.normal(size=(80,1));A=np.array([[.7,.1],[.2,.5]]);B=np.array([[1],[.2]]);z=s.identify_lti(X,U,X@A.T+U@B.T+rng.normal(0,.05,X.shape),T,V,T@A.T+V@B.T);assert z['heldout_rmse']<.01

@pytest.mark.parametrize('mimo',[False,True])
def test_era(mimo):
    A=np.diag([.4,.8]);B=np.eye(2) if mimo else np.ones((2,1));C=np.eye(2) if mimo else np.ones((1,2));G=np.array([np.zeros((len(C),B.shape[1]))]+[C@np.linalg.matrix_power(A,i)@B for i in range(14)]);z=s.era(G,2,5);np.testing.assert_allclose(np.sort(np.linalg.eigvals(z['A'])),[.4,.8]);assert z['impulse_rmse']<1e-12 and z['similarity_ambiguous']


def test_era_rank():
    with pytest.raises(ValueError):s.era(np.ones((15,1,1)),2,5)


def rhs(X):
    x,y=X.T;return np.column_stack((-x+2*x*y,-2*y+x*x))


def test_sindy():
    X,T=data();z=s.sindy(X,rhs(X),T,rhs(T),2,.1);e=dict(zip(z['exponents'],z['coefficients']));np.testing.assert_allclose(e[(1,1)],[2,0],atol=1e-12);np.testing.assert_allclose(e[(2,0)],[0,1],atol=1e-12);assert np.count_nonzero(z['coefficients'])==4 and z['heldout_rmse']<1e-12


def test_sindy_wrong_library():
    X,T=data();z=s.sindy(X,rhs(X),T,rhs(T),1,.1);assert z['heldout_rmse']>.5


def test_sindy_noise():
    X,T=data();rng=np.random.default_rng(1);z=s.sindy(X,rhs(X)+rng.normal(0,.02,X.shape),T,rhs(T),2,.1);assert np.count_nonzero(z['coefficients'])==4 and z['heldout_rmse']<.01


def test_dmd():
    X,T=data();A=np.diag([.6,.8]);z=s.dmd(X,X@A.T,T,T@A.T);np.testing.assert_allclose(np.sort(z['eigenvalues']),[.6,.8]);assert z['heldout_rmse']<1e-12


def test_edmd():
    X,T=data(1);z=s.dmd(X,.7*X,T,.7*T,degree=3);np.testing.assert_allclose(np.sort(z['eigenvalues'].real),[.343,.49,.7,1]);assert z['heldout_rmse']<1e-12 and not z['invariance_certified']


def test_edmd_noninvariant():
    X,T=data(1);z=s.dmd(X,np.sin(X),T,np.sin(T),degree=2);assert z['heldout_rmse']>.1


def test_operator():
    X,T=data();z=s.operator_inference(X,rhs(X),T,rhs(T));assert z['heldout_rmse']<1e-12

@pytest.mark.parametrize('noise',[0,.05])
def test_conservative(noise):
    X,T=data();rng=np.random.default_rng(11);f=lambda X:np.column_stack((-X[:,1]*(1+X[:,0]),X[:,0]*(1+X[:,0])));z=s.operator_inference(X,f(X)+rng.normal(0,noise,X.shape),T,f(T),conservative=True);assert z['heldout_rmse']<max(1e-12,noise);assert z['coefficient_conservation_residual']<1e-12;D,_=s.library(T,2);np.testing.assert_allclose(np.sum(T*(D@z['coefficients']),1),0,atol=1e-12)


def test_conservative_wrong_model():
    X,T=data();z=s.operator_inference(X,-X,T,-T,conservative=True);assert z['heldout_rmse']>.5 and z['coefficient_conservation_residual']<1e-12

@pytest.mark.parametrize('deg',[0,4,True])
def test_library_budget(deg):
    with pytest.raises(ValueError):s.library([[1,2],[2,3]],deg)
