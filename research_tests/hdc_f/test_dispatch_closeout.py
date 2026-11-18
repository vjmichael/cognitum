import numpy as np
import pytest
from cognitum.research.hdc_hardware import pack, scores
from cognitum.research.hdc_uncertain_visual import VisualBank,LevelEncoder,consolidate,hamming
from cognitum.research.hdc_cifar_fast import FastVisualBank,merge_exact,encode_rows,distance
from research_tests.hdc_f.test_hardware import native

@pytest.mark.parametrize('d',[1,65,511,512,1025,2048,4097,65536])
def test_dispatch_all(d,native):
    rng=np.random.default_rng(d);q=pack(rng.integers(0,2,(3,d)));p=pack(rng.integers(0,2,(5,d)))
    q[:,-1]|=np.uint64(~((1<<(d%64))-1)&((1<<64)-1)) if d%64 else np.uint64(0)
    ref=scores(q,p,d)
    for mode in range(4):
        if native.selected(d,mode)<0:
            with pytest.raises(RuntimeError):native.scores(q,p,d,mode)
        else:assert np.array_equal(native.scores(q,p,d,mode),ref)
    assert native.selected(d,3)==(2 if d>=2048 and native.capabilities&4 else 1 if native.capabilities&2 else 0)

@pytest.mark.parametrize('d',[65,512])
def test_fast_parity(d):
    rng=np.random.default_rng(d);enc=LevelEncoder(64,d,16,4);x=rng.integers(0,16,(60,64),dtype=np.uint8);z=encode_rows(enc,x)
    assert np.array_equal(z,np.stack([enc.encode(r) for r in x]));assert np.array_equal(distance(z[:,None,:],z[None,:,:],d),hamming(z[:,None,:],z[None,:,:],d))
    weights=np.arange(1,11);a,b=consolidate(z[:10],9,d,np.random.default_rng(8),weights=weights);c,e=merge_exact(z[:10],9,d,np.random.default_rng(8),weights)
    assert np.array_equal(a,c) and np.array_equal(b,e)
    for mode in ('merge','fixed','replace'):
        old=VisualBank(d,5,seed=12,novelty_floor=.99,mode=mode);new=FastVisualBank(d,5,seed=12,novelty_floor=.99,mode=mode)
        for v in z:
            assert old.observe(v)==new.observe(v);assert old.n==new.n and old.merges==new.merges
            for k in ('bank','mean','var','count'):assert np.array_equal(getattr(old,k),getattr(new,k))
        assert old.rng.bit_generator.state==new.rng.bit_generator.state


def test_rtl_vectors(tmp_path):
    from tools.cog03f_rtl import vectors
    a=vectors(tmp_path/'a');b=vectors(tmp_path/'b');assert a==b and a['cycles']>2000 and a['blocked_input_cycles']>0 and a['retired_results']>40 and a['resets']==2
