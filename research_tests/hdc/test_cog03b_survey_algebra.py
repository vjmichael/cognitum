import numpy as np
import pytest
from cognitum.research.hdc_survey_algebra import *


def test_tpr_dual_role_and_order():
    R=np.array([[1.,1.],[0.,1.]])
    f,g=np.array([3.,4.]),np.array([-2.,5.])
    x=tpr_bind(R[:,0],f)+tpr_bind(R[:,1],g)
    dual=np.linalg.inv(R)
    np.testing.assert_allclose(tpr_extract(dual[0],x),f)
    np.testing.assert_allclose(tpr_extract(dual[1],x),g)
    assert not np.array_equal(tpr_bind(f,g),tpr_bind(g,f))
    with pytest.raises(ValueError): tpr_bind(np.ones(257),np.ones(257))


def test_mbat_exact_and_singular():
    R=np.array([[1.,2.],[2.,1.],[1.,-1.]])
    f=np.array([3.,4.])
    np.testing.assert_allclose(mbat_bind(R,f),[11.,10.,-1.])
    np.testing.assert_allclose(mbat_recover(R,mbat_bind(R,f)),f)
    with pytest.raises(ValueError): mbat_recover(np.ones((2,2)),np.ones(2))


def test_sparse_and_or_and_order():
    a=np.array([[1,0,1,0],[0,1,1,0]],bool)
    np.testing.assert_array_equal(sparse_conjunction(a),[0,0,1,0])
    np.testing.assert_array_equal(sparse_disjunction(a),[1,1,1,0])
    np.testing.assert_array_equal(sparse_conjunction(a),sparse_conjunction(a[::-1]))
    with pytest.raises(ValueError): sparse_conjunction(a.astype(int))


def test_additive_cdt_equation():
    a=np.array([[1,0,1,0,0],[0,1,0,0,0]],bool)
    p=np.array([[4,0,1,2,3],[2,3,4,0,1]],np.int64)
    z=np.any(a,axis=0)
    expected=np.array([z[i] and any(z[int(q[i])] for q in p) for i in range(len(z))])
    np.testing.assert_array_equal(additive_cdt(a,p),expected)
    np.testing.assert_array_equal(additive_cdt(a[::-1],p),expected)
    with pytest.raises(ValueError): additive_cdt(a,np.zeros((1,5),np.int64))


def test_euclidean_clifford_blades():
    e=np.eye(8)
    for i in [1,2,4]: np.testing.assert_array_equal(geometric_bind(e[i],e[i]),e[0])
    np.testing.assert_array_equal(geometric_bind(e[1],e[2]),e[3])
    np.testing.assert_array_equal(geometric_bind(e[2],e[1]),-e[3])
    np.testing.assert_array_equal(geometric_bind(e[3],e[3]),-e[0])
    rng=np.random.default_rng(31); a,b,c=rng.normal(size=(3,8))
    np.testing.assert_allclose(geometric_bind(geometric_bind(a,b),c),geometric_bind(a,geometric_bind(b,c)),atol=1e-12)
    with pytest.raises(ValueError): geometric_bind(np.ones(6),np.ones(6))
