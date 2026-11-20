"""Conformal uncertainty and domain-shift limits (local math only)."""
import numpy as np
from math import ceil
import pytest
from scipy.stats import norm

@pytest.mark.parametrize('seed',[3,17,51])
def test_split_conformal_marginal_coverage_under_iid_exchangeability(seed):
    rng=np.random.default_rng(seed);alpha=.1;N=1000;ncal=29
    C=np.abs(rng.normal(size=(N,ncal)));T=np.abs(rng.normal(size=N))
    radius=np.sort(C,axis=1)[:,ceil((ncal+1)*(1-alpha))-1]
    coverage=np.mean(T<=radius)
    assert .87<coverage<.93
    # Split-conformal rank identity for iid continuous scores, here k/(n+1)=.9.
    assert ceil((ncal+1)*(1-alpha))/(ncal+1)==pytest.approx(.9)

@pytest.mark.parametrize('seed',[3,17,51])
def test_shift_breaks_the_same_coverage_assumption(seed):
    rng=np.random.default_rng(seed);N=1000;ncal=29;alpha=.1
    C=np.abs(rng.normal(size=(N,ncal)))
    R=np.sort(C,axis=1)[:,ceil((ncal+1)*(1-alpha))-1]
    shifted=np.abs(rng.normal(loc=3,scale=2,size=N))
    assert np.mean(shifted<=R)<.5


def test_calibration_metric_is_not_a_physical_certification():
    x=norm.isf(.05)
    assert x>1.64
    # Conditional heteroscedasticity is a counterexample to naive constant-scale extrapolation.
    assert 2*norm.sf(x/3)>.5
