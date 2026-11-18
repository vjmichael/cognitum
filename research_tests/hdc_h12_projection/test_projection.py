import numpy as np
import pytest
from tools.h12_projection.projection import Plan,Sparse,Hadamard,unpack,words
from tools.h12_projection.symbolic import expected_signal,independent_threshold,trial
@pytest.mark.parametrize('f,d',[(1,1),(7,65),(64,256),(65,257),(128,1024),(1280,1024)])
def test_projection_exact(f,d):
    r=np.random.default_rng(19);x=r.integers(-5,6,(5,f)).astype(np.float32);p=Plan(f,d);w=p.dense();z=p.reference(x,w)
    assert np.array_equal(p.encode(x,p.packed()),z);assert np.array_equal(p.encode(x),z)
    assert np.array_equal(unpack(z,d),(x.astype(np.float64)@w.astype(np.float64))<0)
    assert p.packed().nbytes==((f+7)//8)*d
@pytest.mark.parametrize('f,d',[(7,65),(64,256),(1280,513)])
def test_float_reference(f,d):
    x=np.random.default_rng(17).uniform(-5,5,(6,f)).astype(np.float32);x[0]=0;p=Plan(f,d);w=p.dense();z=p.reference(x,w)
    assert np.array_equal(p.encode(x,p.packed()),z);assert np.array_equal(p.encode(x),z)
    assert np.array_equal(unpack(z,d),x.astype(np.float64)@w.astype(np.float64)<0)
@pytest.mark.parametrize('f,d',[(3,65),(64,256),(65,257)])
def test_structured(f,d):
    x=np.ones((3,f),np.float32)
    for p in (Sparse(f,d,min(f,16),4),Hadamard(f,d,4)):
        a=p.encode(x);assert a.shape==(3,(d+63)//64);assert np.array_equal(a,p.encode(x));assert np.array_equal(a[0],a[1]);assert np.array_equal(words(unpack(a,d)),a)
def test_invalid():
    p=Plan(4,65)
    with pytest.raises(ValueError):p.encode(np.full((1,4),np.nan,dtype=np.float32))
    with pytest.raises(ValueError):p.encode(np.zeros((1,4),np.float64))
    with pytest.raises(ValueError):Plan(4,65,block=65)
    with pytest.raises(ValueError):p.encode(np.zeros((1,4),np.float32),np.zeros((1,64),np.uint8))
def test_signal():
    assert expected_signal(1)==1;assert expected_signal(3)==.5;assert expected_signal(5)==.375
    assert independent_threshold(4096,100,.01)<independent_threshold(256,100,.01)
    r=trial(1024,1,16,10,1);assert r['exact_top1']==1 and r['mean_signal']==1

def test_near_cancellation():
    from tools.h12_projection.projection import stable_bits
    import math
    x=np.array([[5.,-5.,-1e-12,1e-20],[5.,-5.,1e-12,-1e-20],[0,0,0,0]],np.float32)
    w=np.ones((4,65),np.int8)
    bits=stable_bits(x,w,x@w.astype(np.float32))
    assert bits[0].all() and not bits[1:].any()
    assert all(bits[i,0]==(math.fsum(map(float,v))<0) for i,v in enumerate(x))

def test_majority_formula_exact_small_k():
    from itertools import product
    for k in [1,3,5,7,9]:
        actual=np.mean([int(sum(t)>0)*2-1 for t in ((1,*s) for s in product((-1,1),repeat=k-1))])
        assert actual==expected_signal(k)

def test_exact_binding_and_commutativity():
    a,b,r=np.random.default_rng(5).choice([-1,1],(3,256))
    assert np.array_equal((a*r)*r,a)
    assert np.array_equal(a*b,b*a) # ordinary MAP alone cannot distinguish order
    assert not np.array_equal(a*np.roll(b,1),b*np.roll(a,1))
