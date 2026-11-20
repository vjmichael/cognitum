from fractions import Fraction as Q
import json
import pytest
from cognitum.research import kan_continuum_ritz as q
from tools.cog04q.oracle import verify

@pytest.fixture(scope='module')
def history():
    return q.adaptive()

def test_exact_initial_forms():
    raw=q.assemble((Q(1,2),));r=json.loads(raw)
    assert r['dof']==3
    for k in ('mass','stiffness'):
        a=r[k];assert all(a[i][j]==a[j][i] for i in range(3) for j in range(3))
        assert all(Q(x)>0 for x in r[k+'_ldl'])

def test_initial_analytic_reference(history):
    raw,r=history[0]
    assert r['values']==pytest.approx([9.87217667,42,94.25090025],rel=1e-8)
    assert verify(raw,r)['max_eigenvalue_difference']<1e-8

def test_nested_convergence(history):
    assert len(history)==9
    for (_,a),(_,b) in zip(history,history[1:]):
        assert set(a['cuts'])<set(b['cuts'])
        assert all(v<=u+1e-8 for u,v in zip(a['values'],b['values']))
    raw,r=history[-1];ref=verify(raw,r)
    assert r['dof']==11 and max(ref['relative_errors'])<1e-4

def test_full_independent_history(history):
    assert all(verify(raw,r)['quadrature_points']>0 for raw,r in history)

def test_invalid_knots():
    for c in ((),(Q(1,3),),(Q(1,2),Q(1,2)),(Q(1),),(0.5,),(Q(1,256),)):
        with pytest.raises(ValueError):q.assemble(c)

def test_invalid_modes_steps():
    with pytest.raises(ValueError):q.solve((Q(1,2),),4)
    with pytest.raises(ValueError):q.adaptive(steps=12)

def test_replay_and_oracle_corruption(history):
    raw,r=history[0]
    with pytest.raises(ValueError,match='replay'):q.replay((Q(1,2),),raw+b' ')
    with pytest.raises(ValueError,match='eigenspectrum'):verify(raw,{**r,'values':[v+1 for v in r['values']]})

def test_refinement_tie():
    cuts,i=q.refine((Q(1,2),),[1.,1.])
    assert i==0 and cuts==(Q(1,4),Q(1,2))
