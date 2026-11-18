import numpy as np
import pytest
from cognitum.research.hdc_frontier_closeout import *

@pytest.mark.parametrize('n',[1,3,4,17,65])
def test_pack(n):
    x=np.arange(n,dtype=np.uint8)%64;p=pack6(x);assert p.nbytes==(n*6+7)//8;np.testing.assert_array_equal(unpack6(p,x.shape),x)

def test_pack_refuses_padding():
    with pytest.raises(ValueError):unpack6(np.array([255],np.uint8),(1,))

def test_packed_matches_dense_updates():
    a=PackedPhaseAdam(4,8,3,13,seed=4,lr=.75);b=PackedPhaseAdam(4,8,3,13,seed=4,lr=.75,packed=False);x=np.array([[0,1,2,3],[7,6,5,4],[0,0,0,0]]);y=np.array([0,1,2]);
    for _ in range(5):
        assert a.update(x,y)==b.update(x,y)
        for u,v in zip(a.codes(),b.codes()):np.testing.assert_array_equal(u,v)
        np.testing.assert_array_equal(a.scores(x),b.scores(x))
    assert a.persistent_array_bytes()<b.persistent_array_bytes()
    assert a.m is None and a.v is None

def test_rare_unseen_value():
    a=PackedPhaseAdam(2,8,2,9,seed=1);before=a.codes()[1].copy();a.update(np.array([[0,1],[1,0]]),np.array([0,1]));np.testing.assert_array_equal(before[2:],a.codes()[1][2:])

def test_union():
    x=np.array([[1,1,-1],[1,-1,-1],[-1,1,1],[-1,-1,1]]);y=np.array([0,0,1,1]);w=np.array([[1,1,-1],[-1,1,1]]);m,ix=class_union(x,y,w,.8);np.testing.assert_array_equal(ix,[0,2]);np.testing.assert_array_equal(ix,np.flatnonzero(m.any(0)))

@pytest.mark.parametrize('m',[1,5,12])
def test_packed_thermometer(m):
    from cognitum.research.hdc_frontier_learning import expanded_dot
    rng=np.random.default_rng(5);x=rng.choice([-1,1],(7,13));k=rng.integers(0,m+1,(3,13));q=rng.choice([-1,1],k.shape);s,n=packed_expanded_dot(x,k,q,m);np.testing.assert_array_equal(s,expanded_dot(x,k,q,m));assert n==3*((13*m+7)//8)

def test_rgb_shared_and_independent():
    rng=np.random.default_rng(0);x=rng.integers(0,8,(4,3,5));p=rng.choice([-1,1],(5,7));v=rng.choice([-1,1],(8,7));np.testing.assert_array_equal(channel_bind(x,p,v),channel_bind(x,np.broadcast_to(p,(3,5,7)),v))
