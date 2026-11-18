import itertools
import math
from collections import Counter
import numpy as np
import pytest
from cognitum.research.hdc_encoders import CodebookSpec
from cognitum.research.hdc_structured_encoders import (OrderedLevels, structured_sum,
    gaussian_level, mux4, polygon_encode, tree_leaf_gaps, tree_error,
    distinct_sparse_fp, gappy_counts, gappy_pair_counts, propagation_counts)

@pytest.mark.parametrize('mode',['level','thermometer','density'])
def test_nested_levels(mode):
    s=OrderedLevels(64,9,123,mode);a=np.stack([s.atom(i) for i in range(9)])
    assert np.array_equal(np.count_nonzero(a^a[0],axis=1),np.arange(9)*8)
    assert np.count_nonzero(a[0]^a[-1])==64
    assert np.array_equal(a[4],s.atom(4))

def test_circular():
    s=OrderedLevels(64,8,4,'circular');a=np.stack([s.atom(i) for i in range(8)])
    assert np.all(a.sum(1)==32)
    assert np.count_nonzero(a[0]^a[1])==np.count_nonzero(a[0]^a[-1])==16
    assert np.count_nonzero(a[0]^a[4])==64

def test_levels_guard():
    with pytest.raises(ValueError):OrderedLevels(63,8,0,'circular')
    with pytest.raises(ValueError):OrderedLevels(8,10,0)
    with pytest.raises(ValueError):OrderedLevels(8,3,0).atom(True)

def test_structured_roles():
    s=CodebookSpec(1024,42);a=(5,6,7);b=(8,9,10)
    t=structured_sum([a,b],s)
    assert np.array_equal(t,structured_sum([b,a],s))
    assert np.array_equal(t,structured_sum([a],s)+structured_sum([b],s))
    assert not np.array_equal(structured_sum([a],s),structured_sum([(7,6,5)],s))

@pytest.mark.parametrize('n',[0.,1.,.2,.5,.8])
def test_gaussian_level(n):
    x=np.random.default_rng(9).normal(size=32768);a=gaussian_level(n,x)
    assert abs(a.mean()-n)<.012
    assert np.all(~gaussian_level(max(0,n-.1),x)|a)

def test_mux_truth_table():
    x,y=np.asarray(list(itertools.product([False,True],repeat=2))).T
    for i in range(4):
        a=np.zeros((4,4),bool);a[i]=True
        assert np.array_equal(mux4(a,x,y),np.asarray(x,dtype=int)+2*y==i)

def test_mux_expected_and_correlation_control():
    r=np.random.default_rng(7);n=65536;x=r.normal(size=n)
    p=[.1,.6,.3,.9];a=np.stack([gaussian_level(v,x) for v in p]);sx=r.random(n)<.25;sy=r.random(n)<.75
    expected=np.dot(p,[.75*.25,.25*.25,.75*.75,.25*.75])
    assert abs(mux4(a,sx,sy).mean()-expected)<.01
    q=r.random(n)<.5;corners=np.array([np.zeros(n,bool),np.ones(n,bool),np.ones(n,bool),np.zeros(n,bool)])
    assert mux4(corners,q,q).sum()==0 # correlated selectors violate bilinear expectation

def test_polygon_tile_replay():
    a=np.array([[0.,.3],[.7,1.]])
    for scale in (1,2,4):
        x=polygon_encode(a,67,4,scale,block=1)
        assert np.array_equal(x,polygon_encode(a,67,4,scale,block=11))
        assert np.max(abs(x))<=a.size*scale**2

def test_polygon_single_pixel():
    a=np.array([[1.]])
    for scale in (1,2,4):
        spec=CodebookSpec(63,5);expected=2*spec.bits(scale**2).sum(axis=0,dtype=np.int32)-scale**2
        assert np.array_equal(polygon_encode(a,63,5,scale),expected)

