import numpy as np
import pytest
from cognitum.research.hdc_ghrr import GHRRSpec, FlatBank
from cognitum.research.hdc_algebra import Spec

@pytest.mark.parametrize('d,m',[(1,1),(13,1),(16,2),(17,3),(32,4),(4,8)])
@pytest.mark.parametrize('precision',['complex64','complex128'])
@pytest.mark.parametrize('seed',[4103,4111,4127])
def test_exact_matrix_and_flatten(d,m,precision,seed):
    s=GHRRSpec(d,m,precision); a,b,c=s.random_atoms(3,seed); tol=s.unit_tol
    assert s.unitary(a) and s.unitary(b) and s.unitary(c)
    np.testing.assert_array_equal(s.random_atoms(3,seed),np.stack([a,b,c]))
    # Scalar loops, not a second matrix API invocation, as binding oracle.
    ref=np.asarray([[[sum(complex(a[k,i,j])*complex(b[k,j,l]) for j in range(m)) for l in range(m)] for i in range(m)] for k in range(d)])
    ab=s.bind(a,b)
    np.testing.assert_allclose(ab,ref,atol=tol)
    np.testing.assert_allclose(s.unbind(a,ab,side='left'),b,atol=tol)
    np.testing.assert_allclose(s.unbind(b,ab,side='right'),a,atol=tol)
    np.testing.assert_allclose(s.bind(ab,c),s.bind(a,s.bind(b,c)),atol=tol)
    np.testing.assert_allclose(s.bind(a,s.inverse(a)),s.identity(),atol=tol)
    if m==1: np.testing.assert_allclose(ab,s.bind(b,a),atol=tol)
    else: assert np.linalg.norm(ab-s.bind(b,a))>0.01
    assert s.similarity(a,a)==pytest.approx(1,abs=tol)
    for x,y in [(a,b),(a+b,c),(a+b,2*b-c)]:
        manual=sum((complex(i).conjugate()*complex(j)).real for i,j in zip(x.flat,y.flat))/(d*m)
        assert s.similarity(x,y)==pytest.approx(manual,abs=1e-10)
        for policy in ['fixed','cosine']:
            expected=s.matrix_similarity(x,y,policy=policy)
            assert s.similarity(x,y,policy=policy)==pytest.approx(expected,abs=1e-10)
            bank=FlatBank(s,np.stack([a,b,c,x]),policy=policy)
            np.testing.assert_allclose(bank.scores(y),[s.matrix_similarity(z,y,policy=policy) for z in (a,b,c,x)],atol=1e-10)
    for side in ['left','right']:
        x,y=(s.bind(c,a),s.bind(c,b)) if side=='left' else (s.bind(a,c),s.bind(b,c))
        assert s.similarity(x,y)==pytest.approx(s.similarity(a,b),abs=tol)

@pytest.mark.parametrize('d',[16,256,1024])
def test_scalar_reduction(d):
    s=GHRRSpec(d,1); f=Spec('FHRR',d)
    a,b=s.random_atoms(2,87)
    np.testing.assert_allclose(s.bind(a,b).ravel(),f.bind(a.ravel(),b.ravel()),atol=2e-6)
    assert s.similarity(a,b,policy='cosine')==pytest.approx(f.similarity(a.ravel(),b.ravel()),abs=2e-6)
    assert s.similarity(a,b)==pytest.approx(f.similarity(a.ravel(),b.ravel()),abs=2e-6)
    np.testing.assert_allclose(s.permute(a,3).ravel(),f.permute(a.ravel(),3))

def test_fixed_vs_cosine_and_zero():
    s=GHRRSpec(4,2); a=s.identity(); b=2*a
    assert s.similarity(a,b)==pytest.approx(2)
    assert s.similarity(a,b,policy='cosine')==pytest.approx(1)
    assert s.similarity(a,np.zeros_like(a))==0
    with pytest.raises(ValueError): s.inverse(b)
    with pytest.raises(ValueError): s.similarity(a,np.zeros_like(a),policy='cosine')
    with pytest.raises(ValueError): FlatBank(s,np.stack([a,np.zeros_like(a)]),policy='cosine')
    with pytest.raises(ValueError): FlatBank(s,np.stack([a]),policy='cosine').scores(np.zeros_like(a))

