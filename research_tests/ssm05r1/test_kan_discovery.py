"""Native KAN represented-field integration; not part of isolated local run."""
import itertools
import numpy as np
import pytest
from cognitum.research import ssm_identification_extended as e
from tools.cog04o.fixtures import elliptic


def test_kan_polynomial():
    X=np.array(list(itertools.product([0,.125,.375,.625,.875,1],repeat=2)))
    T=np.array(list(itertools.product([.25,.5,.75],repeat=2)))
    z=e.kan_polynomial(elliptic(),X,T,4,.01);coef=dict(zip(z['exponents'],z['coefficients'][:,0]))
    for p,c in { (1,1):9.,(1,2):-9.,(2,1):-9.,(2,2):9.}.items():
        assert coef[p]==pytest.approx(c,abs=1e-8)
    assert np.count_nonzero(z['coefficients'])==4 and z['heldout_rmse']<1e-9 and z['represented_field_only']


def test_kan_reject_domain():
    with pytest.raises(ValueError,match='KAN sample budget'):
        e.kan_polynomial(elliptic(),[[2,0]],[[0,0]],2,.1)