def test_tree_exact_enumeration():
    tree=((0,1,2),3,4);gaps=tree_leaf_gaps(tree)
    atoms=np.asarray(list(itertools.product([-1,1],repeat=5)))
    s=np.sign(np.sign(atoms[:,:3].sum(axis=1))+atoms[:,3]+atoms[:,4])
    for i,g in gaps.items():assert np.mean(s*atoms[:,i])==pytest.approx(g)
    assert gaps[0]==pytest.approx(.25) and gaps[3]==pytest.approx(.5)
    assert tree_error(8192,gaps[0])[0]<tree_error(128,gaps[0])[0]

def test_tree_refuses_repeat():
    with pytest.raises(ValueError):tree_leaf_gaps((1,2,(1,3,4)))
    with pytest.raises(ValueError):tree_leaf_gaps((1,2))

def test_distinct_sparse_enumeration():
    choices=list(itertools.combinations(range(5),2));vals=[]
    for a,b,q in itertools.product(choices,repeat=3): vals.append(set(q)<=set(a)|set(b))
    assert distinct_sparse_fp(5,2,2)==pytest.approx(np.mean(vals))
    assert distinct_sparse_fp(5,2,0)==0
    assert distinct_sparse_fp(5,5,1)==1

def test_gappy_features():
    assert gappy_counts('ABCD',2,3)==Counter(['AB','AC','BC','BD','CD'])
    assert gappy_pair_counts('ABCDE',2,1)==Counter(['ABCD','ABDE','BCDE'])
    assert gappy_pair_counts('AAA',1,1)==Counter({'AA':3})

def test_graph_permutation_psd():
    a=np.array([[0,1,0],[1,0,1],[0,1,0]],bool);y=np.array([0,1,1]);w=np.array([[1.,-.1],[-1.,1.]])
    f=propagation_counts(a,y,w); p=[2,0,1]
    assert f==propagation_counts(a[np.ix_(p,p)],y[p],w)
    g=propagation_counts(a,np.array([1,0,0]),w);keys=sorted(f.keys()|g.keys())
    x=np.array([[c[k] for k in keys] for c in (f,g)],float)
    assert np.linalg.eigvalsh(x@x.T).min()>=-1e-10
    with pytest.raises(ValueError):propagation_counts(np.triu(a),y,w)


def test_native_thermometer_parity():
    import torchhd
    a=torchhd.thermometer(9,64,'BSC').numpy()
    s=OrderedLevels(64,9,123,'thermometer')
    assert np.array_equal(a,np.stack([s.atom(i) for i in range(9)]))


@pytest.mark.parametrize('method',['level','circular'])
def test_native_ordered_replay(method):
    import torch,torchhd
    f=getattr(torchhd,method)
    a=f(8,64,'BSC',generator=torch.Generator().manual_seed(7))
    b=f(8,64,'BSC',generator=torch.Generator().manual_seed(7))
    assert a.shape==(8,64) and a.dtype==torch.bool and torch.equal(a,b)
    assert torch.unique(a,dim=0).shape[0]==8
    # The native randomized geometry is not the exact anchored custom geometry.


def test_native_density_binding():
    import torch,torchhd
    torch.manual_seed(7)
    e=torchhd.embeddings.Density(3,64)
    x=torch.tensor([[0.,.25,1.],[.5,1.,0.]])
    expected=(e.key.weight*e.density_encoding(x)).sum(dim=-2)
    assert torch.equal(e(x),expected)


def test_grouped_holdout_no_proportional_duplicate():
    from tools.cog03c2c_pilot import group_split
    c=[Counter({str(i):k}) for i in range(12) for k in (1,2)]
    y=np.repeat(np.arange(12)%2,2)
    train,test=group_split(c,y,17)
    assert not (set(train//2)&set(test//2))
    assert len(train)+len(test)==24


def test_real_protocol_tiny_replay():
    from tools.cog03c2c_pilot import measure
    rows=['AACA'+('A' if i%2==0 else 'G')+'C'*i+'TT' for i in range(12)]
    y=np.arange(12)%2
    a=measure('promoter',rows,y,11,'resident',64)
    b=measure('promoter',rows,y,11,'streamed',64)
    assert a['predictions']==b['predictions'] and a['split_sha256']==b['split_sha256']
    assert a['landmark_ids']==b['landmark_ids']
    assert b['serialized_snapshot_bytes']<a['serialized_snapshot_bytes']
