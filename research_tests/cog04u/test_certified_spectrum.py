from fractions import Fraction as Q
from itertools import product
from math import pi
import json
import pytest
from cognitum.research import kan_certified_spectrum as u
from tools.cog04r.fixtures import CASES
from tools.cog04r.oracle import reference
from tools.cog04u.oracle import verify

@pytest.mark.parametrize('name',list(CASES))
def test_certificate_history(name):
    p=CASES[name];ref=reference(p,rtol=2e-12);previous=None
    for n in (2,4,8,16):
        c=tuple(Q(i,n) for i in range(1,n))
        raw,cert=u.certify(p,c);rows=verify(p,c,raw,cert,ref)
        if previous is None:previous=rows
    if name in ('DD','NN','DN'):assert max(x['width'] for x in rows)<1e-20
    else:assert max(x['width'] for x in rows)<max(x['width'] for x in previous)/2

@pytest.mark.parametrize('left,right',list(product(('D','N','R'),repeat=2)))
def test_all_endpoints(left,right):
    p=u.r.Problem((1,1),(0,0),(1,1),(left,int(left=='R')),(right,int(right=='R')))
    c=(Q(1,2),);raw,cert=u.certify(p,c)
    assert raw==u.r.assemble(p,c) and u.replay(p,c,cert)

def test_pi_and_sqrt():
    lo,hi=u.pi_interval()
    # Independent rational decimal bracket, known from elementary arctangent expansion.
    a=Q('3.1415926535897932384626433832795028841971')
    b=a+Q(1,10**40)
    assert lo<a<b<hi and hi-lo<Q(1,10**22)
    for x in (Q(0),Q(2),Q(1,3),Q(16)):
        y=u.sqrt_upper(x);assert y*y>=x and (y-Q(1,10**12)<=0 or (y-Q(1,10**12))**2<=x)

def test_null_mode_and_replay_no_eigh(monkeypatch):
    p=CASES['NN'];c=(Q(1,2),);raw,cert=u.certify(p,c)
    d=json.loads(cert);assert d['rows'][0]['lower']==d['rows'][0]['upper']=='0'
    monkeypatch.setattr(u,'eigh',lambda *a,**k:pytest.fail('replay called floating eigensolver'))
    assert u.replay(p,c,cert)

def test_corruption():
    p=CASES['DD'];c=(Q(1,2),);raw,cert=u.certify(p,c)
    with pytest.raises(ValueError,match='replay'):u.replay(p,c,cert+b' ')
    d=json.loads(cert);d['rows'][0]['upper']='0'
    with pytest.raises(ValueError,match='replay'):u.replay(p,c,u._canonical(d))
    d=json.loads(cert);d['rows'][0]['ritz_upper_trial']='1'
    with pytest.raises(ValueError,match='upper inertia'):u.replay(p,c,u._canonical(d))

def test_exact_inertia():
    Q0=Q(0);M=[[Q(1),Q0],[Q0,Q(1)]];S=[[Q(2),Q(1)],[Q(1),Q(2)]]
    assert u._dense_inertia(M,S,Q(5,2))['negative_pivots']==1
    assert u._tri_inertia([Q(1)]*2,[Q0],[Q(2)]*2,[Q(1)],Q(4))['negative_pivots']==2
    with pytest.raises(ZeroDivisionError):u._dense_inertia(M,S,Q(2))

def test_invalid_input():
    with pytest.raises(ValueError):u.certify(CASES['DD'],(Q(1,3),))
