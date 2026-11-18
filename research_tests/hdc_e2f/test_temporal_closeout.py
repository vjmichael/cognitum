import numpy as np
import pytest
from cognitum.research.hdc_temporal import CategoricalHMM,LDNSummary
from cognitum.research.hdc_temporal_closeout import *

def model():return CategoricalHMM([1,0],[[0,1],[1,0]],[[1,0],[0,1]])

def test_dwell_one_exact():
    a=model();b=duration_hmm(a,1);assert np.array_equal(a.transition,b.transition);assert a.score([0,1,0])==b.score([0,1,0])

def test_min_dwell():
    m=duration_hmm(model(),3);assert m.score([0,0,0,1,1,1,0])==0.;assert m.score([0,0,1])==-np.inf

def test_dwell_stochastic():
    m=duration_hmm(CategoricalHMM([.4,.6],[[.8,.2],[.3,.7]],[[.1,.9],[.5,.5]]),4);assert np.allclose(m.transition.sum(1),1);assert np.isfinite(m.score([0,1]*100))
    with pytest.raises(ValueError):duration_hmm(model(),0)

def test_duration_tokens():
    assert np.array_equal(duration_tokens([0,0,1,0,0,0,0,0],2),[1,5,3]);assert not np.array_equal(duration_tokens([0,0,1],2),duration_tokens([0,1,1],2))

def test_batch_summary_oracle():
    x=np.random.default_rng(9).normal(size=(3,31,2));z=batched_summary(x,4,.3,1/64)
    assert np.allclose(z,[adaptive_summary(a) for a in x],atol=1e-13)
    with pytest.raises(ValueError):batched_summary(np.ones((65,3,1)))

def test_duration_normalized_constant():
    a=adaptive_summary(np.ones((32,1)),normalized=True);b=adaptive_summary(np.ones((64,1)),normalized=True);assert np.allclose(a[:4],b[:4],atol=1e-12)

def test_seeded_projection_replay_and_tail():
    r=np.random.default_rng(13);x=r.normal(size=(101,5));y=np.arange(101)%3;m=SeededPackedHead(131,4).fit(x,y);n=SeededPackedHead(131,4,block=17).fit(x,y)
    assert np.array_equal(m.head.bits,n.head.bits);assert np.array_equal(m.predict(x),n.predict(x));assert m.numeric_bytes==2*5*8+3*8+3*17+24;assert not (m.head.bits[:,-1]&248).any()

def test_seeded_head_bounded():
    x=np.arange(30).reshape(10,3);m=SeededPackedHead(32,1).fit(x,np.arange(10)%2)
    with pytest.raises(ValueError):m.encode(np.zeros((65,3)))
