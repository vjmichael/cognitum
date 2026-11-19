"""Genuine existing NumPy KAN kernel versus independent interval evaluator."""
from types import SimpleNamespace as NS
import numpy as np
import pytest
from cognitum.research.kan_portable import PortableKAN
from cognitum.mel import uncertainty as u


def pair(rng,basis,degree,i,o,k,*,small=False):
    count=k-degree-1 if basis==1 else k
    grid=np.tile(np.linspace(-2,2,k,dtype=np.float32),(i,1))
    w=rng.uniform(-.1 if small else -1,.1 if small else 1,(o,i,count)).astype(np.float32)
    mask=rng.integers(0,2,(o,i)).astype(np.float32)
    base=rng.uniform(-.1,.1,(o,i)).astype(np.float32);bias=rng.uniform(-.1,.1,o).astype(np.float32)
    actual=dict(grid=grid,spline=w,mask=mask,base=base,bias=bias,degree=degree,kind='spline' if basis==1 else 'rbf')
    ref=NS(inputs=i,outputs=o,knots=k,basis=basis,degree=degree,grid=grid.ravel().tolist(),coefficients=w.ravel().tolist(),mask=mask.ravel().tolist(),base=base.ravel().tolist(),bias=bias.tolist())
    return actual,ref


@pytest.mark.parametrize('basis,degree',[(1,0),(1,1),(1,2),(1,3),(2,0)])
@pytest.mark.parametrize('seed',[7,81,902])
def test_real_kernel_against_reference(basis,degree,seed):
    rng=np.random.default_rng(seed); a,l=pair(rng,basis,degree,2,3,7,small=True)
    z=np.vstack((rng.uniform(-1.9,1.9,(5,2)),[2.,-2.],[0.,0.])).astype(np.float32)
    out=PortableKAN([a])(z)
    ref=u.kan_bounds([l],tuple(tuple(u.Interval.point(v) for v in row) for row in z.tolist()))
    for rr,yy in zip(ref,out.tolist()):
        for b,y in zip(rr,yy):
            assert u.error_verdict(b,y,2e-6)=='within'
            assert u.error_verdict(b,y+.01,2e-6)=='outside'


def test_real_two_layer_kernel():
    rng=np.random.default_rng(22); a,l=pair(rng,2,0,2,3,5,small=True);b,m=pair(rng,1,2,3,2,6,small=True)
    z=rng.uniform(-1.9,1.9,(5,2)).astype(np.float32)
    out=PortableKAN([a,b])(z)
    ref=u.kan_bounds([l,m],tuple(tuple(u.Interval.point(v) for v in row) for row in z.tolist()))
    for rr,yy in zip(ref,out.tolist()):
        assert all(u.error_verdict(x,y,2e-6)=='within' for x,y in zip(rr,yy))
