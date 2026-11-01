"""KAN accepted-domain boundary must match one-sided spline value, not zero out."""
import numpy as np
import pytest

from cognitum.research.kan_portable import PortableKAN


def model(kind='spline', degree=0):
    grid=np.array([[0.,1.,2.,3.,4.]],dtype=np.float32)
    weights=np.array([[[2.,5.,7.,11.][:grid.shape[1]-degree-1]]],dtype=np.float32)
    layer={'kind':kind,'degree':degree,'grid':grid,'spline':weights,
           'mask':np.ones((1,1),np.float32),'base':None,'bias':None}
    return PortableKAN([layer])


def test_degree_zero_last_accepted_knot_is_left_limit():
    m=model()
    x=np.array([[4.0]],np.float32)
    left=np.nextafter(x,np.array([[-np.inf]],np.float32))
    assert m(x)[0,0]==11.0  # Old code silently returned zero.
    assert m(x)[0,0]==m(left)[0,0]


@pytest.mark.parametrize('degree',[0,1,2])
def test_boundary_matches_one_sided_float32_limit(degree):
    m=model(degree=degree)
    right=np.array([[4.0]],np.float32)
    interior=np.nextafter(right,np.array([[-np.inf]],np.float32))
    assert np.array_equal(m(right),m(interior))
    assert np.isfinite(m(right)).all()


def test_spline_interior_values_unchanged():
    m=model()
    values=m(np.array([[0.],[0.5],[1.],[2.],[3.],[3.999]],np.float32))[:,0]
    assert list(values)==[2.,2.,5.,7.,11.,11.]


def test_rbf_endpoint_not_affected_by_spline_adjustment():
    g=np.array([[0.,1.,2.]],np.float32)
    m=PortableKAN([{'kind':'rbf','degree':0,'grid':g,
                    'spline':np.ones((1,1,3),np.float32),
                    'mask':np.ones((1,1),np.float32),'base':None,'bias':None}])
    a=m(np.array([[2.]],np.float32))
    manual=np.exp(-((2-g[0])/1.0)**2).sum()
    assert np.isclose(a[0,0],manual,atol=1e-6)
