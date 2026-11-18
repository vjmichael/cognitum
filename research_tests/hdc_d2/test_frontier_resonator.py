import numpy as np
import itertools
import pytest
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_ghrr import GHRRSpec
from cognitum.research.hdc_resonator_frontier import *

def fixture(family='MAP',n=5,d=256,seed=8):
    rng=np.random.default_rng(seed);s=Spec(family,d)
    banks=[rng.choice([-1.,1.],size=(n,d)).astype(s.dtype) if family=='MAP' else np.exp(1j*rng.uniform(-np.pi,np.pi,(n,d))).astype(s.dtype) for _ in range(3)]
    return CoupledResonator(s,banks)

@pytest.mark.parametrize('rule',['relu','polynomial','softmax'])
def test_weight_oracle(rule):
    a=np.array([-2.,.1,.5,1.]);w=cleanup_weights(a,rule,beta=3.)
    ref=np.exp(3*a) if rule=='softmax' else np.maximum(a,0)**(2 if rule=='polynomial' else 1)
    np.testing.assert_allclose(w,ref/ref.sum())
@pytest.mark.parametrize('rule',['relu','polynomial'])
def test_zero_rectified(rule):np.testing.assert_allclose(cleanup_weights([-1,-2],rule),[.5,.5])
@pytest.mark.parametrize('family',['MAP','FHRR'])
@pytest.mark.parametrize('rule',RULES)
def test_recurrent_known_fixed(family,rule):
    r=fixture(family);ids=(1,2,3);q=r.compose(ids);out=r.decode(q,rule=rule,initial=ids,steps=50)
    if family=='FHRR' and rule=='sign':
        # Phase feedback can reconstruct perfectly without settling to a fixed state.
        assert out.status=='budget' and out.ids is None and out.projections==150 and out.decoded_ids==ids
    else:
        assert out.ids==ids and out.status=='fixed' and out.projections>=3
    assert out.score>0.9999
@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_exhaustive_scalar(family):
    r=fixture(family);q=r.compose((1,2,3));q=q.copy();q[:17]*=-1
    oracle=sorted([(r.spec.similarity(q,r.compose(ids)),ids) for ids in itertools.product(range(5),repeat=3)],reverse=True)
    a=r.exhaustive(q);assert a.ids==oracle[0][1];assert a.score==pytest.approx(oracle[0][0],abs=1e-6)
    with pytest.raises(ValueError):r.exhaustive(q,max_candidates=10)
@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_ambiguous_exact_collision(family):
    r=fixture(family);banks=[x.copy() for x in r.banks];banks[0][1]=banks[0][0];r=CoupledResonator(r.spec,banks)
    q=r.compose((0,0,0));assert r.exhaustive(q).ids is None
    assert r.decode(q,initial=(0,0,0)).ids is None

def test_budget_zero_invalid():
    r=fixture();q=r.compose((1,2,3));assert r.decode(q*0).ids is None
    with pytest.raises(ValueError):r.decode(q,steps=251)
    with pytest.raises(ValueError):r.decode(q.astype('float64'))
    with pytest.raises(ValueError):r.decode(q,initial=(1,2,99))

def test_seed_replay_and_counts():
    r=fixture();q=r.compose((1,2,3));a=r.decode(q,seed=12,restarts=3,steps=7,asynchronous=False);b=r.decode(q,seed=12,restarts=3,steps=7,asynchronous=False)
    assert a==b and a.projections==3*a.sweeps and a.sweeps<=21

def test_classical_factorized_energy_and_direct_dense():
    rng=np.random.default_rng(3);p=rng.choice([-1,1],(5,64)).astype(np.int8);q=p[0].copy();q[:8]*=-1
    a=iterate_classical(p,q);w=p.astype(np.int64).T@p.astype(np.int64)-len(p)*np.eye(64,dtype=np.int64);x=q.copy()
    for _ in range(a.sweeps):
        for i in range(len(x)):
            f=w[i]@x
            if f:x[i]=np.sign(f)
    np.testing.assert_array_equal(a.state,x); assert np.all(np.diff(a.energies)<=0)

def test_continuous_iteration_energy():
    p=np.eye(5);q=np.array([.8,.05,.05,.05,.05]);r=iterate_continuous(p,q,beta=16)
    assert r.status=='fixed' and np.argmax(r.state)==0 and np.all(np.diff(r.energies)<=1e-12)

@pytest.mark.parametrize('family',['FHRR','GHRR'])
def test_directed_paths(family):
    if family=='FHRR':
        s=Spec('FHRR',128);rng=np.random.default_rng(11);v=np.exp(1j*rng.uniform(-np.pi,np.pi,(2,128))).astype(s.dtype)
    else:s=GHRRSpec(32,2);v=s.random_atoms(2,11)
    e=(Edge('a','r','b','1'),Edge('b','s','c','2'),Edge('a','s','d','3'),Edge('d','r','e','4'))
    p=OrderedPaths(s,dict(zip(('r','s'),v)),e,'v1');q=p.encode(('r','s'))
    assert s.similarity(q,p.encode(('s','r')))<.9
    ranked=p.candidates('a',q,2);assert ranked[0][1]==e[:2]
    assert p.verify(ranked[0][1],start='a',relations=('r','s'),current_snapshot='v1',canonical_edges=e)==('c',('1','2'))
    assert p.verify(ranked[1][1],start='a',relations=('r','s'),current_snapshot='v1',canonical_edges=e) is None
    assert p.verify(e[:2],start='a',relations=('r','s'),current_snapshot='v1',canonical_edges=e[1:]) is None
    with pytest.raises(ValueError):p.verify(e[:2],start='a',relations=('r','s'),current_snapshot='v2',canonical_edges=e)
    with pytest.raises(OverflowError):p.candidates('a',q,2,max_paths=1)

@pytest.mark.parametrize('family',['MAP','FHRR'])
def test_unknown_and_superposition_do_not_gain_authority(family):
    r=fixture(family,n=5,d=512);rng=np.random.default_rng(91);q=r.compose((1,2,3));alien=rng.choice([-1.,1.],size=q.shape).astype(q.dtype) if family=='MAP' else np.exp(1j*rng.uniform(-np.pi,np.pi,q.shape)).astype(q.dtype)
    a=r.decode(alien,rule='relu',steps=20,restarts=2,minimum=.95);assert a.ids is None
    both=(q+r.compose((3,1,0))).astype(q.dtype);a=r.decode(both,rule='relu',steps=20,restarts=2,minimum=.95);assert a.ids is None

def test_reject_unbounded_query():
    r=fixture();q=r.compose((1,2,3))*17
    with pytest.raises(ValueError):r.decode(q)
    with pytest.raises(ValueError):r.exhaustive(q)

@pytest.mark.parametrize('seed',[7,9,11])
def test_actual_torchhd_synchronous_map(seed):
    import torch,torchhd
    from importlib.metadata import version
    assert version('torch-hd')=='5.8.4'
    r=fixture('MAP',n=5,d=128,seed=seed);q=r.compose((1,2,3));states=np.stack([np.where(b.sum(0)>=0,1,-1).astype(np.float32) for b in r.banks]);domains=np.stack(r.banks)
    native=lambda a:torchhd.ensure_vsa_tensor(torch.from_numpy(a.copy()),vsa='MAP')
    out=torchhd.resonator(native(q),native(states),native(domains)).detach().cpu().numpy()
    # TorchHD uses sign(0)=0; this research engine explicitly projects zero to +1.
    np.testing.assert_array_equal(np.stack(r.sweep(q,states,asynchronous=False)),np.where(out>=0,1,-1))
