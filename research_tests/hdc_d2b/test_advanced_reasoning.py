import numpy as np
import pytest
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_resonator_frontier import CoupledResonator,OrderedPaths,Edge
from cognitum.research.hdc_reasoning_advanced import (correlated_banks,coordinate_beam,peel,gsbc_correlate,BlockFactorizer,graph_rank_features,rank_hv,GraphFingerprintIndex,execute_program,synthesize,transfer_rule,verified_rule_paths)

@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_correlated_mask(family):
    s=Spec(family,128);b=correlated_banks(s,3,8,.5,123);c=correlated_banks(s,3,8,.5,123)
    assert all(np.array_equal(x,y) for x,y in zip(b,c));assert all(np.allclose(abs(x),1) for x in b)
    assert all(np.count_nonzero(np.all(x==x[0],axis=0))>=64 for x in b)
    r=CoupledResonator(s,b);q=r.compose((2,3,4));assert r.exhaustive(q).ids==(2,3,4)

@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_beam_and_peel(family):
    s=Spec(family,256);e=CoupledResonator(s,correlated_banks(s,3,4,0,901));a=(0,1,2);b=(3,2,1)
    assert coordinate_beam(e,e.compose(a),width=16,sweeps=4,seed=5)[0]==a
    ids,res,_=peel(e,2*e.compose(a)+e.compose(b),2,method='exhaustive');assert set(ids)=={a,b} and res<1e-4
    tied,_,_=peel(e,e.compose(a)+e.compose(b),2,method='exhaustive');assert not tied
    assert coordinate_beam(e,np.zeros(s.dimension,s.dtype))[0] is None

@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_ambiguous_correlated(family):
    s=Spec(family,64);e=CoupledResonator(s,correlated_banks(s,3,4,1,1));assert e.exhaustive(e.compose((0,0,0))).ids is None

@pytest.mark.parametrize('length',[4,7,16])
def test_correlation_oracle(length):
    r=np.random.default_rng(length);a=r.random((3,length));b=r.random((3,length));a/=a.sum(1,keepdims=True);b/=b.sum(1,keepdims=True)
    truth=np.array([[sum(a[j,(i+k)%length]*b[j,k] for k in range(length)) for i in range(length)] for j in range(3)])
    np.testing.assert_allclose(gsbc_correlate(a,b),truth,atol=1e-14)

@pytest.mark.parametrize('metric',['linf','dot'])
def test_sparse_decode(metric):
    r=np.random.default_rng(52);e=BlockFactorizer([r.integers(0,64,(8,32)) for _ in range(3)],64);ids=(3,4,2);q=e.encode(ids)
    assert e.exhaustive(q).ids==ids
    x=e.decode(q,metric=metric,sampling=2,threshold=.005,seed=12);assert x.searches<=512 and x==e.decode(q,metric=metric,sampling=2,threshold=.005,seed=12)
    if x.ids is not None:assert x.score>=.5 and x.ids==ids
    assert e.nbytes==3*8*32*2

def test_sparse_metric_and_ambiguous():
    b=np.zeros((3,4),np.int64);e=BlockFactorizer([b,b],8);q=e.encode((0,1));assert e.exhaustive(q).ids is None
    assert e.decode(q).ids is None
    v=np.random.default_rng(3).random((4,8));v/=v.sum(1,keepdims=True)
    assert np.allclose(e._scores(v,b,'linf'),[1-np.max(abs(v-np.eye(8)[p])) for p in b])

@pytest.mark.parametrize('bad',[np.ones((3,3)),np.zeros((2,3)),np.array([[0,1],[0,0]])])
def test_graph_bad(bad):
    with pytest.raises(ValueError):graph_rank_features(bad)

@pytest.mark.parametrize('centrality',['pagerank','degree'])
def test_graph_permutation(centrality):
    a=np.zeros((6,6),int);a[0,1:]=a[1:,0]=1;p=[3,0,5,4,1,2]
    f=graph_rank_features(a,centrality=centrality);assert f==graph_rank_features(a[np.ix_(p,p)],centrality=centrality)
    assert sum(f.values())==5 and np.array_equal(rank_hv(f,128,1),rank_hv(f,128,1))

