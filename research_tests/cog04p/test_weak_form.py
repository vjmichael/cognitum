from fractions import Fraction as Q
import json
import numpy as np
import pytest
from cognitum.research import kan_weak_form as p
from tools.cog04p.oracle import verify
from tools.cog04p.fixtures import probe
from tools.cog04o.fixtures import elliptic,transient,spacetime

def test_analytic_ritz():
    a=elliptic();raw,s=p.spectrum((a,));r=json.loads(raw)
    assert Q(r['mass'][0][0])==Q(9,100)
    assert Q(r['stiffness'][0][0])==Q(9,5)
    assert s['values']==pytest.approx([20])
    assert verify((a,),raw,s)['max_eigenvalue_difference']<1e-10

def test_exact_crossgrid_dependence():
    with pytest.raises(ValueError,match='singular'):p.assemble((elliptic(),elliptic(refined=True)))

def test_zero_field():
    with pytest.raises(ValueError,match='singular'):p.assemble((elliptic(scale=0),))

def test_mixed_profile():
    with pytest.raises(ValueError,match='incompatible'):p.assemble((elliptic(),transient()))

def test_signed_basis():
    a,b=elliptic(),probe('J');raw,s=p.spectrum((a,b));r=json.loads(raw)
    assert r['mass'][0][1]==r['mass'][1][0]
    assert r['stiffness'][1][0]==r['stiffness'][0][1]
    assert all(Q(x)>0 for x in r['exact_mass_ldl_pivots'])
    assert s['values']==sorted(s['values'])
    verify((a,b),raw,s)

@pytest.mark.parametrize('a,b,axes',[(transient,lambda:probe('K'),['x']),
                                      (spacetime,lambda:probe('L'),['x','y'])])
def test_spatial_only(a,b,axes):
    fields=(a(),b());raw,s=p.spectrum(fields)
    assert json.loads(raw)['stiffness_axes']==axes
    assert verify(fields,raw,s)['quadrature_points']>0

def test_budget(monkeypatch):
    monkeypatch.setattr(p,'MAX_WORK',0)
    with pytest.raises(ValueError,match='work budget'):p.assemble((elliptic(),))

def test_count_and_wire():
    with pytest.raises(ValueError,match='basis count'):p.assemble(())
    with pytest.raises(ValueError,match='basis count'):p.assemble((b'x',)*5)
    with pytest.raises(ValueError):p.assemble((b'bad',))

def test_replay():
    a=elliptic();raw=p.assemble((a,))
    assert p.replay((a,),raw)
    with pytest.raises(ValueError,match='replay'):p.replay((a,),raw+b' ')

def test_condition_guard(monkeypatch):
    monkeypatch.setattr(p,'MAX_CONDITION',.5)
    with pytest.raises(ValueError,match='condition'):p.spectrum((elliptic(),))

def test_corrupt_spectrum():
    a=elliptic();raw,s=p.spectrum((a,));s['values'][0]+=1
    with pytest.raises(ValueError,match='spectral disagreement'):verify((a,),raw,s)

def test_semidefinite_witness():
    assert p._ldl([[Q(0),Q(0)],[Q(0),Q(1)]],False)==(0,1)
    with pytest.raises(ValueError):p._ldl([[Q(0),Q(1)],[Q(1),Q(0)]],False)
