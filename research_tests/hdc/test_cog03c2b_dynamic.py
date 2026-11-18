import itertools
import numpy as np
import pytest
from cognitum.research.hdc_dynamic_spatial import VDCToggle,SpatialSketch,SparseProjection
from cognitum.research.hdc_capacity import MAPBSet,map_b_gap,map_b_error,BloomSketch,sparse_or_density
from cognitum.research.hdc_encoders import CodebookSpec

@pytest.mark.parametrize('d',[8,32,256])
def test_vdc_scalar_recurrence(d):
    g=VDCToggle(d)
    for t in range(d):
        state=False;expected=[]
        for x in range(d):
            r=int(f'{x:0{d.bit_length()-1}b}'[::-1],2)
            state^=r<t;expected.append(state)
        assert np.array_equal(g.atom(t),expected)
    assert g.audit(2)['antipodes']==1
    assert np.array_equal(g.atom(3),VDCToggle(d).atom(3))
    with pytest.raises(ValueError):g.atom(d)

@pytest.mark.parametrize('n',[1,3,5,7,9])
def test_map_b_gap_exhaustive(n):
    a=np.array(list(itertools.product([-1,1],repeat=n)))
    assert map_b_gap(n)==pytest.approx(np.mean(a[:,0]*np.sign(a.sum(1))))
    fn,fp=map_b_error(7,n)
    g=map_b_gap(n);threshold=g/2
    # independent enumerated score distribution, seven IID Bernoulli outcomes
    rows=np.array(list(itertools.product([0,1],repeat=7)))
    k=rows.sum(1);bad=(2*k/7-1)<threshold;p=(1+g)/2
    assert fn==pytest.approx(np.sum((p**k*(1-p)**(7-k))[bad]))
    assert fp==pytest.approx(np.mean(~bad))

def test_map_b_direct_boolean_oracle():
    m=MAPBSet(33,42,[1,3,5]);s=CodebookSpec(33,42)
    b=s.bits(1,1)[0].astype(int)+s.bits(1,3)[0]+s.bits(1,5)[0]>=2
    for i in range(9):assert m.score(i)==pytest.approx(1-2*np.mean(b!=s.bits(1,i)[0]))
    with pytest.raises(ValueError): MAPBSet(33,42,[1,2])

@pytest.mark.parametrize('counting',[False,True])
def test_sparse_or_counted_oracle(counting):
    a=BloomSketch(31,5,123,[0,1,9],counting);c=np.zeros(31,int)
    for i in (0,1,9):
        for j in a.positions(i):c[j]+=1
    if counting: assert np.array_equal(a.data,c)
    else:assert np.array_equal(np.unpackbits(a.data,bitorder='little')[:31],c>0)
    for i in range(30):assert a.contains(i)==bool(np.all(c[a.positions(i)]>0))
    assert all(a.contains(i) for i in (0,1,9))
    with pytest.raises(ValueError): BloomSketch(31,5,123,[1,1],counting)

def test_counting_intersection_formula_exhaustive():
    # n=m=2 items, overlap=1, k=2 positions, M=2 slots. Enumerate 6 draws.
    estimates=[]
    for row in itertools.product([0,1],repeat=6):
        a=np.bincount(row[:4],minlength=2);b=np.bincount(row[2:],minlength=2)
        estimates.append((a@b-2*2*4/2)/(2*(1-1/2)))
    assert np.mean(estimates)==pytest.approx(1)
    a=BloomSketch(32,4,8,[1,2],True);b=BloomSketch(32,4,8,[2,3],True)
    assert a.estimate_intersection(b)==pytest.approx((a.data.astype(int)@b.data.astype(int)-2*2*16/32)/(4*(1-1/32)))
    with pytest.raises(ValueError):a.estimate_intersection(BloomSketch(32,4,9,[1],True))
    assert sparse_or_density(2,2,2)==pytest.approx(15/16)

@pytest.mark.parametrize('d',[32,128])
def test_spatial_isometry_and_retrieval(d):
    x=np.array([[.1,.2],[.7,.8]]);y=np.array([.25,.75]);l=np.linspace(0,1,17);w=np.array([.1,.1,.2])
    a=SpatialSketch.fit(x,y,l,d,31,w);b=SpatialSketch.fit(x,y,l,d,31,w,'hrr')
    assert np.allclose(a.memory,np.fft.fft(b.memory))
    for q in [x[0],x[1],np.array([.2,.3])]:
        assert np.allclose(a.query_vector(q),np.fft.fft(b.query_vector(q)))
        for cleanup in ['none','hopfield','resonator']:assert a.predict(q,cleanup)==pytest.approx(b.predict(q,cleanup),abs=1e-12)
    single=SpatialSketch.fit(x[:1],y[:1],l,d,31,w)
    assert np.allclose(single.query_vector(x[0]),single._phase(single.frequencies,np.r_[0.,0.,y[0]],d,'fhrr'))
    assert abs(single.predict(x[0])-.25)<.15
    with pytest.raises(ValueError):a.predict(np.array([1.]))

