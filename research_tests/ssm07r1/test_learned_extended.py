import numpy as np
import pytest
from scipy.linalg import expm
from cognitum.research import ssm_learned as s, ssm_learned_extended as e


@pytest.mark.parametrize('T',[1,3,17,128])
@pytest.mark.parametrize('complex_', [False,True])
def test_jvp(T,complex_):
    rng=np.random.default_rng(T);F=rng.uniform(.2,.8,(T,3));G=rng.normal(size=F.shape);h=rng.normal(size=3);dF,dG,dh=rng.normal(size=F.shape),rng.normal(size=F.shape),rng.normal(size=3)
    if complex_:F=F+.1j;dG=dG+.2j
    z=e.scan_jvp(F,G,h,dF,dG,dh);X=[];D=[];x=h.copy();d=dh.copy()
    for a,b,p,q in zip(F,G,dF,dG):d=p*x+a*d+q;x=a*x+b;X.append(x);D.append(d)
    np.testing.assert_allclose(z['states'],X,atol=1e-12);np.testing.assert_allclose(z['tangent'],D,atol=1e-12);eps=1e-6;np.testing.assert_allclose(z['tangent'],(s.affine_scan(F+eps*dF,G+eps*dG,h+eps*dh)-s.affine_scan(F-eps*dF,G-eps*dG,h-eps*dh))/(2*eps),atol=2e-8)


def test_mamba1():
    u=np.linspace(-1,1,31);g=np.linspace(.3,1,31);b=np.array([[1,.2],[.2,.3]]);c=np.array([[.7,.1],[-.2,.1]]);a=np.array([-.4,-1.]);dt=[-1,.2];k=[.7,.2];h=np.array([.3,.5]);args=(k,a,dt,b,c,h,.4,g);z=e.mamba1(u,*args);q=e.mamba1(u,*args,scan=False);np.testing.assert_allclose(z['outputs'],q['outputs'],atol=1e-12)
    v=np.convolve(u,k)[:len(u)];v=v/(1+np.exp(-v));x=h.copy();Y=[]
    for t,w in enumerate(v):
        d=np.log1p(np.exp(dt[0]+dt[1]*w));x=np.exp(-np.exp(a)*d)*x+d*(b[:,0]+w*b[:,1])*w;Y.append(((c[:,0]+w*c[:,1])@x+.4*w)*g[t]/(1+np.exp(-g[t])))
    np.testing.assert_allclose(z['outputs'],Y,atol=1e-12);u[20:]+=2;np.testing.assert_array_equal(e.mamba1(u,*args)['outputs'][:20],z['outputs'][:20])


@pytest.mark.parametrize('seed',[2,17,81])
def test_selective_train(seed):
    rng=np.random.default_rng(seed);u=rng.uniform(-1,1,160);v=rng.uniform(-1,1,80);f=lambda x:e.mamba1(x,[1],[.25],[-1,.4],[[1,0]],[[.8,0]],[0])['outputs'];z=e.selective_fit(u,f(u),v,f(v),[0,.1,.5]);np.testing.assert_allclose(z['parameters'],[.25,.4,.8],atol=1e-6);assert z['heldout_rmse']<1e-8 and z['gradient_error']<1e-7


@pytest.mark.parametrize('seed',[3,11])
def test_structured_train(seed):
    rng=np.random.default_rng(seed);u=rng.normal(size=160);v=rng.normal(size=80);r=s.s4_discretize(2,.25);f=lambda x:s.recurrence(r['F'],r['G'],[[.8,-.3]],x[:,None],[0,0])['outputs'][:,0];z=e.structured_fit(u,f(u),v,f(v),2,.18);assert z['step']==pytest.approx(.25,abs=1e-7);np.testing.assert_allclose(z['readout'],[.8,-.3],atol=1e-7);assert z['heldout_rmse']<1e-8


@pytest.mark.parametrize('block',[1,4,7,32,64])
def test_ssd(block):
    rng=np.random.default_rng(8);a=rng.uniform(.1,.99,31);a[8]=0;b,c=rng.normal(size=(2,31,3));u=rng.normal(size=(31,2));h=rng.normal(size=(3,2));z=e.ssd(a,b,c,u,h,block);np.testing.assert_allclose(z['dense'],z['serial'],atol=1e-12);np.testing.assert_allclose(z['chunked'],z['serial'],atol=1e-12);np.testing.assert_allclose(z['final_state'],z['serial_final'],atol=1e-12);a2=a.copy();a2[21:]=0;np.testing.assert_array_equal(e.ssd(a2,b,c,u,h,block)['dense'][:21],z['dense'][:21])


def test_rotary():
    rng=np.random.default_rng(7);T=35;rates=np.array([-.3+2j,-.3-2j]);dt=rng.uniform(.01,.3,T);mix=rng.uniform(0,1,T);u=rng.normal(size=(T,2));b=rng.normal(size=(T,1,2))+1j*rng.normal(size=(T,1,2));b=np.concatenate((b,b.conj()),1);c=np.tile([[[1,1],[1j,-1j]]],(T,1,1));h=np.array([.2+.1j,.2-.1j]);p=np.array([.5-.4j,.5+.4j]);z=e.rotary_mimo(rates,dt,mix,b,c,u,h,p);state=np.array([h[0].real,h[0].imag]);prev=np.array([p[0].real,p[0].imag]);Y=[]
    for j in range(T):
        F=expm(dt[j]*np.array([[-.3,-2],[2,-.3]]));v=(b[j,0]@u[j]);v=np.array([v.real,v.imag]);state=F@state+dt[j]*(mix[j]*v+(1-mix[j])*F@prev);prev=v;Y.append([2*state[0],-2*state[1]])
    np.testing.assert_allclose(z['outputs'],Y,atol=1e-12);q=e.rotary_mimo(rates,dt[:12],mix[:12],b[:12],c[:12],u[:12],h,p);w=e.rotary_mimo(rates,dt[12:],mix[12:],b[12:],c[12:],u[12:],q['final_state'],q['previous_injection']);np.testing.assert_allclose(np.vstack((q['outputs'],w['outputs'])),z['outputs'],atol=1e-12)


def test_trapezoid_refinement():
    errors=[]
    for n in [16,32,64]:
        t=np.arange(1,n+1)/n;z=e.rotary_mimo([-1],[1/n]*n,[.5]*n,np.ones((n,1,1)),np.ones((n,1,1)),t[:,None],[0],[0]);errors.append(abs(z['outputs'][-1,0]-np.exp(-1)))
    assert errors[2]<errors[1]/3.9 and errors[1]<errors[0]/3.9


@pytest.mark.parametrize('seed',[1,21,71])
def test_memory(seed):
    z=e.memory_trial(seed);m=z['metrics'];assert m['rotation']['accuracy']==1 and m['rotation']['rmse']<1e-12;assert m['positive_decay']['accuracy']<.7 and m['last_token']['accuracy']<.7 and z['hand_designed_features']


@pytest.mark.parametrize('fn',[lambda:e.scan_jvp([[1]],[[1]],[0],[[1]],[[1]],[0,0]),lambda:e.ssd([1.1],[[1]],[[1]],[[1]],[[0]]),lambda:e.rotary_mimo([1],[1],[.5],[[[1]]],[[[1]]],[[1]],[0],[0]),lambda:e.memory_trial(-1),lambda:e.mamba1([1],[1],[0],[100,0],[[1,0]],[[1,0]],[0])])
def test_refuse(fn):
    with pytest.raises(ValueError):fn()
