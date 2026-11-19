import itertools
import numpy as np
import pytest
from scipy.integrate import nquad
from scipy.spatial.distance import cdist
from cognitum.research.vfa_multivariate import Mixture, Composition, TensorInterpolator, TensorFPE, tensor_kernel

X=np.random.default_rng(38).uniform(-1.7,1.7,(51,2))
A=np.array([[-.7,.1],[.6,-.3]])
W=np.array([.8,-.35]);S=np.array([.7,1.1])
F=Mixture.sections(A,W,S)
G=Mixture.sections([[.1,.8]],[.65],[.9,.5])

def oracle(x):
    x=np.asarray(x)
    return .8*np.exp(-.5*(((x[...,0]+.7)/.7)**2+((x[...,1]-.1)/1.1)**2))-.35*np.exp(-.5*(((x[...,0]-.6)/.7)**2+((x[...,1]+.3)/1.1)**2))

def g_oracle(x):
    return .65*np.exp(-.5*(((x[...,0]-.1)/.9)**2+((x[...,1]-.8)/.5)**2))

def finite_gradient(fn,x,h=1e-5):
    return np.stack([(fn(x+h*e)-fn(x-h*e))/(2*h) for e in np.eye(x.shape[1])],axis=1)

def finite_hessian(fn,x,h=1e-4):
    e=np.eye(x.shape[1]);r=np.empty((len(x),len(e),len(e)));v=fn(x)
    for i,j in itertools.product(range(len(e)),repeat=2):
        if i==j:r[:,i,j]=(fn(x+h*e[i])-2*v+fn(x-h*e[i]))/h**2
        else:r[:,i,j]=(fn(x+h*e[i]+h*e[j])-fn(x+h*e[i]-h*e[j])-fn(x-h*e[i]+h*e[j])+fn(x-h*e[i]-h*e[j]))/(4*h*h)
    return r

@pytest.mark.parametrize('dim',[1,2,3,5,8])
def test_kernel(dim):
    r=np.random.default_rng(dim);x=r.normal(size=(8,dim));y=r.normal(size=(6,dim));s=r.uniform(.5,1.5,dim)
    np.testing.assert_allclose(tensor_kernel(x,y,s),np.exp(-cdist(x/s,y/s,'sqeuclidean')/2),atol=2e-15)
    k=tensor_kernel(x,x,s);assert np.linalg.eigvalsh(k).min()>-1e-12

@pytest.mark.parametrize('op',['eval','sum','scale','product','const_product','poly','grad','hess','laplace','whole','box','reproduce','parallelogram'])
def test_mixture(op):
    if op=='eval':a,b=F.evaluate(X),oracle(X)
    elif op=='sum':a,b=F.add(G).evaluate(X),oracle(X)+g_oracle(X)
    elif op=='scale':a,b=F.scale(-.5).evaluate(X),-.5*oracle(X)
    elif op=='product':a,b=F.multiply(G).evaluate(X),oracle(X)*g_oracle(X)
    elif op=='const_product':a,b=F.add(Mixture.const(2,2)).multiply(G.add(Mixture.const(2,-.2))).evaluate(X),(oracle(X)+2)*(g_oracle(X)-.2)
    elif op=='poly':a,b=F.polynomial([.3,-.4,.5,.1]).evaluate(X),.3-.4*oracle(X)+.5*oracle(X)**2+.1*oracle(X)**3
    elif op=='grad':a,b=F.gradient(X),finite_gradient(oracle,X)
    elif op=='hess':a,b=F.hessian(X),finite_hessian(oracle,X)
    elif op=='laplace':a,b=F.laplacian(X),np.trace(finite_hessian(oracle,X),axis1=1,axis2=2)
    elif op=='whole':a,b=F.integral(),nquad(lambda x,y:oracle([x,y]),[[-np.inf,np.inf],[-np.inf,np.inf]])[0]
    elif op=='box':a,b=F.integral([-1,-2],[2,.7]),nquad(lambda x,y:oracle([x,y]),[[-1,2],[-2,.7]])[0]
    elif op=='reproduce':a,b=F.inner(Mixture.sections([X[0]],[1],S)),oracle(X[0])
    else:
        H=Mixture.sections([[.1,0]],[.7],S);a,b=F.add(H).norm()**2+F.add(H.scale(-1)).norm()**2,2*(F.norm()**2+H.norm()**2)
    np.testing.assert_allclose(a,b,atol=4e-7,rtol=4e-7)

@pytest.mark.parametrize('degree',[1,3,5,7])
def test_sin(degree):
    f=Mixture.sections([[0,0]],[.8],[.7,1.1]);p,e=f.sin_polynomial(degree)
    assert np.max(np.abs(p.evaluate(X)-np.sin(f.evaluate(X))))<=e+1e-13
    assert e==pytest.approx(.8**(degree+2)/__import__('math').factorial(degree+2))

