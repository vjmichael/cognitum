import numpy as np
import pytest
from cognitum.research.hdc_survey_algebra import SurveySpec, geometric_bind, geometric_unit_inverse

@pytest.mark.parametrize('family,shape',[('TPR',(3,4)),('MBAT',(12,)),('SPARSE_AND_OR',(12,)),('CDT',(12,)),('GEOMETRIC',(8,))])
def test_reference_operations(family,shape):
    s=SurveySpec(family,shape)
    a=np.zeros(shape,s.dtype);a.flat[1]=1
    b=np.zeros(shape,s.dtype);b.flat[2]=1
    kw={'permutations':np.arange(12,dtype=np.int64)[None,:]} if family=='CDT' else {}
    bundled=s.bundle([a,b],**kw)
    np.testing.assert_array_equal(bundled,a.astype(int)+b.astype(int))
    assert s.similarity(a,a)==1 and s.similarity(a,b)==0
    pk={'axis':0} if family=='TPR' else {}
    np.testing.assert_array_equal(s.permute(s.permute(a,2,**pk),-2,**pk),a)
    ids,scores=s.cleanup(a,[b,a,a],min_similarity=.9,k=3)
    np.testing.assert_array_equal(ids,[1,2]);np.testing.assert_array_equal(scores,[1,1])
    assert not len(s.cleanup(a,[b],min_similarity=.5)[0])
    with pytest.raises(ValueError): s.similarity(a,np.zeros_like(a)) if s.dtype!=bool else s.similarity(np.zeros_like(a),np.zeros_like(a))
    with pytest.raises(ValueError): s.bundle(np.zeros((0,*shape),s.dtype))
    with pytest.raises(ValueError): s.cleanup(a,[b],min_similarity=float('nan'))
    with pytest.raises(ValueError): s.similarity(a,b.astype(np.complex128))

@pytest.mark.parametrize('shift',[-5,0,1,2,3])
def test_geometric_basis_permutation_is_algebra_automorphism(shift):
    s=SurveySpec('GEOMETRIC',(8,));rng=np.random.default_rng(15);a,b=rng.normal(size=(2,8))
    np.testing.assert_allclose(s.permute(geometric_bind(a,b),shift),geometric_bind(s.permute(a,shift),s.permute(b,shift)),atol=1e-12)

def test_geometric_unit_inverse_and_rejection():
    v=np.zeros(8);v[1]=.6;v[2]=.8
    w=np.eye(8)[4];u=geometric_bind(v,w);one=np.eye(8)[0]
    np.testing.assert_allclose(geometric_bind(u,geometric_unit_inverse(u)),one,atol=1e-12)
    with pytest.raises(ValueError): geometric_unit_inverse(u*2)
    with pytest.raises(ValueError): geometric_unit_inverse(np.zeros(8))

def test_heterogeneous_shape_and_explicit_policy():
    with pytest.raises(ValueError): SurveySpec('TPR',(257,257))
    with pytest.raises(ValueError): SurveySpec('GEOMETRIC',(12,))
    with pytest.raises(ValueError): SurveySpec('TPR',(2,2)).permute(np.ones((2,2)),1)
    with pytest.raises(ValueError): SurveySpec('CDT',(4,)).bundle(np.ones((2,4),bool))
    s=SurveySpec('MBAT',(2,));assert s.similarity(np.array([1e300,0.]),np.array([1e300,0.]))==1


def test_typed_composition_and_recovery():
    a=np.array([1.,0.]);b=np.array([3.,4.,5.]);s=SurveySpec('TPR',(2,3));x=s.compose(a,b);np.testing.assert_array_equal(s.recover(a,x),b)
    role=np.array([[1.,0.],[0.,1.],[1.,1.]]);s=SurveySpec('MBAT',(3,));f=np.array([2.,4.]);np.testing.assert_allclose(s.recover(role,s.compose(role,f)),f)
    s=SurveySpec('GEOMETRIC',(8,));eye=np.eye(8);x=s.compose(eye[1],eye[2]);np.testing.assert_array_equal(s.recover(eye[1],x,side='left'),eye[2]);np.testing.assert_array_equal(s.recover(eye[2],x,side='right'),eye[1]);
    with pytest.raises(ValueError):s.recover(eye[2],x)
    for family in ('SPARSE_AND_OR','CDT'):
        s=SurveySpec(family,(4,));a=np.array([1,1,0,0],bool);b=np.array([0,1,1,0],bool);kw={'permutations':np.arange(4,dtype=np.int64)[None,:]} if family=='CDT' else {}
        x=s.compose(a,b,**kw)
        with pytest.raises(ValueError):s.recover(a,x)
