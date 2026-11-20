import itertools
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import logsumexp
from cognitum.research import ssm_scientific_extended as e


@pytest.mark.parametrize('a',[0.,.4,.8])
def test_variational_linear(a):
    y=np.array([.3,1.,-.5,.8]);q=.4;r=.7;n=len(y);C=np.zeros((n,n));C[0,0]=1
    for i in range(1,n):C[i,:i]=a*C[i-1,:i];C[:i,i]=C[i,:i];C[i,i]=a*a*C[i-1,i-1]+q
    J=np.linalg.inv(C)+np.eye(n)/r;M=np.linalg.solve(J,y/r);V=np.linalg.inv(J);z=e.variational(y,a,q,r,[1,0]);np.testing.assert_allclose(z['means'],M,atol=1e-6);np.testing.assert_allclose(z['variances'],1/J.diagonal(),atol=1e-6)
    evidence=-.5*(n*np.log(2*np.pi)+np.linalg.slogdet(C+r*np.eye(n))[1]+y@np.linalg.solve(C+r*np.eye(n),y));kl=.5*(np.linalg.slogdet(V)[1]-np.log(1/J.diagonal()).sum());assert z['elbo']==pytest.approx(evidence-kl,abs=1e-9);assert z['directional_gradient_error']<1e-6


def test_variational_nonlinear():
    y=[.4,-.2];z=e.variational(y,0,.8,.5,[.2,.7]);ll=0
    for v,p in zip(y,[1,.8]):ll+=np.log(quad(lambda x:np.exp(-x*x/(2*p)-(v-.2*x-.7*np.tanh(x))**2/1)/(2*np.pi*np.sqrt(p*.5)),-12,12,epsabs=1e-12)[0])
    assert z['initial_elbo']<z['elbo']<=ll+1e-8 and ll-z['elbo']<.1 and z['uses_future']


@pytest.mark.parametrize('seed',[4,17,82])
def test_particle_gradient(seed):
    rng=np.random.default_rng(seed);x=rng.normal(size=2048);N=rng.normal(size=(4,len(x)));y=[.2,.1,-.3,.5];b=.2;args=(y,x,N,.7);z=e.particle_gradient(*args,b,.4,.8);p=e.particle_gradient(*args,b+1e-6,.4,.8);m=e.particle_gradient(*args,b-1e-6,.4,.8);assert z['gradient']==pytest.approx((p['log_likelihood']-m['log_likelihood'])/2e-6,abs=1e-7);assert not z['resampled']


def test_particle_gaussian():
    rng=np.random.default_rng(9);x=rng.normal(size=8192);z=e.particle_gradient([.4],x,rng.normal(size=(1,len(x))),.7,0,.4,.8);v=.7**2+.4**2;assert z['means'][0]==pytest.approx(v/(v+.8)*.4,abs=.025);assert z['log_likelihood']==pytest.approx(-.5*(np.log(2*np.pi*(v+.8))+.4**2/(v+.8)),abs=.025)


def test_particle_degenerate():
    with pytest.raises(ValueError,match='degeneracy'):e.particle_gradient([100],[-1,0,1],[[0]*3],1,0,0,.0001,.9)


def fields(rng,n,count,k):
    t=2*np.pi*np.arange(n)/n;return rng.normal(size=(count,1))+sum(rng.normal(size=(count,1))*np.cos(j*t)+rng.normal(size=(count,1))*np.sin(j*t) for j in range(1,k+1))


def reference(x,u,w):
    n=x.shape[-1];k=len(w)-1;z=np.fft.rfft(x,axis=-1);v=np.fft.rfft(u,axis=-1);t=np.fft.rfft(np.tanh(u),axis=-1);out=np.zeros_like(z);out[...,:k+1]=w[:,0]*z[...,:k+1]+w[:,1]*v[...,:k+1]+w[:,2]*t[...,:k+1];return np.fft.irfft(out,n=n,axis=-1)


@pytest.mark.parametrize('n',[32,64,128])
def test_operator(n):
    rng=np.random.default_rng(7);k=3;j=np.arange(k+1);w=np.column_stack((.95*np.exp(-.15*j*j),.3/(j+1),.2/(j+1)));X=fields(rng,32,80,k);U=fields(rng,32,80,k);Y=reference(X,U,w);z=e.operator_fit(X,U,Y,k);np.testing.assert_allclose(z['weights'],w,atol=1e-12);x=fields(rng,n,1,k)[0];u=fields(rng,n,12,k);p=e.operator_roll(z['weights'],x,u);R=[x];
    for f in u:R.append(reference(R[-1],f,w))
    np.testing.assert_allclose(p['states'],R,atol=1e-11)