@pytest.mark.parametrize('binding',['and','xor'])
def test_sparse_train_fit_and_scalar_counts(binding):
    x=np.array([[0.,.2,1.],[.2,.5,.6],[1.,.9,.8]])
    a=SparseProjection.fit(x,64,42,.1,binding);c=np.zeros((3,64),int)
    for i in range(3):
        r=np.random.default_rng(np.random.SeedSequence([42,i]));p=r.random(64)<.1;u=r.random(64)
        for j in range(3):
            for h in range(64):c[j,h]+=bool(x[j,i]>u[h]) & bool(p[h]) if binding=='and' else bool(x[j,i]>u[h]) ^ bool(p[h])
    assert np.array_equal(c,a.counts(x));assert np.array_equal(a.threshold,np.median(c,axis=0))
    before=a.threshold.copy();a.bits(np.ones((1,3)));assert np.array_equal(before,a.threshold)
    with pytest.raises(ValueError):a.bits(np.ones((1,3))*2)
    assert not a.threshold.flags.writeable

from cognitum.research.hdc_dynamic_spatial import NoShiftSymbols,QuasiNormalLevels,vdc_sequence

def test_no_shift_growth_and_order():
    s=NoShiftSymbols(512,57);a=s.atom(3,2);g=s.ngram([2,3,4]);s.atom(90,17)
    assert np.array_equal(a,s.atom(3,2));assert np.array_equal(g,s.ngram([2,3,4]))
    assert not np.array_equal(g,s.ngram([4,3,2]))
    assert np.array_equal(g,s.atom(2,0)^s.atom(3,1)^s.atom(4,2))
    with pytest.raises(ValueError):s.atom(2**20,0)

def test_qnd_radical_inverse_and_level_monotonicity():
    assert np.array_equal(vdc_sequence(8,2),[0,.5,.25,.75,.125,.625,.375,.875])
    q=QuasiNormalLevels(64,16);a=q.sequence()
    assert np.allclose(a,np.mean([vdc_sequence(64,2**j) for j in range(1,7)],axis=0))
    assert np.all(q.level(.3)<=q.level(.6));assert np.array_equal(q.symbol(3),q.level(3/16)^(vdc_sequence(64,16)<.5))
    with pytest.raises(ValueError):q.symbol(16)

from cognitum.research.hdc_dynamic_spatial import ScreenedSymbols
from cognitum.research.hdc_capacity import bloom_exact_fp

def test_screened_append_atomic_and_replay():
    bank=ScreenedSymbols(VDCToggle(128)).append(0)
    with pytest.raises(ValueError):bank.append(1)
    assert bank.ids==(0,)
    b=ScreenedSymbols(CodebookSpec(1024,31)).append(1).append(2)
    c=b.append(199);assert c.ids==(1,2,199);assert np.array_equal(c.atom(2),b.atom(2))
    assert np.array_equal(c.atom(199),ScreenedSymbols(c.spec,c.ids).atom(199))
    with pytest.raises(ValueError):c.append(2)

@pytest.mark.parametrize('m,k,n',[(2,1,1),(3,2,2),(4,2,2)])
def test_bloom_occupancy_exhaustive(m,k,n):
    hits=[]
    for x in itertools.product(range(m),repeat=n*k):
        hits.append((len(set(x))/m)**k)
    assert bloom_exact_fp(m,k,n)==pytest.approx(np.mean(hits),abs=1e-14)

@pytest.mark.parametrize('d',[32,128,512])
def test_half_fhrr_exact_geometry(d):
    x=np.array([[.1,.2],[.7,.8]]);y=np.array([.25,.75]);l=np.linspace(0,1,17);w=np.array([.1,.1,.2]);a=SpatialSketch.fit(x,y,l,d,31,w);b=SpatialSketch.fit(x,y,l,d,31,w,'half-fhrr')
    assert np.array_equal(a.memory[:d//2+1],b.memory)
    assert b.memory.nbytes==(d//2+1)*16
    for q in [x[0],x[1],np.array([.2,.3])]:
        for mode in ['none','hopfield','resonator']:assert a.predict(q,mode)==pytest.approx(b.predict(q,mode),abs=2e-12)
