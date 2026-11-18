import numpy as np
import pytest
from cognitum.research.hdc_uncertain_visual import *

@pytest.mark.parametrize('groups',[None,np.arange(20)])
def test_rank(groups):
    a=np.stack([np.arange(20),np.arange(20)],axis=1); y=np.zeros(20,dtype=int)
    m=Mondrian(.1).fit(a,y,groups); assert m.cutoffs[0]==18 and np.isinf(m.cutoffs[1]); assert m.predict([[18,1],[19,1]]).tolist()==[[True,True],[False,True]]

def test_group_max():
    a=np.stack([np.arange(20),np.arange(20)],axis=1); m=Mondrian(.2).fit(a,np.zeros(20,dtype=int),np.repeat(np.arange(10),2));assert m.counts.tolist()==[10,0] and m.cutoffs[0]==17

def test_finite_sample_small():
    assert np.isinf(Mondrian(.1).fit([[0,1]],[0]).cutoffs).all()

def test_ties_included():
    m=Mondrian(.2).fit(np.ones((20,2)),np.repeat([0,1],10)); assert m.predict([[1,1]]).all()

def test_scores():
    p=np.array([[1,1,-1,-1],[-1,-1,1,1]]);w=np.array([[p[0],p[0]],[p[0],p[1]]]); a=scores(w,p)
    assert a[0,0,0]==0 and a[0,0,2]==0 and a[1,0,2]==.5;assert nonconformity(a)[0,0]<nonconformity(a)[0,1]

@pytest.mark.parametrize('d',[31,64,129])
def test_pack(d):
    enc=LevelEncoder(5,d,8,1);x=np.arange(5);p=np.unpackbits(enc.p,axis=1,count=d);l=np.unpackbits(enc.l,axis=1,count=d);oracle=np.packbits(((p^l[x]).sum(0)*2>=5).astype(np.uint8));np.testing.assert_array_equal(enc.encode(x),oracle);assert hamming(oracle,oracle,d)==0

def test_padding():
    assert hamming(np.array([0,0],np.uint8),np.array([0,127],np.uint8),9)==0

def test_consolidate():
    a=np.packbits(np.array([[0]*8,[0]*7+[1],[1]*8,[1]*7+[0]],np.uint8),axis=1)
    c,l=consolidate(a,2,8,np.random.default_rng(4),top_m=1);assert len(c)==2 and l[0]==l[1] and l[2]==l[3] and l[0]!=l[2]

@pytest.mark.parametrize('mode',['merge','replace','fixed'])
def test_bound(mode):
    m=VisualBank(65,4,seed=4,novelty_floor=.99,mode=mode);r=np.random.default_rng(5);n=m.numeric_bytes
    for _ in range(100):m.observe(np.packbits(r.integers(0,2,65)));assert m.n<=4 and m.numeric_bytes==n
    if mode=='merge':assert m.merges>0

def test_replay():
    r=np.random.default_rng(2); qs=np.packbits(r.integers(0,2,(70,33)),axis=1);a=VisualBank(33,5,seed=17,novelty_floor=.85);b=VisualBank(33,5,seed=17,novelty_floor=.85)
    assert [a.observe(q) for q in qs]==[b.observe(q) for q in qs];np.testing.assert_array_equal(a.bank,b.bank)

def test_predict_no_mutation():
    m=VisualBank(16,3);q=np.array([1,2],np.uint8);m.observe(q);b=m.bank.copy();m.predict(q);np.testing.assert_array_equal(m.bank,b)

@pytest.mark.parametrize('bad',[np.nan,np.inf,-np.inf])
def test_reject(bad):
    with pytest.raises(ValueError):Mondrian().fit([[bad,1]],[0])
    with pytest.raises(ValueError):LevelEncoder(3,32).encode([0,1,bad])
