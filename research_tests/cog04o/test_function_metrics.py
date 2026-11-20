from fractions import Fraction as Q
import json
import pytest
from cognitum.research import kan_function_metrics as m
from tools.cog04o.fixtures import elliptic,transient,spacetime
from tools.cog04o.oracle import reference


def compare(a,b):return json.loads(m.compare(a,b))
def q(row,key):return Q(row[key])


def test_quadrature_moments_and_gram():
    g=m._axis_gram((),(),0);d=m._axis_gram((),(),1)
    assert g[6][7]==Q(1,6)
    assert d[6][5]==1
    assert all(g[i][j]==g[j][i] for i in range(9) for j in range(9))
    assert all(d[i][j]==d[j][i] for i in range(9) for j in range(9))


def test_refined_equivalent_fields():
    a,b=elliptic(),elliptic(refined=True)
    r=compare(a,b)
    assert q(r['l2'],'left_squared')==Q(9,100)
    assert q(r['h1_seminorm'],'left_squared')==Q(9,5)
    assert q(r['h1'],'left_squared')==Q(189,100)
    assert q(r['h1'],'distance_squared')==0
    assert q(r['l2'],'distance_squared')==0
    assert r['pde_target_error_claim'] is False and r['execution_authorized'] is False
    assert m.replay(a,b,m.compare(a,b))


def test_zero_and_scaled_fields():
    a,b=elliptic(),elliptic(refined=True,scale=2)
    r=compare(a,b)
    assert q(r['l2'],'inner')==Q(9,50)
    assert q(r['l2'],'distance_squared')==Q(9,100)
    assert q(r['h1'],'right_squared')==4*Q(189,100)
    z=compare(a,elliptic(scale=0))
    assert q(z['h1'],'right_squared')==0
    assert q(z['h1'],'distance_squared')==Q(189,100)


def test_signed_cross_and_symmetry():
    a,b=elliptic(),elliptic(refined=True,scale=-1)
    r,s=compare(a,b),compare(b,a)
    assert q(r['h1'],'inner')==-Q(189,100)
    assert q(r['h1'],'distance_squared')==4*Q(189,100)
    assert r['h1']==s['h1']


def test_nonzero_initial_lift():
    r=compare(transient(),transient(correction=True))
    assert q(r['l2'],'left_squared')==Q(3,10)
    assert q(r['l2'],'right_squared')==Q(21,10)
    assert q(r['l2'],'inner')==Q(3,4)
    assert q(r['l2'],'distance_squared')==Q(9,10)
    assert q(r['components'][2],'left_squared')==0
    assert q(r['components'][2],'right_squared')==Q(27,10)
    assert q(r['h1'],'right_squared')==Q(129,5)


def test_rank_three_lift():
    r=compare(spacetime(),spacetime(correction=True))
    assert r['axes']==['x','y','t']
    assert q(r['l2'],'left_squared')==Q(9,100)
    assert q(r['l2'],'right_squared')==Q(63,100)
    assert q(r['h1'],'right_squared')==Q(351,25)


def test_incompatible_profiles_same_rank():
    with pytest.raises(ValueError,match='incompatible'):m.compare(elliptic(),transient())


def test_tampered_checkpoint():
    with pytest.raises(ValueError):m.compare(b'not a checkpoint',elliptic())


def test_tampered_receipt():
    a,b=elliptic(),elliptic(refined=True)
    r=compare(a,b);r['l2']['inner']='0'
    with pytest.raises(ValueError,match='replay'):m.replay(a,b,m.f.canonical(r))
    with pytest.raises(ValueError,match='size'):m.replay(a,b,b'x'*(m.MAX_RECEIPT+1))


def test_independent_gram_refuses_corruption(monkeypatch):
    genuine=m._poly_inner
    monkeypatch.setattr(m,'_poly_inner',lambda *a:genuine(*a)+1)
    with pytest.raises(ValueError,match='Gram quadrature'):m._axis_gram((),(),0)


def test_invalid_order_and_aggregate_budget(monkeypatch):
    with pytest.raises(ValueError):m._axis_gram((),(),2)
    a=elliptic()
    monkeypatch.setattr(m,'MAX_WORK',1)
    with pytest.raises(ValueError,match='work budget'):m.compare(a,a)


@pytest.mark.parametrize('make',[lambda:(elliptic(),elliptic(refined=True,scale=2)),
                              lambda:(transient(),transient(correction=True)),
                              lambda:(spacetime(),spacetime(correction=True))])
def test_independent_scipy_reference(make):
    a,b=make();r=compare(a,b);ref,n=reference(a,b)
    assert n>0 and len(ref)==len(r['components'])
    for x,y in zip(r['components'],ref):
        for k in y:assert abs(float(Q(x[k]))-y[k])<=1e-10+1e-10*abs(y[k])
