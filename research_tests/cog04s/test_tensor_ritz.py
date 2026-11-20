from fractions import Fraction as Q
from math import pi
import json
import pytest
from cognitum.research import kan_tensor_ritz as s
from tools.cog04s.fixtures import CASES
from tools.cog04s.oracle import verify,continuum,sums

@pytest.mark.parametrize('name',list(CASES))
def test_convergence(name):
    p=CASES[name];ref=continuum(p);rows=s.history(p)
    results=[verify(p,a,b,ref) for a,b in rows]
    assert max(results[-1]['scaled_errors'])<1e-5
    assert any(x['dense_reference'] is not None for x in results)

def test_analytic_multiplicity():
    assert continuum(CASES['square-DD'])['values']==pytest.approx([2*pi*pi,5*pi*pi,5*pi*pi],rel=2e-9)
    assert continuum(CASES['box-DD'])['values']==pytest.approx([3*pi*pi,6*pi*pi,6*pi*pi],rel=2e-9)
    assert continuum(CASES['box-NN'])['values']==pytest.approx([0,pi*pi,pi*pi],rel=2e-9,abs=1e-9)

def test_exact_entries():
    p=CASES['square-DD'];cuts=((Q(1,2),),)*2
    raw=s.assemble(p,cuts);d=json.loads(raw)
    m=Q(d['factors'][0]['mass'][0][0]);k=Q(d['factors'][0]['stiffness'][0][0])
    assert s.entry(raw,(0,0),(0,0))==(m*m,2*k*m)
    assert s.entry(raw,(0,1),(1,0))==s.entry(raw,(1,0),(0,1))
    assert s.replay(p,cuts,raw)

def test_reject():
    p=CASES['square-DD'];c=((Q(1,2),),)*2
    with pytest.raises(ValueError):s.Problem(p.axes,(0,1))
    with pytest.raises(ValueError):s.Problem(p.axes[:1],(1,))
    with pytest.raises(ValueError):s.assemble(p,c[:1])
    with pytest.raises(ValueError):s.solve(p,c,4)
    with pytest.raises(ValueError):s.replay(p,c,s.assemble(p,c)+b' ')
    with pytest.raises(ValueError):s.entry(s.assemble(p,c),(3,0),(0,0))

def test_length_and_order():
    assert sums([[1,4],[2,8]],(1,2),3)==[1.5,3.,4.5]
    assert s.combine([[1,4],[2,8]],(Q(1),Q(1,4)),3)==[(1.5,(0,0)),(3.,(0,1)),(4.5,(1,0))]

def test_actual_tensor_null():
    p=CASES['box-NN'];raw,row=s.solve(p,((Q(1,2),),)*3)
    assert json.loads(raw)['constant_null_mode']
    assert row['values'][0]==0
    assert row['mass_orthogonality']<1e-8
