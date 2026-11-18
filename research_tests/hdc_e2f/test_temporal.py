import itertools
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from cognitum.research.hdc_temporal import CategoricalHMM,BinaryForward,LDN,LIF,BinaryNgram

def model():return CategoricalHMM([.7,.3],[[.8,.2],[.25,.75]],[[.9,.1],[.2,.8]])

def test_exact_forward_oracle():
    m=model();x=[0,1,0,1];p=0.
    for h in itertools.product(range(2),repeat=len(x)):
        v=m.initial[h[0]]*m.emission[h[0],x[0]]
        for i in range(1,len(x)):v*=m.transition[h[i-1],h[i]]*m.emission[h[i],x[i]]
        p+=v
    assert np.exp(m.score(x))==pytest.approx(p,abs=1e-14)

def test_long_loglik_stability():
    assert np.isfinite(model().score([0,1]*1000))

def test_zero_likelihood():
    m=CategoricalHMM([1],[[1]],[[1,0]])
    assert m.score([1])==-np.inf
    b=BinaryForward(m,31);assert b.consume([1])==-np.inf and b.depleted and b.consume([0])==-np.inf
    b.reset();assert b.consume([0]*100)==0

def test_packed_deterministic_and_tail():
    m=CategoricalHMM([1,0],[[0,1],[1,0]],[[1,0],[0,1]])
    b=BinaryForward(m,17);assert b.consume([0,1]*30)==0 and b.state_bytes==6
    bits=np.unpackbits(b.state,axis=1,bitorder='little');assert (bits[:,:17].sum(0)==1).all() and not bits[:,17:].any()

def test_population_convergence():
    m=model();x=[0,1,1,0,1,0,0,1];scores=[BinaryForward(m,8192,s).consume(x) for s in range(5)]
    assert abs(np.mean(scores)-m.score(x))<.12

def test_population_chunk_replay():
    m=model();x=[0,1,1,0,1,0,0,1]
    a=BinaryForward(m,257,9);b=BinaryForward(m,257,9);v=a.consume(x);b.consume(x[:3]);assert b.consume(x[3:])==v and np.array_equal(a.state,b.state)

def test_fit_normalized():
    x=[[0,1,0,1],[0,0,1,0],[1,0,1,1]]
    m=CategoricalHMM.fit(x,2,2,seed=5,iterations=5)
    assert np.allclose(m.transition.sum(1),1) and np.allclose(m.emission.sum(1),1) and np.isfinite(m.score(x[0]))

def test_reject_invalid():
    with pytest.raises(ValueError):CategoricalHMM([1],[[.5]],[[1]])
    for x in ([],[-1],[2],[.5]):
        with pytest.raises(ValueError):model().score(x)
    with pytest.raises(ValueError):BinaryForward(model(),7)

def test_ldn_first_order():
    a=LDN(1,2,.1);assert a.step([3])[0,0]==pytest.approx(3*(1-np.exp(-.05)))

def test_ldn_ode_oracle():
    a=LDN(5,.7,.03,2);x=[.2,-.8];initial=np.arange(10).reshape(5,2)/10;a.state=initial.copy()
    r=solve_ivp(lambda t,z:(a.A@z.reshape(5,2)+a.B[:,None]*x).ravel(),[0,.03],initial.ravel(),rtol=1e-11,atol=1e-12)
    assert np.allclose(a.step(x).ravel(),r.y[:,-1],atol=1e-10)

def test_ldn_chunk_and_reset():
    x=np.random.default_rng(5).normal(size=(40,2));a=LDN(7,1,.02,2);b=LDN(7,1,.02,2)
    assert np.array_equal(a.consume(x),np.concatenate((b.consume(x[:19]),b.consume(x[19:]))));b.reset();assert np.array_equal(a.consume(x[:0]),np.empty((0,7,2)));a.reset();assert np.array_equal(a.consume(x),b.consume(x))

def test_ldn_constant_and_stability():
    a=LDN(8,1,.02);assert np.max(np.abs(np.linalg.eigvals(a.Ad)))<1
    z=a.consume(np.ones((1000,1)))[-1,:,0];assert np.allclose(z,[1]+[0]*7,atol=1e-9)
    assert a.numeric_bytes==(2*8*8+3*8)*8

def test_lif_oracle():
    a=LIF(1,alpha=.5,beta=.5,threshold=1.);assert not a.step([.5])[0];assert a.step([.5])[0];assert a.voltage[0]==0 and a.current[0]==.75
    a.reset();assert a.current[0]==0
    with pytest.raises(ValueError):a.step([-1])

def test_ngram_order_and_stream():
    c=np.random.default_rng(5).integers(0,2,(3,129),dtype=np.uint8);a=BinaryNgram(c,2);b=BinaryNgram(c,2);x=[0,1,2,1]
    ref=[]
    for i in range(1,len(x)):ref.append(np.logical_xor(np.roll(c[x[i-1]],1),c[x[i]]).astype(int)*2-1)
    assert np.array_equal(a.consume(x),np.mean(ref,axis=0));b.consume(x[:2]);assert np.array_equal(a.consume(x[-1:]),b.consume(x[2:]+x[-1:]))
    a.reset();assert not np.array_equal(a.consume([0,1]),BinaryNgram(c,2).consume([1,0]))

def test_ngram_bounded():
    a=BinaryNgram(np.eye(8,dtype=int),3);n=a.numeric_bytes;a.consume([0,1,2]*1000);assert a.numeric_bytes==n and a.windows==2998 and len(a.ring)==3

def test_exact_stream_score_matches_training_trace():
    m=model();x=[0,0,1,1]*100
    assert m.score(x)==pytest.approx(m.forward(x)[0],abs=1e-10)

def test_ldn_summary_independent_and_bounded():
    from cognitum.research.hdc_temporal import LDNSummary
    x=np.random.default_rng(42).normal(size=(73,2));a=LDNSummary(4,.3,1/64,2);n=a.numeric_bytes
    for u in x:a.step(u)
    z=LDN(4,.3,1/64,2).consume(x);ref=np.r_[z[-1].ravel(),z.mean(0).ravel(),z.std(0).ravel()]
    assert a.numeric_bytes==n and np.allclose(a.feature(),ref,atol=1e-12)
    a.reset();assert a.n==0 and a.numeric_bytes==n
    with pytest.raises(ValueError):a.feature()

def test_packed_majority_exact_tail():
    from cognitum.research.hdc_temporal import PackedPrototype
    rng=np.random.default_rng(99);p=rng.normal(size=(4,131));q=rng.normal(size=131);m=PackedPrototype(p)
    assert m.numeric_bytes==4*17 and np.array_equal(m.distances(q),((p>=0)!=(q>=0)).sum(1))
