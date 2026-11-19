import numpy as np
import pytest
from scipy.integrate import quad
from cognitum.research.vfa_rkhs import Gaussian, Interpolator, FPE, kernel

X=np.linspace(-3,3,129)
F=Gaussian.sections([-.7,.4],[1.2,-.3],.8)
G=Gaussian.sections([.2,1.1],[.6,1.5],.8)

@pytest.mark.parametrize('op',['add','scale','product','derivative','integral','norm','reproduce','polarization'])
def test_algebra(op):
    f=lambda x:1.2*np.exp(-.5*((x+.7)/.8)**2)-.3*np.exp(-.5*((x-.4)/.8)**2)
    g=lambda x:.6*np.exp(-.5*((x-.2)/.8)**2)+1.5*np.exp(-.5*((x-1.1)/.8)**2)
    if op=='add': actual,ref=F.add(G).evaluate(X),f(X)+g(X)
    elif op=='scale': actual,ref=F.scale(-2).evaluate(X),-2*f(X)
    elif op=='product': actual,ref=F.multiply(G).evaluate(X),f(X)*g(X)
    elif op=='derivative': actual,ref=F.derivative(X),(f(X+1e-5)-f(X-1e-5))/2e-5
    elif op=='integral': actual,ref=F.integral(),quad(f,-np.inf,np.inf)[0]
    elif op=='norm': actual,ref=F.norm()**2,1.2**2+.3**2-2*1.2*.3*np.exp(-.5*(1.1/.8)**2)
    elif op=='reproduce': actual,ref=F.inner(Gaussian.sections([.23],[1],.8)),f(.23)
    else: actual,ref=F.add(G).norm()**2+F.add(G.scale(-1)).norm()**2,2*(F.norm()**2+G.norm()**2)
    np.testing.assert_allclose(actual,ref,atol=2e-9,rtol=2e-9)

@pytest.mark.parametrize('n',[3,5,8,12])
def test_power(n):
    x=np.linspace(-2,2,n); model=Interpolator.fit(x,F.evaluate(x),.8)
    np.testing.assert_allclose(model.function.evaluate(x),F.evaluate(x),atol=1e-10)
    k=kernel(x,x,.8); cross=kernel(X,x,.8)
    ref=np.sqrt(np.maximum(0,1-np.einsum('ij,ji->i',cross,np.linalg.solve(k,cross.T))))
    np.testing.assert_allclose(model.power(X),ref,atol=1e-7)
    error=np.abs(F.evaluate(X)-model.function.evaluate(X))
    assert np.all(error<=model.error_bound(X,F.norm())+1e-8)
    assert model.function.norm()<=F.norm()+1e-8

@pytest.mark.parametrize('seed',range(4))
def test_fpe(seed):
    basis=FPE.random(2048,.8,seed); d=np.linspace(-4,4,97)
    ref=np.exp(-.5*(d/.8)**2)
    assert np.max(np.abs(basis.similarity(d)-ref))<=basis.finite_pair_bound(len(d),.01)
    c=basis.encode_sections(F)
    oracle=np.sum(F.weights[None,:]*basis.similarity((X[:,None]-F.centers).ravel()).reshape(len(X),-1),axis=1)
    np.testing.assert_allclose(basis.evaluate(c,X),oracle,atol=2e-14)
    assert np.max(np.abs(basis.evaluate(c,X)-F.evaluate(X)))<=np.sum(abs(F.weights))*basis.finite_pair_bound(len(X)*len(F.centers),.01)

@pytest.mark.parametrize('action',[lambda: F.add(F.multiply(G)).norm(),lambda: Interpolator.fit([0,0],[1,1],1),lambda: Interpolator.fit([0,1e-7],[1,1],1),lambda: FPE.random(0,1,0),lambda: FPE.random(8,1,0).encode_sections(F),lambda: Gaussian.sections([0],[np.nan],1),lambda: kernel([1j],[0],1),lambda: Gaussian.sections(range(17),np.ones(17),1).multiply(Gaussian.sections(range(17),np.ones(17),1)),lambda: Interpolator.fit([0],[1],1).error_bound([0],-1)])
def test_refusal(action):
    with pytest.raises(ValueError): action()

def test_snapshot():
    a=np.array([1.]);f=Gaussian.sections([0],a,1);a[0]=0
    assert f.evaluate([0])[0]==1
    with pytest.raises(ValueError): f.weights.setflags(write=True)
    with pytest.raises(ValueError): FPE.random(8,1,0).omega.setflags(write=True)

def test_power_worst_case():
    x=np.array([-1.,0.,1.]); z=.43; ell=.8
    model=Interpolator.fit(x,np.zeros(3),ell)
    k=kernel(x,[z],ell).ravel(); a=np.linalg.solve(kernel(x,x,ell),k)
    witness=Gaussian.sections(np.r_[z,x],np.r_[1.,-a],ell)
    p=model.power([z])[0]
    np.testing.assert_allclose(witness.norm(),p,atol=1e-14)
    np.testing.assert_allclose(witness.evaluate([z])[0]/witness.norm(),p,atol=1e-14)