@pytest.mark.parametrize('m',[1,2,4])
def test_paper_encoder(m):
    s=GHRRSpec(64,m,'complex128'); q=s.random_atoms(1,25)[0]; r=np.random.default_rng(19)
    theta=r.normal(size=(64,m,3)); x,y=r.normal(size=(2,3))
    a,b=s.encode(x,theta,q),s.encode(y,theta,q)
    eye=s.identity()
    for j in range(64): np.testing.assert_allclose(a[j],q[j]@np.diag(np.exp(1j*(theta[j]@x))),atol=1e-12)
    assert s.unitary(a)
    assert s.similarity(a,b)==pytest.approx(np.cos(theta@(x-y)).mean(),abs=1e-12)
    np.testing.assert_allclose(s.encode(np.zeros(3),theta,q),q,atol=1e-12)
    np.testing.assert_allclose(s.bind(s.encode(x,theta,eye),s.encode(y,theta,eye)),s.encode(x+y,theta,eye),atol=1e-12)

def test_order_and_explicit_sides():
    s=GHRRSpec(3,2,'complex128')
    a=np.repeat(np.array([[[0,1],[1,0]]],complex),3,axis=0)
    b=np.repeat(np.array([[[1,0],[0,-1]]],complex),3,axis=0)
    ab=s.bind(a,b); ba=s.bind(b,a)
    assert s.similarity(ab,ba)==-1
    np.testing.assert_allclose(s.unbind(a,ab,side='left'),b)
    assert not np.allclose(s.unbind(a,ab,side='right'),b)
    with pytest.raises(ValueError): s.unbind(a,ab,side='bad')
    np.testing.assert_allclose(s.bundle([ab,ba]),np.zeros_like(ab))

def test_bank_immutable_deterministic_ties():
    s=GHRRSpec(16,2); a,b=s.random_atoms(2,19); rows=np.stack([a,a,b]); bank=FlatBank(s,rows)
    rows[:]=0
    assert bank.nbytes==3*s.scalar_count*16
    ids,scores=bank.topk(a,2)
    np.testing.assert_array_equal(ids,[0,1]); np.testing.assert_allclose(scores,[1,1],atol=1e-6)
    with pytest.raises(ValueError): bank.topk(a,0)
    with pytest.raises(ValueError): bank._real[0,0]=0

@pytest.mark.parametrize('args',[(0,2),(8,0),(True,2),(1,9),(65536,2),(10,2,'float32')])
def test_bad_specs(args):
    with pytest.raises(ValueError): GHRRSpec(*args)

def test_bad_operands_and_budget():
    s=GHRRSpec(16,2); a=s.identity()
    for bad in (a.ravel(),a.astype(np.complex128),np.full_like(a,np.nan)):
        with pytest.raises(ValueError): s.bind(a,bad)
    with pytest.raises(ValueError): s.random_atoms(0,1)
    with pytest.raises(ValueError): s.random_atoms(1,-1)
    with pytest.raises(ValueError): GHRRSpec(16384,2).random_atoms(4096,1)
    with pytest.raises(ValueError): s.bundle(np.empty((0,*s.shape),s.dtype))
    with pytest.raises(ValueError): s.similarity(a,a,policy='bad')
    with pytest.raises(ValueError): s.permute(a,True)

@pytest.mark.parametrize('d,m',[(32,2),(128,2),(32,4)])
@pytest.mark.parametrize('policy',['fixed','cosine'])
def test_native_accumulator_parity_and_cost(d,m,policy):
    s=GHRRSpec(d,m); a=s.random_atoms(16,1809); a[1]+=a[2]
    bank=FlatBank(s,a,policy=policy,accumulator='native')
    assert bank.nbytes==a.nbytes+(len(a)*4 if policy=='cosine' else 0)
    np.testing.assert_allclose(bank.scores(a[1]),[s.matrix_similarity(x,a[1],policy=policy) for x in a],atol=2e-6)
    with pytest.raises(ValueError): FlatBank(s,a,accumulator='bad')
