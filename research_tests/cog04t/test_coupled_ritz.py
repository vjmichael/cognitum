from fractions import Fraction as Q
import json
import numpy as np
import pytest
from cognitum.research import kan_coupled_ritz as t
from tools.cog04t.fixtures import CASES
from tools.cog04t.oracle import verify,continuum

@pytest.mark.parametrize('name',list(CASES))
def test_convergence(name):
    p=CASES[name];ref=continuum(p);rows=t.history(p)
    checks=[verify(p,raw,row,ref) for raw,row in rows]
    e=[max(c['scaled_errors']) for c in checks]
    f=[max(c['left_function_errors']+c['right_function_errors']) for c in checks]
    assert e[-1]<1e-5 and f[-1]<1e-3
    assert e[-1]<e[0]/100 and f[-1]<f[0]/100
    assert e[-1]<e[-2] and f[-1]<f[-2]

def test_exact_drift_and_adjoint():
    p=CASES['drift-complex'];raw=t.assemble(p,(Q(1,2),));a=json.loads(raw)
    G=[[Q(x) for x in row] for row in a['drift_form']]
    assert any(x for row in G for x in row)
    assert all(G[i][j]==-G[j][i] for i in range(3) for j in range(3))
    m,A=t.numeric(raw)
    assert np.allclose(m,m.T) and not np.allclose(A,A.T)
    assert t.replay(p,(Q(1,2),),raw)

def test_complex_conjugate():
    p=CASES['complex'];raw,row=t.solve(p,(Q(1,2),))
    z=t.unpack(row['values'])
    assert all(abs(v.imag)>2 for v in z)
    assert all(min(abs(v-u.conjugate()) for u in z)<1e-9 for v in z)

def test_symmetric_and_nonnormal():
    p=CASES['symmetric'];m,A=t.numeric(t.assemble(p,(Q(1,2),)))
    assert np.allclose(A,A.T)
    _,row=t.solve(CASES['triangular'],(Q(1,2),))
    assert max(row['reciprocal_overlap_condition'])>1.5
    assert row['max_off_diagonal']<1e-8

def test_left_right_corruption():
    p=CASES['drift-real'];raw,row=t.solve(p,(Q(1,2),))
    bad={**row,'left_columns':row['right_columns']}
    with pytest.raises(ValueError,match='left/right'):verify(p,raw,bad)

def test_validation():
    for b,C in [(5,((1,0),(0,2))),(0,((1,1),(0,1))),(0,((1,5),(0,2))),(0,((1,2),)),(0.,((1,0),(0,2)))]:
        with pytest.raises(ValueError):t.Problem(b,C)
    p=CASES['complex'];cuts=(Q(1,2),);raw=t.assemble(p,cuts)
    with pytest.raises(ValueError):t.replay(p,cuts,raw+b' ')
    with pytest.raises(ValueError):t.replay(CASES['triangular'],cuts,raw)
    with pytest.raises(ValueError):t.history(p,5)
    with pytest.raises(ValueError):t.assemble(p,(Q(1,3),))