@pytest.mark.parametrize('op',['eval','grad','hess','laplace'])
def test_composition(op):
    outer=Mixture.sections([[.2,-.1]],[.9],[.65,.9]);c=Composition(outer,(F,G))
    fn=lambda x:.9*np.exp(-.5*(((oracle(x)-.2)/.65)**2+((g_oracle(x)+.1)/.9)**2))
    if op=='eval':a,b=c.evaluate(X),fn(X)
    elif op=='grad':a,b=c.gradient(X),finite_gradient(fn,X)
    elif op=='hess':a,b=c.hessian(X),finite_hessian(fn,X)
    else:a,b=c.laplacian(X),np.trace(finite_hessian(fn,X),axis1=1,axis2=2)
    np.testing.assert_allclose(a,b,atol=4e-7,rtol=4e-7)

@pytest.mark.parametrize('shape',[(3,4),(4,5),(3,3,3)])
def test_tensor_interpolator(shape):
    d=len(shape);axes=tuple(np.linspace(-1,1,n) for n in shape);s=np.linspace(.7,1.1,d)
    sites=np.array(list(itertools.product(*axes)));q=np.random.default_rng(d).uniform(-1.5,1.5,(41,d))
    f=Mixture.sections([np.full(d,.2),np.full(d,-.3)],[.65,-.4],s);y=f.evaluate(sites)
    m=TensorInterpolator.fit(axes,y.reshape(shape),s)
    k=np.exp(-cdist(sites/s,sites/s,'sqeuclidean')/2);cross=np.exp(-cdist(q/s,sites/s,'sqeuclidean')/2)
    np.testing.assert_allclose(m.function.weights,np.linalg.solve(k,y),atol=1e-9)
    np.testing.assert_allclose(m.function.evaluate(sites),y,atol=1e-10)
    p=np.sqrt(np.maximum(0,1-np.einsum('ij,ji->i',cross,np.linalg.solve(k,cross.T))))
    np.testing.assert_allclose(m.power(q),p,atol=1e-7)
    assert np.all(abs(m.function.evaluate(q)-f.evaluate(q))<=m.error_bound(q,f.norm())+1e-8)
    assert m.condition==pytest.approx(np.linalg.cond(k),rel=1e-7)

@pytest.mark.parametrize('seed',[0,1,2,3])
def test_fpe(seed):
    b=TensorFPE.random(2048,S,seed);c=b.encode_sections(F)
    x,y=X[0],X[1];np.testing.assert_allclose(b.encode(x)*b.encode(y),b.encode(x+y),atol=4e-15)
    ref=(np.cos((X[:,None,:]-A[None,:,:])@b.omega.T).mean(axis=-1)*W).sum(axis=1)
    np.testing.assert_allclose(b.evaluate(c,X),ref,atol=2e-14)
    assert np.max(abs(b.evaluate(c,X)-oracle(X)))<=sum(abs(W))*b.finite_pair_bound(len(X)*len(W),.01)
    fn=lambda x:b.evaluate(c,x)
    np.testing.assert_allclose(b.gradient(c,X),finite_gradient(fn,X),atol=1e-8)
    np.testing.assert_allclose(b.hessian(c,X),finite_hessian(fn,X),atol=3e-7)

@pytest.mark.parametrize('fn',[lambda: F.multiply(Mixture.const(1,1)),lambda: F.inner(G),lambda:F.add(Mixture.const(2,1)).integral(),lambda:F.integral([1,0],[0,1]),lambda: F.evaluate([[np.nan,0]]),lambda: F.polynomial([1]*10),lambda: F.sin_polynomial(2),lambda: Mixture.sections(np.zeros((17,2)),np.ones(17),S).multiply(Mixture.sections(np.zeros((17,2)),np.ones(17),S)),lambda: TensorInterpolator.fit(([0,0],[0,1]),np.ones((2,2)),S),lambda: TensorInterpolator.fit(([0,1e-7],[0,1]),np.ones((2,2)),S),lambda: TensorInterpolator.fit((range(17),range(17)),np.ones((17,17)),S),lambda:Composition(G,(F,)),lambda:TensorFPE.random(0,S,0),lambda:TensorFPE.random(8,S,0).encode_sections(G)])
def test_refusal(fn):
    with pytest.raises(ValueError):fn()


def test_snapshot():
    x=np.array([[0.,0.]]);m=Mixture.sections(x,[1],S);x[:]=1
    assert m.evaluate([[0,0]])[0]==1
    for a in (m.centers,m.weights,m.widths,TensorFPE.random(8,S,0).omega):
        with pytest.raises(ValueError):a.setflags(write=True)
