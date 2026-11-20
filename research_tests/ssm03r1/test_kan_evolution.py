"""Repository-native KAN weak-form bridge; requires existing COG-04P fixtures."""
import hashlib
import numpy as np
import pytest
from cognitum.research import kan_weak_form as p, ssm_extended as d
from tools.cog04o.fixtures import elliptic,transient


@pytest.mark.parametrize('velocity',[None,[0],[2]])
def test_real_kan_evolution(velocity):
    basis=(elliptic(),);raw=p.assemble(basis)
    r=d.kan_evolution(basis,[1],.125,16,velocity)
    assert r['assembly_sha256']==hashlib.sha256(raw).hexdigest()
    assert not r['physical_pde_solution'] and not r['execution_authorized']
    t=r['times']
    ref=np.exp(-20*t) if velocity is None else np.cos(np.sqrt(20)*t)+velocity[0]*np.sin(np.sqrt(20)*t)/np.sqrt(20)
    np.testing.assert_allclose(r['states'][:,0],ref,atol=1e-9)


def test_time_basis_refused():
    with pytest.raises(ValueError,match='spatial-only'):
        d.kan_evolution((transient(),),[1],.125,4)
