from fractions import Fraction as Q
from itertools import product
from math import pi
import json
import numpy as np
import pytest
from cognitum.research import kan_sturm_liouville as r
from tools.cog04r.fixtures import CASES
from tools.cog04r.oracle import reference,verify

@pytest.mark.parametrize('name',list(CASES))
def test_convergence(name):
    p=CASES[name];ref=reference(p);rows=r.history(p)
    assert len(rows)==4
    for raw,v in rows:verify(p,raw,v,ref)
    raw,v=rows[-1]
    assert max(verify(p,raw,v,ref)['scaled_errors'])<1e-5

@pytest.mark.parametrize('left,right',list(product(('D','N','R'),repeat=2)))
def test_endpoint_combinations(left,right):
    p=r.Problem((1,1),(0,0),(1,0),(left,int(left=='R')),(right,int(right=='R')))
    raw,v=r.solve(p,(Q(1,2),))
    a=json.loads(raw)
    assert a['dof']==5-int(left=='D')-int(right=='D')
    assert a['constant_null_mode']==(left==right=='N')
    assert v['values'][0]==0 if left==right=='N' else v['values'][0]>0
    assert r.replay(p,(Q(1,2),),raw)

def test_analytic_references():
    for name,values in [('DD',[(i*pi)**2 for i in (1,2,3)]),('NN',[(i*pi)**2 for i in (0,1,2)]),
                        ('DN',[(i*pi)**2 for i in (.5,1.5,2.5)])]:
        assert reference(CASES[name])['values']==pytest.approx(values,rel=2e-9,abs=1e-9)

def test_weight_and_robin_identity():
    cuts=(Q(1,2),)
    p=r.Problem((1,1),(0,1),(1,1),('R',1),('R',2))
    a=json.loads(r.assemble(p,cuts))
    assert sum(Q(x) for row in a['mass'] for x in row)==Q(3,2)
    assert sum(Q(x) for row in a['stiffness'] for x in row)==Q(7,2)
    assert all(Q(v)>0 for v in a['stiffness_ldl'])

def test_reject_invalid_inputs():
    with pytest.raises(ValueError):r.Problem((1,-1),(0,0),(1,0),('D',0),('D',0))
    with pytest.raises(ValueError):r.Problem((1,0),(0,-1),(1,0),('D',0),('D',0))
    with pytest.raises(ValueError):r.Problem((1,0),(0,0),(1,0),('R',-1),('D',0))
    with pytest.raises(ValueError):r.Problem((1.,0),(0,0),(1,0),('D',0),('D',0))
    with pytest.raises(ValueError):r.assemble(CASES['DD'],(Q(1,3),))
    with pytest.raises(ValueError):r.history(CASES['DD'],5)
    with pytest.raises(ValueError):r.solve(CASES['DD'],(Q(1,2),),4)

def test_replay_corruption():
    p=CASES['NN'];cuts=(Q(1,2),);raw=r.assemble(p,cuts)
    with pytest.raises(ValueError,match='replay'):r.replay(p,cuts,raw+b' ')
    with pytest.raises(ValueError,match='replay'):r.replay(CASES['RR'],cuts,raw)
