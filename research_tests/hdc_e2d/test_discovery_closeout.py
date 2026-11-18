import numpy as np
import pytest
from cognitum.research.hdc_discovery_closeout import *

@pytest.mark.parametrize('dim',[7,33,512])
def test_packed_density(dim):
    a=np.random.default_rng(9).integers(0,2,(32,dim),dtype=np.uint8);x=a[:24];q=a[24:];m=PackedDensity().fit(x);d=DensityDistance(True).fit(x);np.testing.assert_array_equal(m.score(q),d.score(q));assert m.ref.nbytes<x.nbytes

def test_calibration_freezes():
    x=np.repeat([[0,0,0,0],[1,1,1,1]],5,axis=0);m=CalibratedLouvain(k=2,capacity=4);m.fit(x);before=[v.copy() for v in m.reps];m.calibrate([[0,0,0,1],[1,1,1,0]],quantile=1);assert m.thresholds[0]==.25;assert len(m.reps)==len(before);assert m.assign([0,0,0,1]) in (0,1);assert all(np.array_equal(i,j) for i,j in zip(before,m.reps))

def test_calibration_atomic():
    m=CalibratedLouvain(k=1);m.fit([[0,0],[1,1]]);m.calibrate([[0,0]]);old=m.thresholds.copy()
    with pytest.raises(ValueError):m.calibrate([[0,0],[1,1]],[0,1])
    assert m.thresholds==old

@pytest.mark.parametrize('policy,evicts',[('refuse',False),('temporary',False),('lru',True)])
def test_recurrence_and_eviction(policy,evicts):
    a=np.zeros((8,8),np.uint8);m=BoundedWorld(a,a,capacity=1,policy=policy,idle=2,match=.1)
    for _ in range(3):p=m.observe(np.ones(8,np.uint8))
    assert p[:2]==(1,True)
    for _ in range(2):m.observe(a[0])
    r=m.observe([1,0,0,0,0,0,0,0]);assert r[0]==(2 if evicts else -1);assert m.evictions==int(evicts);assert len(m.slots)==1

def test_temporary_eviction():
    a=np.zeros((8,8),np.uint8);m=BoundedWorld(a,a,capacity=1,policy='temporary',idle=1,match=.1);assert m.observe(np.ones(8))[0]==1;assert m.observe([1,0,0,0,0,0,0,0])[0]==2

def test_count_aging_bounded():
    m=BoundedCount(np.array([1,0]),1,8)
    for _ in range(1000):m.update(np.array([1,1]),1)
    assert 1<=m.n<=8 and (m.counts<=m.n).all() and m.total==m.n and m.distance([1,1])==0

def test_packed_world_same_before_aging():
    r=np.random.default_rng(4);a=r.integers(0,2,(20,37),dtype=np.uint8);b=r.integers(0,2,(10,37),dtype=np.uint8);x=r.integers(0,2,(40,37),dtype=np.uint8);m=BoundedWorld(a,b,capacity=4,match=.1);n=OpenWorld(a,b,capacity=4,match=.1)
    for v in x:
        u,w=m.observe(v),n.observe(v);assert u[:2]==w[:2];assert u[2]==pytest.approx(w[2]);assert len(m.slots)<=4
