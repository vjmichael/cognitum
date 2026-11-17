import numpy as np
import pytest
from cognitum.research.hdc_encoders import *

@pytest.mark.parametrize('method',['iid','sobol','halton','hadamard'])
def test_indexed_codebook_stable(method):
    s=CodebookSpec(64,5721,method);a=s.bits(16)
    np.testing.assert_array_equal(a[3:7],s.bits(4,3));np.testing.assert_array_equal(a,s.bits(16));np.testing.assert_array_equal(a,s.bits(24)[:16]);assert a.dtype==bool
    assert coherence(a)['pairs']==120

def test_hadamard_and_antipode_rejection():
    a,r=screened(CodebookSpec(64,15,'hadamard'),64,0.)
    assert r['max_abs']==0
    with pytest.raises(ValueError): CodebookSpec(63,15,'hadamard')
    with pytest.raises(ValueError): CodebookSpec(32,15,'hadamard').bits(33)
    s=CodebookSpec(64,21,'sobol');assert coherence(s.bits(32))['antipodes']>0
    with pytest.raises(ValueError): screened(s,32,.95)
    b=np.array([[True,False],[True,False],[False,True]]);r=coherence(b);assert r['duplicates']==1 and r['antipodes']==2

@pytest.mark.parametrize('d',[1,7,8,9,63,64,65,1024])
def test_packed_exact_scores_and_immutability(d):
    r=np.random.default_rng(81);a=r.integers(0,2,(12,d)).astype(bool);q=r.integers(0,2,d).astype(bool)
    b=PackedBank.from_bits(a);expect=np.count_nonzero(a!=q,axis=1);np.testing.assert_array_equal(b.distances(pack(q)),expect)
    np.testing.assert_array_equal(b.scores(pack(q)),1-2*expect/d);assert b.nbytes==len(a)*((d+7)//8)
    with pytest.raises(ValueError):b.packed.setflags(write=True)
    if d%8:
        bad=pack(q);bad[-1]|=128
        with pytest.raises(ValueError):b.distances(bad)

def test_phase8_quantization_and_exact_lut():
    r=np.random.default_rng(131);a=np.exp(1j*r.uniform(-np.pi,np.pi,(16,257))).astype(np.complex64);q=a[0]
    c=phase8(a);d=phase8(q);rest=phase8_decode(c);s=PhaseBank(c)
    errors=np.abs(np.angle(rest*a.conj()));assert np.max(errors)<=np.pi/256+1e-6
    expect=(rest*phase8_decode(d).conj()).real.mean(axis=1)
    np.testing.assert_allclose(s.scores(d),expect,atol=2e-7)
    assert s.nbytes==a.size and a.nbytes==8*s.nbytes
    assert np.max(np.abs(s.scores(d)-(a*q.conj()).real.mean(axis=1)))<=2*np.pi/256+1e-6
    with pytest.raises(ValueError):phase8(a*2)
    with pytest.raises(ValueError):s.codes.setflags(write=True)

def test_continuous_phase_composition():
    r=np.random.default_rng(71);w=r.normal(size=(128,3));x,y=r.normal(size=(2,3));np.testing.assert_allclose(phase_encode(x+y,w),phase_encode(x,w)*phase_encode(y,w),atol=2e-7)
    with pytest.raises(ValueError):phase_encode(x.astype(np.float32),w)
    with pytest.raises(ValueError):phase_encode(x,w[:,:2])

def test_reject_invalid_and_padding():
    with pytest.raises(ValueError):PackedBank(9,np.array([[1,128]],np.uint8))
    with pytest.raises(ValueError):pack(np.ones(9))
    with pytest.raises(ValueError):CodebookSpec(0,1)
    with pytest.raises(ValueError):CodebookSpec(16,-1)
    with pytest.raises(ValueError):PhaseBank(np.empty((0,32),np.uint8))


def test_nystrom_psd_and_train_only_indices():
    r=np.random.default_rng(11);a=r.normal(size=(8,3));ids=np.arange(len(a),dtype=np.int64)
    encode,report=nystrom_reference(a,ids,gamma=.3);x=encode(a)
    exact=np.exp(-.3*((a[:,None,:]-a[None,:,:])**2).sum(axis=-1));np.testing.assert_allclose(x@x.T,exact,atol=1e-10)
    y=r.normal(size=(5,3));np.testing.assert_allclose(encode(y)@x.T,np.exp(-.3*((y[:,None,:]-a[None,:,:])**2).sum(axis=-1)),atol=1e-10)
    assert report['rank']==8
    with pytest.raises(ValueError):nystrom_reference(a,np.array([len(a)],np.int64),gamma=.3)
    with pytest.raises(ValueError):nystrom_reference(a,np.array([0,0],np.int64),gamma=.3)
