import numpy as np
import pytest
from cognitum.research.hdc_stream_discovery import *

def test_hamming_oracle():
    a=np.random.default_rng(1).integers(0,2,(10,33));b=a[:4];np.testing.assert_allclose(hamming(a,b),np.mean(a[:,None,:]!=b[None,:,:],2))

@pytest.mark.parametrize('cls',[ThermometerProjection,IDLevel])
def test_encoding_train_only(cls):
    a=np.random.default_rng(2).normal(size=(20,4));p=cls(4).fit(a);b=p.encode(a);assert np.array_equal(b,p.encode(np.vstack([a,a*100]))[:len(a)])

def test_thermometer_exact():
    a=np.array([[0.],[.25],[.75],[1.]])
    p=ThermometerProjection(1,1,4);p.R[:]=1;p.fit(a);h=p.encode(a);assert np.array_equal(h.sum(1),[0,1,3,4]);assert hamming(h,h)[1,2]==.5

def test_level_flips():
    p=IDLevel(3,64,8);assert np.all((p.codes[1:]!=p.codes[:-1]).sum(1)==8)

def test_louvain_frozen_bucket_capacity():
    a=np.repeat([[0,0,0,0],[1,1,1,1]],4,axis=0);m=IncrementalLouvain(k=2,capacity=3,threshold=.25);labels=m.fit(a,np.repeat([0,1],4));assert len(set(labels))==2
    old=[x.copy() for x in m.reps];assert m.assign([0,0,0,1],0)==labels[0];assert all(np.array_equal(a,b) for a,b in zip(old,m.reps));assert m.assign([0,0,0,0],2)==2;assert m.assign([0,0,0,0],3)==-1

def test_louvain_singleton():
    m=IncrementalLouvain();assert list(m.fit([[1,0]]))==[0]

def test_count_memory_exact():
    a=np.random.default_rng(3).integers(0,2,(20,31));m=CountMemory(a[0],1.)
    for i,x in enumerate(a[1:]):m.update(x,2.)
    q=a[0];assert m.distance(q)==pytest.approx((a!=q).mean());assert m.radius()==pytest.approx((a[:,None]!=a[None,:]).mean());assert m.n==20 and m.total==39

def test_count_reject_atomic():
    m=CountMemory([0,1],1);c=m.counts.copy()
    with pytest.raises(ValueError):m.update([1,0,1],1)
    assert m.n==1 and np.array_equal(m.counts,c)

def test_open_world_recurrence_and_capacity():
    a=np.zeros((10,8),int);m=OpenWorld(a,a,capacity=1,match=.1)
    assert m.observe(np.zeros(8))[:2]==(0,False)
    for flag in (False,False,True):assert m.observe(np.ones(8))[:2]==(1,flag)
    assert m.observe([1,0,0,0,0,0,0,0])[:2]==(-1,False)
    assert m.mem[0].n==3

@pytest.mark.parametrize('binary',[False,True])
def test_density_inductive_oracle(binary):
    a=np.random.default_rng(4).integers(0,2,(30,13));q=a[:3];m=DensityDistance(binary).fit(a);d=m.distances(q,a);rho,delta=m.components(q)
    for i,row in enumerate(d):
        r=sum(row<m.cutoff);c=[v for v,n in zip(row,m.rho) if n>r];assert rho[i]==r;assert delta[i]==pytest.approx(min(c) if c else max(row));assert m.score(q)[i]==pytest.approx(delta[i]/max(r,1))

def test_density_batch_invariance():
    a=np.random.default_rng(5).normal(size=(32,5));m=DensityDistance().fit(a[:20]);np.testing.assert_allclose(m.score(a[20:21]),m.score(a[20:])[:1])

def test_invalid_bits():
    with pytest.raises(ValueError):hamming([[2]],[[1]])

@pytest.mark.parametrize('dimension',[7,8,33,512])
def test_packed_hamming_exact(dimension):
    a=np.random.default_rng(6).integers(0,2,(12,dimension),dtype=np.uint8);b=a[2:];p=lambda x:np.packbits(x,axis=1,bitorder='little');np.testing.assert_array_equal(packed_hamming(p(a),p(b),dimension),hamming(a,b))

def test_padding_guard():
    with pytest.raises(ValueError):packed_hamming(np.array([[128]],np.uint8),np.array([[0]],np.uint8),7)

def test_wrong_count_width():
    with pytest.raises(ValueError):CountMemory([1,0],1).distance([1])
