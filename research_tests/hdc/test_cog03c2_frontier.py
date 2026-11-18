import numpy as np
import pytest
from cognitum.research.hdc_frontier_encoders import (NysHD, GaussianPhase, IndexedMAP, map_i_membership_bound, intersection_variance)


def test_nyshd_exact_geometry_and_packed_scores():
    g=np.array([[1.,.6],[.6,1.]])
    enc=NysHD.fit(g,32768,971)
    f=enc.features(g)
    np.testing.assert_allclose(f@f.T,g,atol=1e-12)
    b=enc.bank(g)
    s=enc.scaled_scores(b,g)
    np.testing.assert_allclose(np.diag(s),np.pi/2,atol=1e-12)
    assert abs(s[0,1]-np.arcsin(.6))<.025
    assert b.nbytes==8192
    assert enc.nbytes> b.nbytes


def test_nyshd_rank_and_negatives():
    model=NysHD.fit(np.ones((3,3)),64,5)
    assert model.inverse_root.shape==(3,1)
    with pytest.raises(ValueError): model.bits(np.zeros((1,3)))
    with pytest.raises(ValueError): NysHD.fit(np.array([[1.,2.],[2.,1.]]),64,1)
    with pytest.raises(ValueError): NysHD.fit(np.array([[1.,0.],[1.,1.]]),64,1)
    with pytest.raises(ValueError): model.bits(np.ones((1,2)))
    with pytest.raises(ValueError): model.projection[0,0]=0


@pytest.mark.parametrize('width',[.25,1.,4.])
def test_gaussian_fpe_translation_kernel(width):
    e=GaussianPhase.sample(32768,np.array([width,2*width]),711)
    a=np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.]])
    z=e.encode(a)
    np.testing.assert_allclose(z[1]*z[2],z[3],atol=2e-7)
    for i in [1,2,3]:
        expected=np.exp(-.5*np.sum((a[i]/[width,2*width])**2))
        assert abs(np.vdot(z[0],z[i]).real/z.shape[1]-expected)<.018


def test_gaussian_rejects_bad_width_and_shape():
    with pytest.raises(ValueError): GaussianPhase.sample(32,np.array([0.]),5)
    e=GaussianPhase.sample(32,np.array([1.]),5)
    with pytest.raises(ValueError): e.encode(np.ones((2,2)))


def test_indexed_map_update_and_intersection():
    a=IndexedMAP(2048,8,5);b=IndexedMAP(2048,8,5)
    for i in [1,2,3]:a.add(i)
    for i in [2,3,4]:b.add(i)
    assert abs(a.estimate_intersection(b)-2)<.3
    before=a.accumulator.copy();a.add(9);a.remove(9)
    np.testing.assert_array_equal(a.accumulator,before)
    assert a.accounting()['member_id_bytes']==12
    for i in [1,2,3]:a.remove(i)
    assert not a.accumulator.any()
    with pytest.raises(ValueError):a.remove(1)
    with pytest.raises(ValueError):a.estimate_intersection(IndexedMAP(2048,9,5))


def test_capacity_bound_and_independent_variance():
    assert map_i_membership_bound(8192,32,10)<1e-10
    assert intersection_variance(2,2,2,2)==2
    # Enumerate all one-coordinate signs, sets {0,1} and {1,2}.
    import itertools
    samples=np.array([(a+b)*(b+c) for a,b,c in itertools.product([-1,1],repeat=3)])
    assert samples.mean()==1 and samples.var()==intersection_variance(1,2,2,1)
    with pytest.raises(ValueError):map_i_membership_bound(0,3)
    with pytest.raises(ValueError):intersection_variance(64,2,2,3)


@pytest.mark.parametrize('dimension,block',[(257,8),(1024,128),(1025,256)])
def test_stream_exact_packed_replay(dimension,block):
    from cognitum.research.hdc_frontier_encoders import StreamedNysHD
    from cognitum.research.hdc_encoders import pack
    rng=np.random.default_rng(198);x=rng.normal(size=(8,5));g=x@x.T
    cross=rng.normal(size=(13,5))@x.T
    model=NysHD.fit(g,dimension,932);stream=StreamedNysHD(model.inverse_root,dimension,932)
    np.testing.assert_array_equal(stream.packed(cross,block),pack(model.bits(cross)))
    assert stream.nbytes<model.nbytes
    with pytest.raises(ValueError):stream.packed(cross,9)