def test_heat_operator():
    rng=np.random.default_rng(11);k=3;j=np.arange(k+1);a=.1*(2*np.pi*j)**2;dt=.1;dec=np.exp(-a*dt);b=np.r_[dt,-np.expm1(-a[1:]*dt)/a[1:]];w=np.column_stack((dec,b,np.zeros(k+1)));X=fields(rng,32,60,k);U=fields(rng,32,60,k);z=e.operator_fit(X,U,reference(X,U,w),k);x=fields(rng,64,1,k)[0];u=fields(rng,64,1,k);p=e.operator_roll(z['weights'],x,u);np.testing.assert_allclose(p['states'][1],reference(x,u[0],w),atol=1e-12)


def test_operator_refuse():
    with pytest.raises(ValueError,match='outside band'):e.operator_roll([[.5,1,0],[.5,1,0]],np.cos(4*np.pi*np.arange(16)/16),np.zeros((2,16)))
    with pytest.raises(ValueError,match='rank'):e.operator_fit(np.ones((8,16)),np.ones((8,16)),np.ones((8,16)),2)


def simulate(seed,n):
    rng=np.random.default_rng(seed);L=[0];P=np.array([[.98,.02],[.03,.97]])
    for _ in range(n-1):L.append(rng.choice(2,p=P[L[-1]]))
    L=np.array(L);return np.where(L==0,-2,2)+rng.normal(0,.6,n),L


@pytest.mark.parametrize('seed',[4,23,91])
def test_regime(seed):
    y,L=simulate(seed,1800);z=e.regime_fit(y[:1200],L[:1200],2);args=(z['transition'],z['means'],z['variances'],[.5,.5]);base=(z['baseline_mean'],z['baseline_variance']);p=e.regime_forecast(*args,y[1200:],*base);assert p['negative_log_score']<p['baseline_log_score']-.5;assert .84<p['central_90_coverage']<.96
    v=y[1200:].copy();v[20:]+=40;q=e.regime_forecast(*args,v,*base);np.testing.assert_array_equal(p['predictions'][:21],q['predictions'][:21]);assert q['ood'][20:].all()


def test_regime_reference():
    P=np.array([[.7,.3],[.2,.8]]);m=np.array([-1.,1.]);v=np.array([1.,.4]);prior=[.4,.6];y=[.1,.7,-.2];z=e.regime_forecast(P,m,v,prior,y,0,2);weights=[]
    for path in itertools.product(range(2),repeat=4):
        p=prior[path[0]]
        for j,o in enumerate(y):k=path[j+1];p*=P[path[j],k]*np.exp(-.5*(o-m[k])**2/v[k])/np.sqrt(2*np.pi*v[k])
        weights.append(p)
    assert z['negative_log_score']==pytest.approx(-np.log(sum(weights))/3)


@pytest.mark.parametrize('seed',[1,7,32])
def test_automaton(seed):
    rng=np.random.default_rng(seed);A=np.array([[1,0,2],[0,2,1]]);t=rng.integers(0,2,511);z=e.automaton(A,t,0,[1]);p=np.eye(3,dtype=int)
    for j in t:p=np.eye(3,dtype=int)[A[j]].T@p
    assert z['states'][-1]==np.argmax(p[:,0]);np.testing.assert_array_equal(z['transition'],np.argmax(p,axis=0));assert z['accepted']==(z['states'][-1]==1)


def test_noncommuting():
    A=[[1,0,2],[0,2,1]];assert e.automaton(A,[0,1],0,[2])['accepted'];assert not e.automaton(A,[1,0],0,[2])['accepted']


@pytest.mark.parametrize('seed',[1,21,71])
def test_recall(seed):
    z=e.recall_trial(seed);m=z['metrics'];assert m['exact_key']['accuracy']==1 and m['exact_key']['rmse']<1e-12;assert m['decay']['accuracy']<.75 and m['last_token']['accuracy']<.75 and z['hand_designed_features']


@pytest.mark.parametrize('fn',[lambda:e.variational([1],.4,1,1,[1,0]),lambda:e.particle_gradient([1],[1,2],[[0,0]],2,0,0,1),lambda:e.regime_fit([1,2],[0,2],2),lambda:e.automaton([[1,2]],[0],0,[1]),lambda:e.recall_trial(-1)])
def test_refuse(fn):
    with pytest.raises(ValueError):fn()


def test_variational_training():
    rng=np.random.default_rng(721);X=[]
    for _ in range(6):
        x=[rng.normal()]
        for _ in range(15):x.append(.6*x[-1]+rng.normal(scale=np.sqrt(.4)))
        X.append(x)
    X=np.array(X);Y=.7*X+.2*np.tanh(X)+.4*np.tanh(2*np.tanh(X)+.25)+rng.normal(scale=.5,size=X.shape);z=e.variational_train(Y,.6,.4,.25,[.1,.1,.1],4);assert np.min(np.diff(z['elbo_history']))>=-1e-6 and z['elbo_history'][-1]>z['elbo_history'][0]+1;assert z['fixed_hidden_layers'] and not z['global_optimum']
    p=e.variational(Y[0],.6,.4,.25,z['decoder']);assert np.isfinite(p['elbo']) and p['directional_gradient_error']<1e-6
