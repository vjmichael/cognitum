import numpy as np
import pytest
import torch
from torchhd import memory
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_associative import (Cleanup, Candidate, SparseDistributed, classical_field, dense_associative_field, continuous_hopfield, PhaseWorkingMemory)


def bip(seed,n,d):return np.random.default_rng(seed).choice(np.array([-1,1],np.int8),(n,d))

@pytest.mark.parametrize('seed',[1,7,13])
def test_sdm_matches_native(seed):
    a=bip(seed,64,32);k=bip(seed+1,12,32);v=bip(seed+2,12,24);s=SparseDistributed(a,24,13)
    n=memory.SparseDistributed(64,32,24,p=.2,device='cpu',dtype=torch.float32)
    n.threshold=32-2*13
    with torch.no_grad():n.keys.copy_(torch.tensor(a,dtype=torch.float32));n.values.zero_()
    for key,val in zip(k,v):s.write(key,val)
    n.write(torch.tensor(k,dtype=torch.float32),torch.tensor(v,dtype=torch.float32))
    assert np.array_equal(s._counters,n.values.detach().numpy())
    for key in k:assert np.array_equal(s.raw(key)[0],n.read(torch.tensor(key,dtype=torch.float32)).numpy())
    for key,val in zip(k,v):s.write(key,val,subtract=True)
    assert not s._counters.any() and not s._counts.any()


def test_multiple_locations_and_ties():
    a=np.array([[1,1,1],[1,1,-1],[-1,-1,-1]],np.int8);s=SparseDistributed(a,2,1);q=a[0];v=np.array([1,-1],np.int8)
    assert s.write(q,v)==2;assert np.array_equal(s.raw(q)[0],[2,-2]);assert s.read(a[2]) is None
    s.write(q,-v);assert s.read(q) is None


def test_overflow_atomic():
    a=bip(3,3,8);s=SparseDistributed(a,4,8,limit=1);v=bip(4,1,4)[0];s.write(a[0],v);old=s._counters.copy()
    with pytest.raises(OverflowError):s.write(a[0],v)
    assert np.array_equal(old,s._counters)
    s.write(a[0],v,subtract=True)
    with pytest.raises(OverflowError):s.write(a[0],v,subtract=True)

@pytest.mark.parametrize('seed',[1,7,13])
def test_hopfield_native(seed):
    p=bip(seed,7,31);q=bip(seed+1,1,31)[0];t=torch.tensor(p,dtype=torch.float64);x=torch.tensor(q,dtype=torch.float64)
    assert np.array_equal(classical_field(p,q),memory.hopfield(x,t).numpy())
    assert np.allclose(dense_associative_field(p,q),memory.modern_hopfield(x,t).numpy(),atol=1e-11)


def test_continuous_against_scalar_and_attention():
    p=np.array([[1.,0.],[0.,1.],[-1.,0.]]);q=np.array([.2,.8]);beta=3
    w=np.array([np.exp(beta*sum(x*y for x,y in zip(r,q))) for r in p]);expected=sum(x*r for x,r in zip(w,p))/sum(w)
    assert np.allclose(continuous_hopfield(p,q,beta),expected)
    w=torch.softmax(beta*(torch.tensor(p)@torch.tensor(q)),dim=0)
    assert np.allclose(continuous_hopfield(p,q,beta),w.numpy()@p)


def test_cleanup_abstain_and_snapshot():
    a=np.array([[1,-1],[-1,1]],np.float32);c=Cleanup(Spec('MAP',2),a);q=a[0].copy();a[:]=0
    assert c.propose(q,minimum=.9,margin=.2).index==0
    assert c.propose(np.ones(2,np.float32),minimum=-1,margin=0) is None
    assert c.propose(np.array([1,0],np.float32),minimum=.9,margin=0) is None


def test_phase_working_composition():
    rng=np.random.default_rng(12);p=np.exp(1j*rng.uniform(-np.pi,np.pi,(5,512))).astype(np.complex64);w=PhaseWorkingMemory(512,capacity=2);bank=Cleanup(w.spec,p[2:])
    assert w.cue(p[0]) is None;w.add(p[0],p[2]);w.add(p[1],p[3])
    for i in range(2):assert bank.propose(w.cue(p[i]),minimum=.5,margin=.2).index==i
    with pytest.raises(OverflowError):w.add(p[0],p[4])


def test_two_tier_trace_and_missing_long_term():
    from cognitum.research.hdc_associative import TwoTierRecall
    rng=np.random.default_rng(98);p=np.exp(1j*rng.uniform(-np.pi,np.pi,(4,512))).astype(np.complex64)
    addresses=np.array([[1,1,1,1],[-1,-1,-1,-1]],np.int8);hard=np.array([[1,1,1,1],[1,1,1,-1],[-1,-1,-1,-1],[-1,-1,-1,1]],np.int8)
    values=np.array([[1,1,-1],[-1,1,1]],np.int8);s=SparseDistributed(hard,3,1);w=PhaseWorkingMemory(512);t=TwoTierRecall(w,p[2:],addresses,s,values.astype(np.float32))
    assert t.propose(p[0]) is None
    w.add(p[0],p[2]);w.add(p[1],p[3]);s.write(addresses[0],values[0]);assert t.propose(p[1]) is None
    s.write(addresses[1],values[1]);assert tuple(x.index for x in t.propose(p[1]))==(1,1)


@pytest.mark.parametrize('q',[np.zeros(2,np.float32),np.array([1,1],np.float32)])
def test_zero_and_tie_abstain(q):
    c=Cleanup(Spec('MAP',2),np.array([[1,-1],[-1,1]],np.float32))
    assert c.propose(q,minimum=-1,margin=0) is None

@pytest.mark.parametrize('bad',[np.array([1j,0]),np.array([np.nan,0]),np.array([np.inf,0])])
def test_continuous_reject_invalid(bad):
    with pytest.raises(ValueError):continuous_hopfield(np.eye(2),bad,1)