def test_hash_collisions():
    h=GraphFingerprintIndex(bits=0);a={(0,1):5};b={(0,0):4};h.insert('a',a);h.insert('b',b);h.insert('c',a)
    assert h.lookup(a)==('a','c') and h.lookup(b)==('b',);h.remove('a');assert h.lookup(a)==('c',)
    with pytest.raises(ValueError):h.insert('c',b)

@pytest.mark.parametrize('program',[('shift_left',),('reverse','recolor'),('shift_right','shift_right')])
def test_program_synthesis(program):
    train=[((3,1),(8,2)),((6,3),(9,2))];test=((4,2),(11,1));data=[(x,execute_program(x,program)) for x in train]
    for s in [None,Spec('FHRR',128)]:
        p,checked,ranks=synthesize(data,spec=s,budget=20,seed=3);assert p and checked<=20
        assert execute_program(test,p)==execute_program(test,program);assert ranks==(20 if s else 0)

def test_dsl_controls():
    assert execute_program(((0,1),),('shift_left',)) is None
    with pytest.raises(ValueError):execute_program(((1,1),),('exec',))
    with pytest.raises(ValueError):execute_program(((1,1),(1,2)),('reverse',))

def make_graph(snapshot,prefix):
    s=Spec('FHRR',128);rng=np.random.default_rng(4);r={n:np.exp(1j*rng.uniform(-np.pi,np.pi,128)).astype(s.dtype) for n in ['a','b','c','d']};es=[]
    for i in range(2):
        p=prefix+str(i);es.extend([Edge(p,'a',p+'x',p+'1'),Edge(p+'x','b',p+'y',p+'2'),Edge(p,'c',p+'y',p+'3'),Edge(p,'d',p+'x',p+'4')])
    return OrderedPaths(s,r,es,snapshot)

def test_rule_disjoint_entity_witness():
    train=make_graph('train','t');test=make_graph('test','v');assert len(transfer_rule(train,('a','b'),'c',['t0','t1']))==2
    p=verified_rule_paths(test,'v0',('a','b'),'c',current_snapshot='test',canonical_edges=test.edges);assert p==(('v0y',('v01','v02'),'v03'),)
    assert verified_rule_paths(test,'v0',('a','b'),'c',current_snapshot='test',canonical_edges=[x for x in test.edges if x.witness!='v03'])==()
    with pytest.raises(ValueError):verified_rule_paths(test,'v0',('a','b'),'c',current_snapshot='old',canonical_edges=test.edges)

def test_rule_negative_support():
    t=make_graph('train','t');assert transfer_rule(t,('a','b'),'d',['t0','t1']) is None

@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_equal_pair_joint_oracle(family):
    from cognitum.research.hdc_reasoning_advanced import exact_equal_pair
    s=Spec(family,128);e=CoupledResonator(s,correlated_banks(s,3,4,0,91));a=(0,1,2);b=(3,2,1);q=e.compose(a)+e.compose(b)
    ids,res,pairs=exact_equal_pair(e,q);assert set(ids)=={a,b} and res<1e-5 and pairs==2016
    with pytest.raises(ValueError):exact_equal_pair(e,q,max_pairs=10)
    e=CoupledResonator(s,correlated_banks(s,3,4,1,91));assert exact_equal_pair(e,2*e.compose(a))[0] is None


def test_compact_block_native():
    import torch
    import torchhd
    # Native BSBC modular binding uses one position per block; independent
    # conventional and actual native comparisons on exact shared operands.
    from torchhd.tensors.bsbc import BSBCTensor
    r=np.random.default_rng(20);a,b=r.integers(0,32,(2,8,16));e=BlockFactorizer([a,b],32)
    x=torch.tensor(a[3],dtype=torch.int64).as_subclass(BSBCTensor);x.block_size=32
    y=torch.tensor(b[4],dtype=torch.int64).as_subclass(BSBCTensor);y.block_size=32
    np.testing.assert_array_equal(torchhd.bind(x,y).numpy(),e.positions((3,4)))
