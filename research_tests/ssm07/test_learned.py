import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import eval_legendre
from scipy.linalg import expm
from cognitum.research import ssm_learned as s


@pytest.mark.parametrize('n',[1,4,8,16])
def test_hippo(n):
    u=[1,-2,.3,4];dt=[.2,.7,.1,1.2];r=s.hippo(u,dt,n);ends=np.r_[0,np.cumsum(dt)]
    for i,t in enumerate(ends[1:]):
        ref=[sum(u[j]*quad(lambda x:np.sqrt(2*k+1)*eval_legendre(k,2*x/t-1)/t,ends[j],ends[j+1],epsabs=1e-12)[0] for j in range(i+1)) for k in range(n)]
        np.testing.assert_allclose(r['coefficients'][i],ref,atol=1e-11);assert r['mean_square_truncation'][i]==pytest.approx(np.dot(dt[:i+1],np.square(u[:i+1]))/t-np.dot(ref,ref),abs=1e-11)


def test_hippo_truncation():
    e=[s.hippo([1,-1],[1,1],n)['mean_square_truncation'][-1] for n in (1,2,4,8,16)];assert np.all(np.diff(e)<=1e-12) and e[-1]<e[0]/10


@pytest.mark.parametrize('n',[1,4,8,16])
def test_legs(n):
    r=s.legs(n);V=r['eigenbasis'];q=r['low_rank'];M=np.diag(r['diagonal'])-np.outer(q,q.conj());np.testing.assert_allclose(V@M@V.conj().T,r['A'],atol=1e-11);np.testing.assert_allclose(V.conj().T@V,np.eye(n),atol=1e-11);np.testing.assert_allclose(np.sort(np.linalg.eigvals(r['A'])),-np.arange(n,0,-1))


@pytest.mark.parametrize('n,dt',[(1,.1),(4,.3),(8,1.),(16,2.)])
def test_s4(n,dt):
    a=s.legs(n);z=s.s4_discretize(n,dt);A=a['A'];B=a['B'];F,G=z['F'],z['G'];np.testing.assert_allclose(F,np.linalg.solve(np.eye(n)-dt*A/2,np.eye(n)+dt*A/2),atol=1e-11);np.testing.assert_allclose(G,np.linalg.solve(np.eye(n)-dt*A/2,dt*B),atol=1e-11);assert max(abs(np.linalg.eigvals(F)))<1


@pytest.mark.parametrize('complex_', [False,True])
def test_convolution(complex_):
    rng=np.random.default_rng(12);F=np.diag([.8,.6]);G=rng.normal(size=(2,2));C=rng.normal(size=(2,2));U=rng.normal(size=(73,2));h=[1.,-1.]
    if complex_:U=U+1j*U[::-1]
    a=s.recurrence(F,G,C,U,h);b=s.convolution(F,G,C,U,h);np.testing.assert_allclose(a['outputs'],b['outputs'],atol=1e-12)


@pytest.mark.parametrize('n',[1,2,3,7,33,512])
def test_scan(n):
    rng=np.random.default_rng(n);A=rng.uniform(.1,.99,(n,4));B=rng.normal(size=(n,4));h=rng.normal(size=4);np.testing.assert_allclose(s.affine_scan(A,B,h),s.serial(A,B,h),atol=1e-12)


def test_diagonal():
    a=np.array([-.2+1j,-.2-1j,-.8]);B=np.array([[1,2],[1,2],[.3,.5]]);C=np.array([[1,1,1],[1j,-1j,1]]);u=np.random.default_rng(42).normal(size=(60,2));d=np.linspace(.01,.5,len(u));h=np.array([.2+.3j,.2-.3j,.1]);z=s.diag_steps(a,B,C,u,h,d,True);q=s.diag_steps(a,B,C,u,h,d);np.testing.assert_allclose(z['outputs'],q['outputs'],atol=1e-12);assert max(abs(z['outputs'].imag.ravel()))<1e-12
    ref=h.copy()
    for i,dt in enumerate(d):
        M=np.block([[np.diag(a),B],[np.zeros((2,5))]]);D=expm(M*dt);ref=D[:3,:3]@ref+D[:3,3:]@u[i];np.testing.assert_allclose(z['states'][i],ref,atol=1e-12)
    v=s.diag_steps(a,B,C,u[:19],h,d[:19],True);w=s.diag_steps(a,B,C,u[19:],v['final_state'],d[19:],True);np.testing.assert_allclose(np.vstack((v['outputs'],w['outputs'])),z['outputs'],atol=1e-12)


def test_long_memory():
    u=np.zeros((512,1));u[0]=1;z=s.diag_steps([-.001],[[1]],[[1]],u,[0],[1.]*512,True);np.testing.assert_allclose(z['outputs'][:,0],(-np.expm1(-.001)/.001)*np.exp(-.001*np.arange(512)),rtol=1e-12)


def test_selective():
    args=([.7,.2],[-.4,-1],.3,-1,[[1,.2],[.2,-.1]],[[.4,.3],[1,-.2]],[.1,.2]);u=np.random.default_rng(3).normal(size=100);z=s.selective(u,*args,scan=True);q=s.selective(u,*args);np.testing.assert_allclose(z['outputs'],q['outputs'],atol=1e-12);assert np.std(z['delta'])>.01;u[40:]+=2;v=s.selective(u,*args,scan=True);np.testing.assert_array_equal(v['outputs'][:40],z['outputs'][:40]);assert np.max(abs(v['outputs'][40:]-z['outputs'][40:]))>.1


@pytest.mark.parametrize('seed',[2,13,51])
def test_train(seed):
    rng=np.random.default_rng(seed);u=rng.normal(size=256);v=rng.normal(size=80);f=lambda x:s.recurrence(np.diag([.35,.85]),[[1],[1]],[[.7,-.3]],x[:,None],[0,0])['outputs'][:,0];z=s.diagonal_fit(u,f(u),v,f(v),[.25,.75]);np.testing.assert_allclose(z['poles'],[.35,.85],atol=1e-7);assert z['heldout_rmse']<1e-8 and z['gradient_error']<1e-6


@pytest.mark.parametrize('kind',['s4','s4d'])
def test_structured_readout(kind):
    rng=np.random.default_rng(3);u=rng.normal(size=(120,1));v=rng.normal(size=(70,1));n=4
    if kind=='s4':
        z=s.s4_discretize(n,.2);f=lambda x:s.recurrence(z['F'],z['G'],np.eye(n),x,np.zeros(n))['states']
    else:
        rates=np.array([-.5+1j,-.5-1j,-.5+2j,-.5-2j]);f=lambda x:s.diag_steps(rates,np.ones((n,1)),np.eye(n),x,np.zeros(n),[.2]*len(x))['states']
    X,T=f(u),f(v);w=np.array([1,1,.5,.5]);r=s.fit_readout(X,(X@w)[:,None],T,(T@w)[:,None]);np.testing.assert_allclose(r['readout'],w[None,:],atol=1e-10);assert r['heldout_rmse']<1e-10


@pytest.mark.parametrize('fn',[lambda:s.hippo([1],[0],2),lambda:s.legs(17),lambda:s.diag_steps([.1],[[1]],[[1]],[[1]],[0],[1]),lambda:s.affine_scan([[1]],[[1]],[0,0]),lambda:s.fit_readout([[1,1],[2,2]],[[1],[2]],[[1,1]],[[1]])])
def test_refusal(fn):
    with pytest.raises(ValueError):fn()
